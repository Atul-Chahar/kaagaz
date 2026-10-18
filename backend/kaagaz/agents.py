"""The shared agents graph, kaagaz:agents: how Kaagaz's agents remember their work and coordinate.

Three agents share it:
- Watcher: re-fetches the government sources, re-checks every rule's proof sentence, records SourceChecks and
  Findings, and links each Finding to the schemes it affects.
- Reviewer: a person. Approves or rejects a Finding; nothing in the rules changes without that.
- Caseworker: after an approval, finds the students who target an affected scheme (through the registry), re-plans
  each one and leaves an Alert in that student's own graph. It also reviews one student's case on request.

The registry (StudentRef)-[:TARGETS]->(SchemeRef) holds only ids. Holdings and plans stay in each student's graph.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import secrets

from . import graph

AGENTS_GRAPH = os.environ.get("KAAGAZ_AGENTS_GRAPH", "kaagaz:agents")
AGENTS = {
    "watcher": ("Watcher", "Re-fetches the saved government sources and re-checks every rule's proof sentence"),
    "reviewer": ("Reviewer (a person)", "Approves or rejects what the watcher found; rules change only after this"),
    "caseworker": ("Caseworker", "Reviews a student's case, proposes actions, and re-plans students a change affects"),
}


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{dt.datetime.now(dt.UTC).strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"


def q(name: str, params: dict | None = None, write: bool = False, trace=None) -> list[dict]:
    r = graph.run(AGENTS_GRAPH, name, params or {}, read_only=not write)
    if trace is not None:
        trace.query(r)
    return r.rows


def ensure(trace=None) -> None:
    for aid, (name, role) in AGENTS.items():
        q("agents_init", {"id": aid, "name": name, "role": role, "now": now_iso()}, write=True, trace=trace)


def start_run(agent: str, pack: str, trigger: str, trace=None) -> str:
    ensure(trace)
    rid = new_id(agent)
    q("agents_run_start", {"agent": agent, "run_id": rid, "pack": pack, "now": now_iso(), "trigger": trigger},
      write=True, trace=trace)
    return rid


def finish_run(run_id: str, status: str, summary: dict, trace=None) -> dict:
    return q("agents_run_finish", {"run_id": run_id, "now": now_iso(), "status": status,
                                   "summary": json.dumps(summary)}, write=True, trace=trace)[0]["run"]


def register_target(student_id: str, pack: str, scheme_id: str, trace=None) -> None:
    q("agents_registry_target", {"student_id": student_id, "pack": pack, "scheme_id": scheme_id, "now": now_iso()},
      write=True, trace=trace)


def forget_student(student_id: str) -> None:
    if graph.graph_exists(AGENTS_GRAPH):
        q("agents_registry_forget", {"student_id": student_id}, write=True)


def findings(pack: str, status: str | None = None, limit: int = 50) -> list[dict]:
    if not graph.graph_exists(AGENTS_GRAPH):
        return []
    out = []
    for r in q("agents_findings", {"pack": pack, "status": status, "limit": limit}):
        f = dict(r["finding"])
        f["schemes"] = r["schemes"]
        f["students"] = r["students"]
        out.append(f)
    return out


def finding(fid: str) -> dict | None:
    if not graph.graph_exists(AGENTS_GRAPH):
        return None
    rows = q("agents_finding_get", {"id": fid})
    if not rows or rows[0]["finding"] is None:
        return None
    return dict(rows[0]["finding"]) | {"schemes": rows[0]["schemes"]}


def runs(agent: str | None = None, limit: int = 20) -> list[dict]:
    if not graph.graph_exists(AGENTS_GRAPH):
        return []
    out = []
    for r in q("agents_runs", {"agent": agent, "limit": limit}):
        run = dict(r["run"])
        run["summary"] = json.loads(run["summary"]) if run.get("summary") else None
        out.append(run)
    return out


def run_detail(run_id: str) -> dict | None:
    if not graph.graph_exists(AGENTS_GRAPH):
        return None
    rows = q("agents_run_get", {"run_id": run_id})
    if not rows or rows[0]["run"] is None:
        return None
    run = dict(rows[0]["run"])
    run["summary"] = json.loads(run["summary"]) if run.get("summary") else None
    checks = sorted((dict(c) for c in rows[0]["checks"]), key=lambda c: c.get("source_id", ""))
    return {"run": run, "checks": checks, "findings": rows[0]["findings"]}


def overview() -> list[dict]:
    ensure()
    return q("agents_overview")
