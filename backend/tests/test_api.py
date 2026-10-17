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
    assert r["label"] == "Example student" and r["student_id"] == "example-student"
    rec = client.get("/api/students/example-student").json()
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
