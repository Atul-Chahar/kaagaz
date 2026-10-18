"""HTTP API against a real FalkorDB, through FastAPI's TestClient."""

import pytest
from fastapi.testclient import TestClient

from kaagaz import graph, memory
from kaagaz.api import app

pytestmark = pytest.mark.integration
client = TestClient(app)
OUTCOMES = {"answered_with_path", "answered_from_memory", "not_in_graph", "unknown_name", "no_official_time"}


@pytest.fixture(scope="module", autouse=True)
def seeded():
    graph.seed_pack("in-ka-scholarships")


@pytest.fixture
def sid():
    s = client.post("/api/students", json={"label": "Student"}).json()["id"]
    yield s
    memory.reset(s)


def test_health_reports_falkordb_and_no_llm(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    h = client.get("/api/health").json()
    assert h["falkordb"] is True and h["ok"] is True and h["llm"] is False


def test_schemes_and_documents():
    s = client.get("/api/schemes").json()
    assert len(s["schemes"]) == 11 and all("days_left" in x for x in s["schemes"])
    d = client.get("/api/documents").json()
    assert d["documents"] and all(x["group"] for x in d["documents"])


def test_every_tool_response_has_outcome_and_trace(sid):
    client.put(f"/api/students/{sid}/target", json={"scheme_id": "ka-ssp-pms-obc"})
    calls = [
        client.get("/api/schemes/ka-ssp-pms-obc/prerequisites?depth=2"),
        client.get(f"/api/plan?student_id={sid}&scheme_id=ka-ssp-pms-obc&depth=3"),
        client.get("/api/explain?scheme_id=ka-ssp-pms-obc&doc_id=caste-income-certificate-ka"),
        client.get(f"/api/alternatives?student_id={sid}&scheme_id=ka-ssp-pms-obc"),
        client.post(f"/api/students/{sid}/holdings", json={"doc_id": "aadhaar"}),
        client.get(f"/api/students/{sid}"),
    ]
    for r in calls:
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["outcome"] in OUTCOMES
        tools = [t for t in body["trace"] if t["kind"] == "tool"]
        assert len(tools) == 1
        assert {"tool", "args", "ms", "rows"} <= set(tools[0])
        assert any(t["kind"] == "query" for t in body["trace"])


def test_plan_depth_validation_is_422():
    r = client.get("/api/plan?student_id=abc-123&scheme_id=ka-ssp-pms-obc&depth=9")
    assert r.status_code == 422


def test_unknown_scheme_is_unknown_name(sid):
    r = client.get(f"/api/plan?student_id={sid}&scheme_id=not-a-scheme").json()
    assert r["outcome"] == "unknown_name"


def test_example_student_is_labelled_and_synthetic():
    r = client.post("/api/students/example").json()
    assert r["label"] == "Example student" and r["student_id"].startswith("example-")
    other = client.post("/api/students/example").json()["student_id"]
    assert other != r["student_id"]  # each visitor gets a private copy
    client.post(f"/api/students/example?replace={other}")
    assert not memory.exists(other)  # the replaced copy is deleted
    rec = client.get(f"/api/students/{r['student_id']}").json()
    assert rec["data"]["student"]["label"] == "Example student"
    assert {h["doc_id"] for h in rec["data"]["holdings"]} == set(r["holdings"])


def test_ask_without_llm_is_name_search(monkeypatch, sid):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    r = client.post("/api/ask", json={"question": "Does Fee Reimbursement for Minorities need a caste and income certificate?",
                                      "student_id": sid}).json()
    assert r["mode"] == "name_search"
    assert r["tool"] == "explain" and r["outcome"] in ("answered_with_path", "no_official_time")
    r = client.post("/api/ask", json={"question": "How do I get a domicile certificate?"}).json()
    assert r["outcome"] == "unknown_name"


def test_sources_and_queries_and_benchmark():
    s = client.get("/api/sources").json()["sources"]
    assert s and all(len(x["sha256"]) == 64 for x in s)
    assert sum(x["rules_citing"] for x in s) > 100
    q = client.get("/api/queries").json()
    names = {x["name"] for x in q}
    assert {"prerequisites", "chain_days", "shared_documents", "load_bearing", "fastest_option", "resolve_name"} <= names
    b = client.get("/api/benchmark").json()
    assert set(b) >= {"llm_run", "deterministic_run", "llm_configured"}


def test_falkordb_down_gives_plain_error(monkeypatch):
    from falkordb import FalkorDB
    graph.db.cache_clear()
    monkeypatch.setattr(graph, "db", lambda: FalkorDB(host="localhost", port=1))
    try:
        r = client.get("/api/schemes")
        assert r.status_code == 503
        assert r.json()["message"] == "FalkorDB isn't reachable. Start it with `docker compose up -d`."
    finally:
        monkeypatch.undo()
        graph.db.cache_clear()


def test_ask_name_search_does_not_reuse_scheme_words_for_the_document(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    r = client.post("/api/ask", json={"question": "Does PM YASASVI Top Class need a hostel certificate?"}).json()
    assert r["args"] == {"scheme_id": "nsp-pm-yasasvi-top-class-college", "doc_id": "hostel-certificate"}
    assert r["outcome"] == "not_in_graph"
    r = client.post("/api/ask", json={"question": "Do I need a PAN card for Vidyasiri?"}).json()
    assert r["args"]["doc_id"] == "pan-card"


def test_forget_student_deletes_the_graph(sid):
    client.post(f"/api/students/{sid}/holdings", json={"doc_id": "aadhaar"})
    assert client.delete(f"/api/students/{sid}").json() == {"deleted": True}
    assert client.get(f"/api/students/{sid}").json()["outcome"] == "not_in_graph"


def test_static_route_cannot_read_files_outside_the_frontend_build():
    from kaagaz import api as api_mod
    if not api_mod.FRONTEND_DIST.exists():
        pytest.skip("frontend not built")
    secret = "Kaagaz"  # README starts with "# Kaagaz"; any leak of it means traversal works
    for path in ("/../../README.md", "/..%2F..%2FREADME.md", "/%2e%2e/%2e%2e/README.md", "/../../../../../../etc/hostname"):
        r = client.get(path)
        assert "# Kaagaz" not in r.text, path
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert "<!doctype html>" in r.text.lower()  # falls back to the app shell
    assert secret


def test_sentence_checker_on_a_real_plan_rejects_wrong_numbers_and_invented_documents():
    from kaagaz import agent
    from kaagaz.tools import Tools
    ex = client.post("/api/students/example").json()["student_id"]
    t = Tools()
    res = t.call("plan", {"student_id": ex, "scheme_id": "ka-ssp-fee-reimbursement-minority",
                          "depth": 1, "remember": False})
    compact = {"outcome": res.outcome, "message": res.message, "data": agent._compact(res.data)}
    names = [d["name"] for d in t.pack["documents"]] + [s["name"] for s in t.pack["schemes"]]
    v = res.data["verdict"]
    assert v["kind"] == "on_time" and v["margin"] == 9
    good = (f"You need the caste and income certificate, which takes {v['critical_days']} working days, "
            f"so you have {v['margin']} days spare before 30 Nov 2026.")
    assert agent.check_sentence(good, compact, names) == {"ok": True, "problems": []}
    for bad in ("You are 25 days short.", "You have 28 days spare.", "You are 9 days short.", "You need a domicile certificate.",
                "You also need a ration card."):
        assert not agent.check_sentence(bad, compact, names)["ok"], bad


def test_bad_student_id_is_a_plain_422_not_a_crash():
    r = client.delete("/api/students/BAD ID!")
    assert r.status_code == 422 and "student_id" in r.json()["message"]


def test_as_of_header_changes_today_but_not_the_rules(sid):
    """The submission-day view: the same student and the same rules, counted from a chosen date, and labelled."""
    client.put(f"/api/students/{sid}/target", json={"scheme_id": "ka-ssp-pms-obc"})
    q = f"/api/plan?student_id={sid}&scheme_id=ka-ssp-pms-obc&remember=false"
    before = client.get(q, headers={"X-Kaagaz-As-Of": "2026-10-18"}).json()
    after = client.get(q, headers={"X-Kaagaz-As-Of": "2026-11-05"}).json()
    assert before["as_of"] is True and before["data"]["today"] == "2026-10-18"
    assert before["data"]["deadline"]["date"] == after["data"]["deadline"]["date"] == "2026-10-31"
    # 19 Oct to 31 Oct 2026 in Karnataka: 13 days minus 2 Sundays, the 4th Saturday (24th) and 2 holidays (20th, 26th)
    assert before["data"]["days_left"] == 9
    assert before["data"]["verdict"]["kind"] != "closed" and after["data"]["verdict"]["kind"] == "closed"
    assert [i["id"] for i in before["data"]["items"]] == [i["id"] for i in after["data"]["items"]]
    # the query-string form works too, and without either the real date is used and not labelled
    assert client.get(q + "&as_of=2026-11-05").json()["data"]["verdict"]["kind"] == "closed"
    assert client.get(q).json()["as_of"] is False


def test_as_of_is_per_request_and_bad_dates_are_422():
    s = client.get("/api/schemes", headers={"X-Kaagaz-As-Of": "2026-10-18"}).json()
    assert s["today"] == "2026-10-18" and s["as_of"] is True
    obc = next(x for x in s["schemes"] if x["id"] == "ka-ssp-pms-obc")
    assert obc["days_left"] == 9
    assert client.get("/api/schemes").json()["as_of"] is False
    r = client.get("/api/schemes", headers={"X-Kaagaz-As-Of": "18/10/2026"})
    assert r.status_code == 422 and r.json()["error"] == "bad_arguments"
    assert client.get("/api/health").json()["snapshot_date"] == "2026-10-18"
