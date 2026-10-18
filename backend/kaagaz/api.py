"""HTTP routes. Every route that touches the graph goes through the tool catalogue or a named query file."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from redis.exceptions import ConnectionError as RedisConnectionError

from . import agent, agents, caseworker, graph, memory, watcher
from .planner import MAX_DEPTH
from .tools import DEFAULT_PACK, ToolError, Tools, Trace, catalogue

log = logging.getLogger("kaagaz")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
ROOT = graph.ROOT
FRONTEND_DIST = Path(os.environ.get("KAAGAZ_FRONTEND_DIST", ROOT / "frontend" / "dist"))
BENCH_RESULTS = ROOT / "bench" / "results"
SOURCES_INDEX = ROOT / "data" / "sources" / "index.json"
BROWSER_URL = os.environ.get("FALKORDB_BROWSER_URL", "http://localhost:3000")
# The day this build was submitted. The UI offers "see it as on this day" because most 2026-27 windows close soon
# after it, so a later visitor would otherwise only see closed windows. Rules and deadlines never change with it.
SNAPSHOT_DATE = dt.date.fromisoformat(os.environ.get("KAAGAZ_SNAPSHOT_DATE", "2026-10-18"))
AS_OF_HEADER = "x-kaagaz-as-of"
# "today" for this request: None means the real date in the pack's timezone
AS_OF: ContextVar[dt.date | None] = ContextVar("kaagaz_as_of", default=None)



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


def parse_as_of(raw: str | None) -> dt.date | None:
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"as_of must be a date like 2026-10-18, not {raw!r}") from None


class AsOfMiddleware:
    """Reads the X-Kaagaz-As-Of header (or ?as_of=) and sets the date every tool counts from, for this request only."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.inner(scope, receive, send)
        raw = dict(scope.get("headers") or []).get(AS_OF_HEADER.encode(), b"").decode()
        if not raw:
            raw = (parse_qs(scope.get("query_string", b"").decode()).get("as_of") or [""])[0]
        try:
            day = parse_as_of(raw)
        except ValueError as e:
            res = JSONResponse(status_code=422, content={"error": "bad_arguments", "message": str(e)})
            return await res(scope, receive, send)
        token = AS_OF.set(day)
        try:
            await self.inner(scope, receive, send)
        finally:
            AS_OF.reset(token)


app.add_middleware(AsOfMiddleware)


@app.exception_handler(RedisConnectionError)
async def falkordb_down(_req: Request, _exc: Exception):
    return JSONResponse(status_code=503, content={
        "error": "falkordb_unreachable",
        "message": "FalkorDB isn't reachable. Start it with `docker compose up -d`."})


@app.exception_handler(ValueError)
async def bad_value(_req: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"error": "bad_arguments", "message": str(exc)})


@app.exception_handler(ToolError)
async def tool_error(_req: Request, exc: ToolError):
    return JSONResponse(status_code=422, content={"error": "bad_arguments", "message": str(exc)})


def tools(pack_id: str = DEFAULT_PACK) -> Tools:
    if pack_id not in graph.list_packs():
        raise HTTPException(404, f"unknown pack {pack_id}")
    return Tools(pack_id, today=AS_OF.get())


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
            "browser_url": BROWSER_URL, "snapshot_date": SNAPSHOT_DATE.isoformat(),
            "as_of": AS_OF.get().isoformat() if AS_OF.get() else None}


@app.get("/api/packs")
def packs() -> list[dict]:
    # the default pack first, flagged, so the UI's wording always matches the data it shows by default
    ids = sorted(graph.list_packs(), key=lambda p: (p != DEFAULT_PACK, p))
    return [graph.load_pack(p)["pack"] | {"id": p, "default": p == DEFAULT_PACK} for p in ids]


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
    return {"today": today.isoformat(), "as_of": AS_OF.get() is not None, "schemes": out, "trace": trace.rows}


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
def load_example(pack: str | None = None, replace: str | None = None) -> dict:
    """Load a fresh private copy of the pack's synthetic Example student (so two visitors never reset each other).
    `replace` is this visitor's previous Example copy, which is deleted."""
    pid = _pack_param(pack)
    ex = graph.load_pack(pid).get("example_student")
    if not ex:
        raise HTTPException(404, "this pack has no example student")
    if replace and replace.startswith("example-") and memory.STUDENT_ID.match(replace):
        memory.reset(replace)
    sid = f"example-{secrets.token_hex(5)}"
    label = ex.get("label") or memory.EXAMPLE_LABEL
    memory.ensure_student(sid, label)
    for h in ex.get("holdings", []):
        memory.add_holding(sid, h, None)
    deadline = str(ex["deadline"]) if ex.get("deadline") else None
    memory.set_target(sid, ex["scheme_id"], deadline, "example_own_date" if deadline else "published_window",
                      pack=pid)
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
                             trace, pack=_pack_param(pack)) | {"trace": trace.rows}


class HoldingBody(BaseModel):
    doc_id: str
    issued_on: dt.date | None = None


@app.post("/api/students/{student_id}/holdings")
def add_holding(student_id: str, body: HoldingBody, pack: str | None = None) -> dict:
    return call(_pack_param(pack), "remember_holding",
                {"student_id": student_id, "doc_id": body.doc_id,
                 "issued_on": body.issued_on.isoformat() if body.issued_on else None})


class AppliesBody(BaseModel):
    doc_id: str


@app.post("/api/students/{student_id}/applies")
def add_applies(student_id: str, body: AppliesBody, pack: str | None = None) -> dict:
    """The student says a conditional requirement (e.g. hostel certificate) applies to them."""
    t = tools(_pack_param(pack))
    trace = Trace()
    if t._need(body.doc_id, "Document", trace) is None:
        raise HTTPException(404, f"unknown document {body.doc_id}")
    memory.ensure_student(student_id, trace=trace)
    return memory.add_applies(student_id, body.doc_id, trace) | {"trace": trace.rows}


@app.delete("/api/students/{student_id}/applies/{doc_id}")
def remove_applies(student_id: str, doc_id: str) -> dict:
    memory.check_id(student_id)
    trace = Trace()
    return {"removed": memory.remove_applies(student_id, doc_id, trace), "trace": trace.rows}


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
    # a plan counted from a chosen date is a view, not a visit: it is not saved to the student's memory
    res = call(_pack_param(pack), "plan", {"student_id": student_id, "scheme_id": scheme_id, "depth": depth,
                                           "remember": remember and AS_OF.get() is None})
    res["cypher"] = {n: graph.query_text(n) for n in ("prerequisites", "chain_days")}
    res["as_of"] = AS_OF.get() is not None
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


# ---- agents: the caseworker on one student's case ----------------------------------------------------------

class CaseBody(BaseModel):
    scheme_id: str | None = None


@app.post("/api/students/{student_id}/case")
def review_case(student_id: str, body: CaseBody | None = None, pack: str | None = None) -> dict:
    """The caseworker investigates the case (several tool calls), decides, and proposes actions (not yet done)."""
    memory.check_id(student_id)
    return caseworker.review(tools(_pack_param(pack)), student_id, (body.scheme_id if body else None),
                             as_of=AS_OF.get() is not None)


@app.get("/api/students/{student_id}/case")
def case_state(student_id: str) -> dict:
    """What the agents left in this student's graph: the last review, proposals, tasks and alerts."""
    memory.check_id(student_id)
    reviews = memory.cases(student_id, 1)
    return {"review": reviews[0] if reviews else None, "proposals": memory.proposals(student_id),
            "tasks": memory.tasks(student_id), "alerts": memory.alerts(student_id)}


class DecideBody(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=300)


@app.post("/api/students/{student_id}/proposals/{proposal_id}")
def decide_proposal(student_id: str, proposal_id: str, body: DecideBody, pack: str | None = None) -> dict:
    memory.check_id(student_id)
    return caseworker.act(tools(_pack_param(pack)), student_id, proposal_id, body.approve,
                          as_of=AS_OF.get() is not None)


class TaskBody(BaseModel):
    status: str = Field(pattern="^(open|done)$")


@app.post("/api/students/{student_id}/tasks/{task_id}")
def set_task(student_id: str, task_id: str, body: TaskBody, pack: str | None = None) -> dict:
    """Mark a task done or open. Done on an "apply for" task also records the application (dated today), so the
    plan starts counting that document down; open again removes it."""
    memory.check_id(student_id)
    t = memory.task_status(student_id, task_id, body.status)
    if t is None:
        raise HTTPException(404, "no such task")
    out: dict = {"task": t}
    if t.get("kind") == "apply" and t.get("doc_id"):
        if body.status == "done":
            out["application"] = memory.add_application(student_id, t["doc_id"],
                                                         tools(_pack_param(pack)).today().isoformat())
        else:
            out["application_removed"] = memory.remove_application(student_id, t["doc_id"])
    return out


class ApplicationBody(BaseModel):
    doc_id: str
    applied_on: dt.date | None = None


@app.post("/api/students/{student_id}/applications")
def add_application(student_id: str, body: ApplicationBody, pack: str | None = None) -> dict:
    """The student applied for a document on a date (today if not given). The plan counts it down from then."""
    t = tools(_pack_param(pack))
    trace = Trace()
    if t._need(body.doc_id, "Document", trace) is None:
        raise HTTPException(404, f"unknown document {body.doc_id}")
    on = body.applied_on or t.today()
    if on > t.today():
        raise ValueError("applied_on cannot be after today")
    memory.ensure_student(student_id, trace=trace)
    return memory.add_application(student_id, body.doc_id, on.isoformat(), trace) | {"trace": trace.rows}


@app.delete("/api/students/{student_id}/applications/{doc_id}")
def remove_application(student_id: str, doc_id: str) -> dict:
    memory.check_id(student_id)
    return {"removed": memory.remove_application(student_id, doc_id)}


@app.get("/api/students/{student_id}/tasks.ics")
def tasks_calendar(student_id: str):
    """The student's open tasks as an all-day calendar (one event per task, on its due date)."""
    memory.check_id(student_id)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kaagaz//caseworker//EN", "CALSCALE:GREGORIAN"]
    for t in memory.tasks(student_id):
        if t.get("status") != "open" or not t.get("due"):
            continue
        day = dt.date.fromisoformat(t["due"])
        text = (t.get("title") or "").replace(",", "\\,").replace(";", "\\;")
        lines += ["BEGIN:VEVENT", f"UID:{t['id']}@{student_id}.kaagaz", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{day:%Y%m%d}", f"DTEND;VALUE=DATE:{day + dt.timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{text}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="kaagaz-tasks.ics"'})


@app.post("/api/students/{student_id}/alerts/seen")
def alerts_seen(student_id: str) -> dict:
    memory.check_id(student_id)
    return {"marked": memory.alerts_seen(student_id)}


# ---- agents: watcher, reviewer, shared memory ------------------------------------------------------------------

_watch_lock = threading.Lock()


@app.get("/api/agents")
def agents_state(pack: str | None = None) -> dict:
    pid = _pack_param(pack)
    recent = agents.runs(None, 15)
    return {"agents": agents.overview(), "runs": recent,
            "running": any(r.get("status") == "running" and r.get("agent") == "watcher" for r in recent),
            "findings": agents.findings(pid, None, 100), "graph": agents.AGENTS_GRAPH}


@app.get("/api/agents/runs/{run_id}")
def agent_run(run_id: str) -> dict:
    d = agents.run_detail(run_id)
    if d is None:
        raise HTTPException(404, "no such run")
    return d


class WatchBody(BaseModel):
    only: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=200)


@app.post("/api/agents/watcher/run")
def start_watch(body: WatchBody | None = None, pack: str | None = None) -> dict:
    """Start a watcher run in the background (it fetches politely, so a full run takes a few minutes)."""
    pid = _pack_param(pack)
    if not _watch_lock.acquire(blocking=False):
        raise HTTPException(409, "the watcher is already running")

    def go() -> None:
        try:
            watcher.run_watch(pid, body.only if body else None, body.limit if body else None, trigger="ui")
        except Exception:  # recorded on the run as failed
            log.exception("watcher run failed")
        finally:
            _watch_lock.release()

    threading.Thread(target=go, daemon=True).start()
    return {"started": True}


@app.post("/api/agents/findings/{finding_id}")
def decide_finding(finding_id: str, body: DecideBody) -> dict:
    """The reviewer (a person) approves or rejects what the watcher found. Approval changes the rules graph and the
    caseworker re-plans every student the change affects."""
    try:
        return watcher.decide(finding_id, body.approve, body.note or "")
    except KeyError:
        raise HTTPException(404, "no such finding") from None


# ---- benchmark ---------------------------------------------------------------------

@app.get("/api/benchmark")
def benchmark() -> dict:
    files = sorted(BENCH_RESULTS.glob("*.json"))
    # model-trial-* files are latency trials for choosing a model, not benchmark runs
    llm_runs = [f for f in files if not f.name.startswith(("deterministic-", "model-trial-"))]
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

    DIST_ROOT = FRONTEND_DIST.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = (FRONTEND_DIST / path).resolve()
        # only files inside the built frontend; "../" or absolute paths never leave it
        if path and f.is_relative_to(DIST_ROOT) and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST_ROOT / "index.html")
