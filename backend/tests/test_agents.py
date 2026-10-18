"""Watcher, reviewer and caseworker agents end to end, on a real FalkorDB.

The network is replaced by a fetcher that serves the saved source text (changed where a test needs a change), and
the packs and sources are a temporary copy, so the real data is never touched. The agents graph is a test graph.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from kaagaz import agents, caseworker, graph, memory, sources, watcher
from kaagaz.sources import Fetched
from kaagaz.tools import ToolError, Tools

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
PACK = "in-ka-scholarships"
BCWD = "bcwd-ka-postmatric-2026-27"


class FakeFetcher:
    """Serves each source's saved text, with optional edits, and records what was asked for."""

    def __init__(self, edits: dict[str, tuple[str, str]] | None = None):
        self.edits = edits or {}
        self.asked: list[str] = []

    def fetch(self, url, dest: Path, name: str) -> Fetched:
        self.asked.append(name)
        row = next(r for r in sources.load_index() if r["id"] == name)
        text = sources.saved_text(row)
        if name in self.edits:
            old, new = self.edits[name]
            # saved text can break a sentence across lines, so match the words with any whitespace between them
            text, n = re.subn(r"\s+".join(map(re.escape, old.split())), new, text)
            assert n > 0
        dest.mkdir(parents=True, exist_ok=True)
        raw, txt = dest / f"{name}.html", dest / f"{name}.txt"
        raw.write_text(text)
        txt.write_text(text)
        import hashlib
        return Fetched("ok", http=200, sha256=hashlib.sha256(raw.read_bytes()).hexdigest(), raw_path=raw,
                       text_path=txt, text=text, content_type="text/html", size=len(text))

    def close(self):
        pass


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A temporary repo copy (scripts, packs, sources text and index) wired into the app, and a test agents graph."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    for f in ("audit_data.py", "textnorm.py"):
        shutil.copy(ROOT / "scripts" / f, repo / "scripts" / f)
    shutil.copytree(ROOT / "data" / "packs", repo / "data" / "packs")
    src = repo / "data" / "sources"
    shutil.copytree(ROOT / "data" / "sources" / "text", src / "text")
    shutil.copy(ROOT / "data" / "sources" / "index.json", src / "index.json")
    (src / "raw").mkdir()
    for r in sources.load_index():  # the audit checks raw hashes, so copy the raw files that are in git
        p = ROOT / "data" / "sources" / r["file"]
        if p.exists() and not r.get("large_not_in_git"):
            shutil.copy(p, src / r["file"])
    for mod in (sources, watcher):
        monkeypatch.setattr(mod, "SRC", src)
        monkeypatch.setattr(mod, "CHECKS", src / "checks")
    monkeypatch.setattr(sources, "INDEX", src / "index.json")
    monkeypatch.setattr(sources, "LOCK", src / ".fetch.lock")
    monkeypatch.setattr(graph, "PACKS_DIR", repo / "data" / "packs")
    monkeypatch.setattr(agents, "AGENTS_GRAPH", "kaagaz:test:agents")
    graph.delete_graph("kaagaz:test:agents")
    graph.load_pack.cache_clear()
    graph.seed_pack(PACK)
    students: list[str] = []
    yield {"repo": repo, "students": students}
    for s in students:
        memory.reset(s)
    graph.delete_graph("kaagaz:test:agents")
    monkeypatch.undo()
    graph.load_pack.cache_clear()
    graph.seed_pack(PACK)


def student(world, sid: str, scheme: str, holdings=()) -> str:
    memory.reset(sid)
    memory.ensure_student(sid, "Student")
    for h in holdings:
        memory.add_holding(sid, h, None)
    memory.set_target(sid, scheme, None, "published_window", pack=PACK)
    world["students"].append(sid)
    return sid


def scheme(sid: str) -> dict:
    rows = graph.run(graph.rules_graph_name(PACK), "schemes", {}).rows
    return next(dict(r["scheme"]) for r in rows if r["scheme"]["id"] == sid)


def audit(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(repo / "scripts" / "audit_data.py")], capture_output=True, text=True,
                          check=False)


def test_unchanged_sources_raise_no_findings_and_every_check_is_recorded(world):
    res = watcher.run_watch(PACK, only=[BCWD, "nsp-all-scholarships"], fetcher=FakeFetcher())
    assert res["run"]["status"] == "done" and res["findings"] == []
    assert {c["source_id"] for c in res["checks"]} == {BCWD, "nsp-all-scholarships"}
    assert all(c["status"] == "same_text" and c["rules_missing"] == 0 for c in res["checks"])
    urls = {c["url"] for c in res["checks"]}
    expected = [r for r in graph.run(graph.rules_graph_name(PACK), "rules_by_source", {}).rows if r["url"] in urls]
    assert sum(c["rules_checked"] for c in res["checks"]) == len(expected) > 0


def test_a_moved_deadline_is_found_approved_applied_audited_and_reaches_the_affected_student(world):
    sid = student(world, "agents-test-a", "ka-ssp-fee-concession-bcwd")
    other = student(world, "agents-test-b", "ka-ssp-pms-sc")  # a scheme the change does not touch
    before = Tools(PACK).plan_core(sid, "ka-ssp-fee-concession-bcwd", 8, watcher_trace(), save=True)
    fake = FakeFetcher({BCWD: ("31.10.2026", "15.11.2026")})
    res = watcher.run_watch(PACK, only=[BCWD], fetcher=fake)
    found = [agents.finding(f) for f in res["findings"]]
    dates = [f for f in found if f["kind"] == "date_changed"]
    assert {f["rule_key"] for f in dates} == {"window:ka-ssp-fee-concession-bcwd", "window:ka-ssp-vidyasiri-bcwd"}
    f = next(f for f in dates if f["rule_key"] == "window:ka-ssp-fee-concession-bcwd")
    assert f["new_value"] == "2026-11-15" and f["old_value"] == "2026-10-31" and f["status"] == "open"
    assert f["schemes"] == ["ka-ssp-fee-concession-bcwd"]
    listed = next(x for x in agents.findings(PACK) if x["id"] == f["id"])
    assert listed["students"] == 1  # through the shared registry

    # nothing changes before a person approves
    assert scheme("ka-ssp-fee-concession-bcwd")["window_end"] == "2026-10-31"

    out = watcher.decide(f["id"], approve=True, note="checked the page")
    assert out["applied"]["kind"] == "window_end" and out["applied"]["value"] == "2026-11-15"
    props = scheme("ka-ssp-fee-concession-bcwd")
    assert props["window_end"] == "2026-11-15" and props["window_changed_from"] == "2026-10-31"
    changes = yaml.safe_load((world["repo"] / "data/packs" / PACK / "changes.yaml").read_text())["changes"]
    assert changes[0]["cite"]["excerpt"] == "Last date to apply: 15.11.2026"
    r = audit(world["repo"])
    assert r.returncode == 0, r.stdout

    # the caseworker re-planned the affected student only, and left an alert in that student's own graph
    notified = out["propagation"]["notified"]
    assert [n["student_id"] for n in notified] == [sid]
    alert = memory.alerts(sid)[0]
    assert alert["finding_id"] == f["id"] and "2026-10-31 to 2026-11-15" in alert["message"]
    assert alert["before"] == before["verdict"]["stamp"]
    assert memory.alerts(other) == []
    # handled once: running the caseworker again finds nothing new
    assert caseworker.propagate(PACK)["notified"] == []
    with pytest.raises(ValueError):
        watcher.decide(f["id"], approve=True)


def test_a_rejected_finding_changes_nothing(world):
    fake = FakeFetcher({BCWD: ("31.10.2026", "15.11.2026")})
    res = watcher.run_watch(PACK, only=[BCWD], fetcher=fake)
    fid = res["findings"][0]
    out = watcher.decide(fid, approve=False, note="typo on the page")
    assert out["applied"] is None and out["finding"]["status"] == "rejected"
    assert not (world["repo"] / "data/packs" / PACK / "changes.yaml").exists()
    # seen again later, it keeps its decision instead of coming back as new
    again = watcher.run_watch(PACK, only=[BCWD], fetcher=fake)
    assert agents.finding(fid)["status"] == "rejected" and fid in again["findings"]


def test_a_vanished_proof_sentence_is_marked_stale_not_deleted(world):
    fake = FakeFetcher({BCWD: ("Last date to apply: 31.10.2026", "Dates will be announced.")})
    res = watcher.run_watch(PACK, only=[BCWD], fetcher=fake)
    f = next(agents.finding(x) for x in res["findings"] if agents.finding(x)["kind"] == "excerpt_missing")
    watcher.decide(f["id"], approve=True)
    props = scheme(f["from_id"])
    assert props["window_end"] == "2026-10-31" and props["window_stale_since"]
    assert audit(world["repo"]).returncode == 0


def test_the_watcher_checks_sources_of_targeted_schemes_first(world):
    student(world, "agents-test-c", "ka-ssp-fee-concession-bcwd")
    fake = FakeFetcher()
    watcher.run_watch(PACK, limit=1, fetcher=fake)
    assert fake.asked == [BCWD]


def watcher_trace():
    from kaagaz.tools import Trace
    return Trace()


def test_caseworker_investigates_decides_proposes_and_acts_only_on_approval(world):
    sid = student(world, "agents-test-d", "ka-ssp-pms-obc")
    t = Tools(PACK)
    r = caseworker.review(t, sid, narrate=False)
    tools_used = [s["tool"] for s in r["steps"]]
    assert tools_used[:2] == ["recall", "plan"] and "alternatives" in tools_used and tools_used[-2:] == ["decide",
                                                                                                         "propose"]
    assert r["verdict"]["kind"] in ("late", "late_at_least") and r["decision"]["kind"] == "plan_b"
    assert r["since"] is None
    pending = [p for p in r["proposals"] if p["status"] == "pending"]
    assert pending and memory.tasks(sid) == []  # nothing done yet
    done = caseworker.act(t, sid, pending[0]["id"], approve=True)
    assert done["done"]["task"]["status"] == "open" and len(memory.tasks(sid)) == 1
    assert done["plan_after"]["scheme_id"] == "ka-ssp-pms-obc"
    with pytest.raises(ToolError):
        caseworker.act(t, sid, pending[0]["id"], approve=True)  # already decided
    # the second review remembers the first
    memory.add_holding(sid, "sslc-marks-card", None)
    r2 = caseworker.review(t, sid, narrate=False)
    assert r2["since"]["new_holdings"] == ["sslc-marks-card"] and r2["since"]["stamp_before"] == r["verdict"]["stamp"]
    assert {p["status"] for p in memory.proposals(sid) if p["case_id"] == r["case_id"]} >= {"approved", "replaced"}


def test_agents_and_case_api(world):
    from kaagaz.api import app
    c = TestClient(app)
    sid = student(world, "agents-test-e", "ka-ssp-pms-obc")
    a = c.get("/api/agents").json()
    assert {x["id"] for x in a["agents"]} == {"watcher", "reviewer", "caseworker"}
    r = c.post(f"/api/students/{sid}/case", json={}).json()
    assert r["steps"] and r["decision"]["text"]
    pid = next(p["id"] for p in r["proposals"] if p["status"] == "pending")
    assert c.post(f"/api/students/{sid}/proposals/{pid}", json={"approve": True}).status_code == 200
    state = c.get(f"/api/students/{sid}/case").json()
    assert state["review"]["id"] == r["case_id"] and len(state["tasks"]) == 1
    ics = c.get(f"/api/students/{sid}/tasks.ics")
    assert ics.headers["content-type"].startswith("text/calendar") and "BEGIN:VEVENT" in ics.text
    tid = state["tasks"][0]["id"]
    assert c.post(f"/api/students/{sid}/tasks/{tid}", json={"status": "done"}).json()["task"]["status"] == "done"
    assert c.post("/api/agents/findings/f-nothing", json={"approve": True}).status_code == 404
    as_of = c.post(f"/api/students/{sid}/case", json={}, headers={"X-Kaagaz-As-Of": "2026-10-18"}).json()
    assert as_of["as_of"] is True and as_of["today"] == "2026-10-18"
