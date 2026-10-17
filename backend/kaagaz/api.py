"""HTTP routes. Every route that touches the graph goes through the tool catalogue or a named query file."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis.exceptions import ConnectionError as RedisConnectionError

from . import agent, graph, memory
from .planner import MAX_DEPTH
from .tools import DEFAULT_PACK, ToolError, Tools, Trace, catalogue

log = logging.getLogger("kaagaz")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ROOT = graph.ROOT
FRONTEND_DIST = Path(os.environ.get("KAAGAZ_FRONTEND_DIST", ROOT / "frontend" / "dist"))
BENCH_RESULTS = ROOT / "bench" / "results"
SOURCES_INDEX = ROOT / "data" / "sources" / "index.json"
BROWSER_URL = os.environ.get("FALKORDB_BROWSER_URL", "http://localhost:3000")



@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("KAAGAZ_SEED_ON_START") == "1":
        for pid in graph.list_packs():
            try:
                # always rebuild the shared rules graph from pack.yaml (under a second), so it never goes stale;
                # student graphs (kaagaz:student:*) are separate and untouched
                log.info("seeding %s: %s", pid, graph.seed_pack(pid))
            except RedisConnectionError:
                log.warning("FalkorDB not reachable at startup; seed later with scripts/seed.sh")
    yield


app = FastAPI(title="Kaagaz", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RedisConnectionError)
async def falkordb_down(_req: Request, _exc: Exception):
    return JSONResponse(status_code=503, content={
        "error": "falkordb_unreachable",
        "message": "FalkorDB isn't reachable. Start it with `docker compose up -d`."})


@app.exception_handler(ToolError)
async def tool_error(_req: Request, exc: ToolError):
    return JSONResponse(status_code=422, content={"error": "bad_arguments", "message": str(exc)})


def tools(pack_id: str = DEFAULT_PACK) -> Tools:
    if pack_id not in graph.list_packs():
        raise HTTPException(404, f"unknown pack {pack_id}")
    return Tools(pack_id)


def call(pack_id: str, name: str, args: dict) -> dict:
    return tools(pack_id).call(name, args).as_dict()


def _pack_param(pack: str | None) -> str:
    return pack or DEFAULT_PACK


# ---- meta ------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    try:
        graphs = graph.db().list_graphs()
    except RedisConnectionError:
        return {"ok": False, "falkordb": False,
                "message": "FalkorDB isn't reachable. Start it with `docker compose up -d`."}
    packs = graph.list_packs()
    seeded = {p: graph.rules_graph_name(p) in graphs for p in packs}
    return {"ok": all(seeded.values()), "falkordb": True, "packs": seeded, "llm": agent.llm_configured(),
            "llm_model": agent.config().get("model") if agent.llm_configured() else None,
            "browser_url": BROWSER_URL}


@app.get("/api/packs")
def packs() -> list[dict]:
    return [graph.load_pack(p)["pack"] | {"id": p} for p in graph.list_packs()]


@app.get("/api/tools")
def tool_catalogue() -> list[dict]:
    return catalogue()


@app.get("/api/queries")
def queries() -> list[dict]:
    out = []
    for name in graph.query_names():
        raw = (graph.QUERIES_DIR / f"{name}.cypher").read_text()
        doc = " ".join(ln.lstrip("/ ").strip() for ln in raw.splitlines() if ln.lstrip().startswith("//"))
        out.append({"name": name, "file": f"backend/kaagaz/queries/{name}.cypher", "about": doc,
                    "cypher": graph.query_text(name)})
    return out


# ---- pack data -------------------------------------------------------------------

@app.get("/api/schemes")
def schemes(pack: str | None = None) -> dict:
    pid = _pack_param(pack)
    t = tools(pid)
    trace = Trace()
    rows = t._q("schemes", {}, trace)
    today = t.today()
    out = []
    for r in rows:
        s = dict(r["scheme"])
        end = s.get("window_end")
        s["days_left"] = t.calendar.days_between(today, dt.date.fromisoformat(end)) if end else None
        s["day_unit"] = "working days" if t.calendar.working else "days"
        s["direct_requirements"] = r["direct_requirements"]
        out.append(s)
    return {"today": today.isoformat(), "schemes": out, "trace": trace.rows}


@app.get("/api/documents")
def documents(pack: str | None = None) -> dict:
    t = tools(_pack_param(pack))
    trace = Trace()
    rows = t._q("documents", {}, trace)
    groups = t.pack.get("groups") or []
    where = {d: g["label"] for g in groups for d in g["docs"]}
    for r in rows:
        r["group"] = where.get(r["id"], "Other papers")
    return {"documents": rows, "groups": [g["label"] for g in groups] + ["Other papers"], "trace": trace.rows}


@app.get("/api/schemes/{scheme_id}/prerequisites")
def prerequisites(scheme_id: str, depth: int = MAX_DEPTH, pack: str | None = None) -> dict:
    return call(_pack_param(pack), "prerequisites", {"scheme_id": scheme_id, "depth": depth})


@app.get("/api/explain")
def explain(scheme_id: str, doc_id: str, pack: str | None = None) -> dict:
    res = call(_pack_param(pack), "explain", {"scheme_id": scheme_id, "doc_id": doc_id})
    res["cypher"] = {"explain": graph.query_text("explain"), "document_detail": graph.query_text("document_detail")}
    res["browser_url"] = BROWSER_URL
    res["rules_graph"] = graph.rules_graph_name(_pack_param(pack))
    return res


@app.get("/api/load-bearing")
def load_bearing(pack: str | None = None, student_id: str | None = None) -> dict:
    t = tools(_pack_param(pack))
    trace = Trace()
    held = sorted(h["doc_id"] for h in memory.holdings(student_id, trace)) if student_id else []
    ids = [r["scheme"]["id"] for r in t._q("schemes", {}, trace)]
    if student_id:
        tg = [x["scheme_id"] for x in memory.targets(student_id, trace)]
        ids = tg or ids
    rows = t._q("load_bearing", {"scheme_ids": ids, "held": held, "limit": 8}, trace)
    pr = t._q("load_bearing_pagerank", {"limit": 8}, trace)
    return {"scheme_ids": ids, "by_scheme_count": rows, "pagerank": pr, "trace": trace.rows}


@app.get("/api/graph-stats")
def graph_stats(pack: str | None = None) -> dict:
    pid = _pack_param(pack)
    r = graph.run(graph.rules_graph_name(pid), "graph_stats")
    return {"graph": graph.rules_graph_name(pid), "rows": r.rows, "ms": r.ms}


@app.get("/api/sources")
def sources(pack: str | None = None) -> dict:
    pid = _pack_param(pack)
    index = json.loads(SOURCES_INDEX.read_text())
    usage = graph.run(graph.rules_graph_name(pid), "source_usage").rows
    counts: dict[str, int] = {}
    for u in usage:
        counts[u["url"]] = counts.get(u["url"], 0) + u["n"]
    pk = graph.load_pack(pid)
    conf: dict[str, set] = {}

    def note(c):
        if c:
            conf.setdefault(c["source_url"], set()).add(c["confidence"])

    for r in pk["rules"]:
        note(r["cite"])
    for d in pk["documents"]:
        note(d.get("days_cite"))
        note(d.get("office_cite"))
    for s in pk["schemes"]:
        note((s.get("window") or {}).get("cite"))
    out = []
    for row in index:
        c = conf.get(row["url"], set())
        out.append({"id": row["id"], "title": row["title"], "url": row["url"], "retrieved_at": row["retrieved_at"],
                    "sha256": row["sha256"], "content_type": row["content_type"], "size": row["size"],
                    "rules_citing": counts.get(row["url"], 0),
                    "confidence": "secondary" if c == {"secondary"} else ("official" if "official" in c else None)})
    out.sort(key=lambda r: (-r["rules_citing"], r["title"]))
    return {"sources": out}


# ---- students and plans ------------------------------------------------------------

class NewStudent(BaseModel):
    label: str = Field(default="Student", max_length=60)


@app.post("/api/students")
def new_student(body: NewStudent) -> dict:
    sid = "s-" + secrets.token_hex(6)
    return memory.ensure_student(sid, body.label)


@app.post("/api/students/example")
def load_example(pack: str | None = None) -> dict:
    """Reset and load the synthetic Example student defined in the pack."""
    pid = _pack_param(pack)
    ex = graph.load_pack(pid).get("example_student")
    if not ex:
        raise HTTPException(404, "this pack has no example student")
    sid = memory.EXAMPLE_ID if pid == DEFAULT_PACK else f"{memory.EXAMPLE_ID}-{pid}"[:64]
    memory.reset(sid)
    label = ex.get("label") or memory.EXAMPLE_LABEL
    memory.ensure_student(sid, label)
    for h in ex.get("holdings", []):
        memory.add_holding(sid, h, None)
    deadline = str(ex["deadline"]) if ex.get("deadline") else None
    memory.set_target(sid, ex["scheme_id"], deadline, "example_own_date" if deadline else "published_window")
    return {"student_id": sid, "label": label, "scheme_id": ex["scheme_id"],
            "holdings": ex.get("holdings", []), "about": ex.get("about")}


@app.get("/api/students/{student_id}")
def recall(student_id: str, pack: str | None = None) -> dict:
    return call(_pack_param(pack), "recall", {"student_id": student_id})


class TargetBody(BaseModel):
    scheme_id: str
    deadline: dt.date | None = None


@app.put("/api/students/{student_id}/target")
def set_target(student_id: str, body: TargetBody, pack: str | None = None) -> dict:
    t = tools(_pack_param(pack))
    trace = Trace()
    if t._need(body.scheme_id, "Scheme", trace) is None:
        raise HTTPException(404, f"unknown scheme {body.scheme_id}")
    memory.ensure_student(student_id, trace=trace)
    src = "student" if body.deadline else "published_window"
    return memory.set_target(student_id, body.scheme_id, body.deadline.isoformat() if body.deadline else None, src,
                             trace) | {"trace": trace.rows}


class HoldingBody(BaseModel):
    doc_id: str
    issued_on: dt.date | None = None


@app.post("/api/students/{student_id}/holdings")
def add_holding(student_id: str, body: HoldingBody, pack: str | None = None) -> dict:
    return call(_pack_param(pack), "remember_holding",
                {"student_id": student_id, "doc_id": body.doc_id,
                 "issued_on": body.issued_on.isoformat() if body.issued_on else None})


@app.delete("/api/students/{student_id}/holdings/{doc_id}")
def remove_holding(student_id: str, doc_id: str) -> dict:
    memory.check_id(student_id)
    trace = Trace()
    n = memory.remove_holding(student_id, doc_id, trace)
    return {"removed": n, "trace": trace.rows}


@app.delete("/api/students/{student_id}")
def forget_student(student_id: str) -> dict:
    """Delete a student's whole memory graph (kaagaz:student:<id>)."""
    existed = memory.exists(memory.check_id(student_id))
    memory.reset(student_id)
    return {"deleted": existed}


@app.get("/api/plan")
def plan(student_id: str, scheme_id: str, depth: int = MAX_DEPTH, remember: bool = True,
         pack: str | None = None) -> dict:
    res = call(_pack_param(pack), "plan", {"student_id": student_id, "scheme_id": scheme_id, "depth": depth,
                                           "remember": remember})
    res["cypher"] = {n: graph.query_text(n) for n in ("prerequisites", "chain_days")}
    return res


@app.get("/api/alternatives")
def alternatives(student_id: str, scheme_id: str, pack: str | None = None) -> dict:
    return call(_pack_param(pack), "alternatives", {"student_id": student_id, "scheme_id": scheme_id})


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    student_id: str | None = None
    scheme_id: str | None = None


@app.post("/api/ask")
def ask(body: AskBody, pack: str | None = None) -> dict:
    return agent.ask(tools(_pack_param(pack)), body.question, body.student_id, body.scheme_id)


# ---- benchmark ---------------------------------------------------------------------

@app.get("/api/benchmark")
def benchmark() -> dict:
    files = sorted(BENCH_RESULTS.glob("*.json"))
    llm_runs = [f for f in files if not f.name.startswith("deterministic-")]
    det_runs = [f for f in files if f.name.startswith("deterministic-")]
    return {
        "llm_run": json.loads(llm_runs[-1].read_text()) if llm_runs else None,
        "llm_run_file": llm_runs[-1].name if llm_runs else None,
        "deterministic_run": json.loads(det_runs[-1].read_text()) if det_runs else None,
        "deterministic_run_file": det_runs[-1].name if det_runs else None,
        "llm_configured": agent.llm_configured(),
    }


# ---- frontend ----------------------------------------------------------------------

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(FRONTEND_DIST / "index.html")
