"""Integration tests against a real FalkorDB (docker compose). No database mocks.

Run: docker compose up -d falkordb && cd backend && uv run pytest -m integration
"""

from __future__ import annotations

import datetime as dt
import itertools
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

from kaagaz import graph, memory
from kaagaz.planner import MAX_DEPTH, Planner, RuleGraph
from kaagaz.tools import Tools, Trace

pytestmark = pytest.mark.integration
PACK = "in-ka-scholarships"
RULES = graph.rules_graph_name(PACK)


@pytest.fixture(scope="module", autouse=True)
def seeded():
    try:
        graph.db().list_graphs()
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"FalkorDB is not reachable ({e}). Start it with `docker compose up -d falkordb`.")
    stats = graph.seed_pack(PACK)
    assert stats["nodes"]["Scheme"] > 0
    yield stats


@pytest.fixture
def student():
    sid = f"test-{os.getpid()}-{time.time_ns() % 10**8}"
    yield sid
    memory.reset(sid)


def pack():
    return graph.load_pack(PACK)


def scheme_ids():
    return [s["id"] for s in pack()["schemes"]]


def test_seed_matches_pack_counts(seeded):
    p = pack()
    assert seeded["nodes"]["Scheme"] == len(p["schemes"])
    assert seeded["nodes"]["Document"] == len(p["documents"])
    assert seeded["nodes"]["AnyOf"] == len(p["any_of"])
    req = sum(1 for r in p["rules"] if r["kind"] == "REQUIRES")
    opt = sum(1 for r in p["rules"] if r["kind"] == "OPTION")
    assert seeded["edges"]["REQUIRES"] == req
    assert seeded["edges"]["OPTION"] == opt


def test_every_rule_edge_carries_its_source():
    rows = graph.db().select_graph(RULES).ro_query(
        "MATCH ()-[r:REQUIRES|OPTION]->() RETURN r.source_url, r.source_title, r.retrieved_at, r.excerpt, "
        "r.confidence").result_set
    assert rows
    for row in rows:
        assert all(v for v in row), row


# ---- every query file runs ----------------------------------------------------------

PARAMS = {
    "prerequisites": {"scheme_id": None, "depth": 3},
    "chain_days": {"scheme_id": None, "held": [], "depth": 8, "applies": [], "limit": 5},
    "shared_documents": {"scheme_id": None, "needed": ["caste-income-certificate-ka", "aadhaar"]},
    "load_bearing": {"scheme_ids": None, "held": [], "limit": 5},
    "load_bearing_pagerank": {"limit": 5},
    "fastest_option": {"anyof_id": None, "held": []},
    "resolve_name": {"q": None},
    "search_names": {"words": ["income"], "limit": 5},
    "explain": {"scheme_id": None, "doc_id": "aadhaar"},
    "document_detail": {"doc_id": "caste-income-certificate-ka"},
    "schemes": {},
    "documents": {},
    "source_usage": {},
    "graph_stats": {},
}


def test_every_rules_query_runs_and_returns_rows():
    s0 = scheme_ids()[0]
    a0 = pack()["any_of"][0]["id"]
    fill = {"scheme_id": s0, "scheme_ids": scheme_ids(), "anyof_id": a0, "q": s0}
    names = [n for n in graph.query_names() if not n.startswith(("seed_", "student_", "holding_", "target_",
                                                                     "snapshot_", "recall_", "applies_"))]
    assert set(names) == set(PARAMS), "every rules query must be covered by this test"
    for n in names:
        params = {k: (fill[k] if v is None else v) for k, v in PARAMS[n].items()}
        r = graph.run(RULES, n, params)
        assert r.rows, f"{n} returned no rows"


def test_prerequisites_depth_is_monotonic_and_capped():
    for sid in scheme_ids():
        prev = 0
        for d in range(1, MAX_DEPTH + 1):
            rows = graph.run(RULES, "prerequisites", {"scheme_id": sid, "depth": d}).rows
            assert all(r["depth"] <= d for r in rows)
            assert len(rows) >= prev
            prev = len(rows)
        d1 = graph.run(RULES, "prerequisites", {"scheme_id": sid, "depth": 1}).rows
        direct = {r["to"] for r in pack()["rules"] if r["from"] == sid}
        assert {r["id"] for r in d1 if r["path"] == [sid, r["id"]]} == direct


def test_resolve_name_exact_and_case_insensitive():
    s = pack()["schemes"][0]
    rows = graph.run(RULES, "resolve_name", {"q": s["name"].upper()}).rows
    assert rows and rows[0]["id"] == s["id"] and rows[0]["match"] == "case_insensitive"
    rows = graph.run(RULES, "resolve_name", {"q": s["id"]}).rows
    assert rows[0]["match"] == "exact"
    assert graph.run(RULES, "resolve_name", {"q": "no such scheme anywhere"}).rows == []


# ---- chain_days.cypher agrees with planner.py -------------------------------------------

def _all_of(g: RuleGraph) -> RuleGraph:
    keep = {k: v for k, v in g.nodes.items() if v.label != "AnyOf"}
    return RuleGraph(g.root, keep, [e for e in g.edges if e.src in keep and e.dst in keep])


def test_chain_days_cypher_agrees_with_planner_on_all_of_chains():
    t = Tools(PACK)
    docs = [d["id"] for d in pack()["documents"]]
    held_sets = [set(), {"aadhaar"}, {"caste-income-certificate-ka"}, {"aadhaar", "bank-account"},
                 set(docs[::3]), set(docs[1::2])]
    checked = 0
    for sid in scheme_ids():
        for depth in (1, 2, 4, MAX_DEPTH):
            g, _rows, _s = t.build_rule_graph(sid, depth, Trace())
            conditional = sorted({e.dst for e in g.edges if e.props.get("condition")})
            for held in held_sets:
                for applies in ([], conditional):
                    rows = graph.run(RULES, "chain_days", {"scheme_id": sid, "held": sorted(held), "depth": depth,
                                                           "applies": applies, "limit": 1}).rows
                    cypher = rows[0]["days"] if rows else 0
                    planner = Planner(_all_of(g), held, applies=set(applies)).finish(sid).lb
                    assert cypher == planner, (sid, depth, sorted(held), applies)
                    checked += 1
    assert checked >= 100


def test_fastest_option_matches_planner_choice_when_options_have_no_nested_groups():
    t = Tools(PACK)
    p = pack()
    kids = {}
    for r in p["rules"]:
        kids.setdefault(r["from"], []).append(r["to"])
    anyof_ids = {a["id"] for a in p["any_of"]}

    def has_nested(n, seen=()):
        return any(k in anyof_ids or (k not in seen and has_nested(k, (*seen, k))) for k in kids.get(n, []))

    compared = 0
    for a in p["any_of"]:
        opts = kids.get(a["id"], [])
        if any(has_nested(o) for o in opts):
            continue
        rows = graph.run(RULES, "fastest_option", {"anyof_id": a["id"], "held": []}).rows
        # planner on a graph rooted at this AnyOf
        for sid in scheme_ids():
            g, _r, _s = t.build_rule_graph(sid, MAX_DEPTH, Trace())
            if a["id"] in g.nodes:
                pl = Planner(g, set())
                f = pl.finish(a["id"])
                assert rows[0]["total_days"] == f.lb, a["id"]
                compared += 1
                break
    assert compared >= 1


# ---- tools against the real graph -----------------------------------------------------

def test_unknown_name_runs_no_rules_query_beyond_resolve(student):
    t = Tools(PACK)
    r = t.call("plan", {"student_id": student, "scheme_id": "no-such-scheme"})
    assert r.outcome == "unknown_name"
    queries = [row["tool"] for row in r.trace if row["kind"] == "query"]
    assert queries == ["query:resolve_name"]


def test_explain_not_in_graph():
    t = Tools(PACK)
    sid = scheme_ids()[0]
    reachable = {r["id"] for r in graph.run(RULES, "prerequisites", {"scheme_id": sid, "depth": 8}).rows}
    unrelated = next(d["id"] for d in pack()["documents"] if d["id"] not in reachable)
    r = t.call("explain", {"scheme_id": sid, "doc_id": unrelated})
    assert r.outcome == "not_in_graph"


def test_explain_path_carries_sources():
    t = Tools(PACK)
    sid = "ka-ssp-pms-obc"
    r = t.call("explain", {"scheme_id": sid, "doc_id": "caste-income-certificate-ka"})
    assert r.outcome in ("answered_with_path", "no_official_time")
    path = r.data["paths"][0]
    assert path["nodes"][0]["id"] == sid and path["nodes"][-1]["id"] == "caste-income-certificate-ka"
    assert all(rule["source_url"] and rule["excerpt"] for rule in path["rules"])


def test_plan_trace_and_holding_changes_plan(student):
    t = Tools(PACK)
    sid = "ka-ssp-pms-obc"
    before = t.call("plan", {"student_id": student, "scheme_id": sid}).data
    assert before["critical_path"][0] == sid
    assert before["chain_check"]["agree"]
    first = before["critical_path"][1]
    t.call("remember_holding", {"student_id": student, "doc_id": first})
    after = t.call("plan", {"student_id": student, "scheme_id": sid}).data
    assert first in after["held"]
    assert after["verdict"]["critical_days"] <= before["verdict"]["critical_days"]
    assert first not in after["needed"]


# ---- per-student graph isolation -----------------------------------------------------

def test_student_graphs_are_isolated(student):
    other = student + "-b"
    try:
        t = Tools(PACK)
        t.call("remember_holding", {"student_id": student, "doc_id": "aadhaar"})
        t.call("remember_holding", {"student_id": other, "doc_id": "bank-account"})
        a = {h["doc_id"] for h in memory.holdings(student)}
        b = {h["doc_id"] for h in memory.holdings(other)}
        assert a == {"aadhaar"} and b == {"bank-account"}
        # one Cypher query on A's graph cannot see B's holding at all
        rows = graph.db().select_graph(graph.student_graph_name(student)).ro_query(
            "MATCH (h:Holding) RETURN h.doc_id").result_set
        assert [r[0] for r in rows] == ["aadhaar"]
        assert graph.student_graph_name(student) != graph.student_graph_name(other)
        pa = t.call("plan", {"student_id": student, "scheme_id": "ka-ssp-pms-obc"}).data
        assert "bank-account" not in pa["held"]
    finally:
        memory.reset(other)


def test_student_id_validation_blocks_graph_name_injection():
    with pytest.raises(ValueError):
        memory.check_id("x}) MATCH (n) DETACH DELETE n //")
    with pytest.raises(ValueError):
        memory.check_id("kaagaz:rules:in-ka-scholarships")


# ---- memory survives an app restart ----------------------------------------------------

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_api(port: int) -> subprocess.Popen:
    env = dict(os.environ)
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "kaagaz.api:app", "--port", str(port)],
                            cwd=Path(__file__).resolve().parent.parent, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=1).status_code == 200:
                return proc
        except httpx.HTTPError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("API did not start")


def test_memory_survives_app_restart(student):
    port = _free_port()
    api = _start_api(port)
    try:
        r = httpx.post(f"http://127.0.0.1:{port}/api/students/{student}/holdings",
                       json={"doc_id": "aadhaar", "issued_on": "2020-01-15"}, timeout=10)
        assert r.status_code == 200, r.text
    finally:
        api.send_signal(signal.SIGTERM)
        api.wait(timeout=10)
    api = _start_api(port)
    try:
        r = httpx.get(f"http://127.0.0.1:{port}/api/students/{student}", timeout=10).json()
        assert r["outcome"] == "answered_from_memory"
        assert [(h["doc_id"], h["issued_on"]) for h in r["data"]["holdings"]] == [("aadhaar", "2020-01-15")]
        assert r["data"]["holdings"][0]["added_at"][:10] == dt.datetime.now(dt.UTC).date().isoformat()
    finally:
        api.send_signal(signal.SIGTERM)
        api.wait(timeout=10)


def test_alternatives_rank_reachable_schemes(student):
    t = Tools(PACK)
    for doc in ("aadhaar", "bank-account"):
        t.call("remember_holding", {"student_id": student, "doc_id": doc})
    r = t.call("alternatives", {"student_id": student, "scheme_id": "ka-ssp-pms-obc"})
    opts = r.data["options"]
    assert len(opts) == len(scheme_ids()) - 1
    kinds = [o["verdict"]["kind"] == "on_time" for o in opts]
    assert kinds == sorted(kinds, reverse=True)  # every "can make it" option is listed first
    for a, b in itertools.pairwise(o for o in opts if o["verdict"]["kind"] == "on_time"):
        assert a["verdict"]["margin"] >= b["verdict"]["margin"]


def test_company_pack_converts_calendar_days_into_working_days_exactly():
    graph.seed_pack("in-ka-company")
    t = Tools("in-ka-company", today=dt.date(2026, 10, 17))
    assert t.pack_unit == "working_days"
    held = {"aadhaar", "pan-card", "co-dsc", "co-moa-aoa", "co-registered-office-proof",
            "co-spice-incorporation-certificate", "co-din", "co-company-pan", "co-company-tan", "co-bank-current-account"}
    p = t.plan_core("x-probe", "in-company-ready-to-hire", MAX_DEPTH, Trace(), held=held, save=False)
    pt = next(i for i in p["items"] if i["id"] == "co-professional-tax-ka")
    # 30 calendar days from 17 Oct 2026 end on 16 Nov 2026; count the working days in that span on the pack calendar
    assert pt["end"] == t.calendar.days_between(dt.date(2026, 10, 17), dt.date(2026, 11, 16))
    assert p["verdict"]["exact"] is True
    assert p["chain_check"]["agree"]



def test_conditional_requirement_counts_only_when_it_applies(student):
    t = Tools(PACK)
    sid = "nsp-csss"
    before = t.call("plan", {"student_id": student, "scheme_id": sid, "remember": False}).data
    cond = {c["doc_id"]: c for c in before["conditional"]}
    assert "disability-certificate" in cond and not cond["disability-certificate"]["applies"]
    assert "disability-certificate" not in before["needed"]
    memory.add_applies(student, "disability-certificate")
    after = t.call("plan", {"student_id": student, "scheme_id": sid, "remember": False}).data
    assert "disability-certificate" in after["needed"]
    assert after["chain_check"]["agree"]
