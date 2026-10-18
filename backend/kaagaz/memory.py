"""Per-student memory. Each student is a separate FalkorDB graph: kaagaz:student:<student-id>.

One Cypher query runs on one graph, so a query on one student's graph can never read another student's
holdings. The planner reads holdings here and passes the held document ids as a parameter into the rules graph.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from . import graph

STUDENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
EXAMPLE_LABEL = "Example student"


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def check_id(student_id: str) -> str:
    if not STUDENT_ID.match(student_id or ""):
        raise ValueError("student_id must be 3 to 64 characters: lowercase letters, digits and dashes")
    return student_id


def _g(student_id: str) -> str:
    return graph.student_graph_name(check_id(student_id))


def ensure_student(student_id: str, label: str = "Student", trace=None) -> dict:
    r = graph.run(_g(student_id), "student_init", {"student_id": student_id, "label": label, "now": now_iso()},
                  read_only=False)
    _t(trace, r)
    return r.rows[0]


def exists(student_id: str) -> bool:
    return graph.graph_exists(_g(student_id))


def get_student(student_id: str, trace=None) -> dict | None:
    if not exists(student_id):
        return None
    r = graph.run(_g(student_id), "student_get", {"student_id": student_id})
    _t(trace, r)
    return r.rows[0] if r.rows else None


def add_holding(student_id: str, doc_id: str, issued_on: str | None, trace=None) -> dict:
    r = graph.run(_g(student_id), "holding_add",
                  {"student_id": student_id, "doc_id": doc_id, "issued_on": issued_on, "now": now_iso()},
                  read_only=False)
    _t(trace, r)
    return r.rows[0]


def remove_holding(student_id: str, doc_id: str, trace=None) -> int:
    r = graph.run(_g(student_id), "holding_remove", {"student_id": student_id, "doc_id": doc_id}, read_only=False)
    _t(trace, r)
    return r.rows[0]["removed"] if r.rows else 0


def add_applies(student_id: str, doc_id: str, trace=None) -> dict:
    r = graph.run(_g(student_id), "applies_add", {"student_id": student_id, "doc_id": doc_id, "now": now_iso()},
                  read_only=False)
    _t(trace, r)
    return r.rows[0]


def remove_applies(student_id: str, doc_id: str, trace=None) -> int:
    r = graph.run(_g(student_id), "applies_remove", {"student_id": student_id, "doc_id": doc_id}, read_only=False)
    _t(trace, r)
    return r.rows[0]["removed"] if r.rows else 0


def applies(student_id: str, trace=None) -> set[str]:
    if not exists(student_id):
        return set()
    r = graph.run(_g(student_id), "recall_applies", {"student_id": student_id})
    _t(trace, r)
    return {row["doc_id"] for row in r.rows}


def add_application(student_id: str, doc_id: str, applied_on: str, trace=None) -> dict:
    r = graph.run(_g(student_id), "application_add", {"student_id": student_id, "doc_id": doc_id,
                                                      "applied_on": applied_on, "now": now_iso()}, read_only=False)
    _t(trace, r)
    return r.rows[0]


def remove_application(student_id: str, doc_id: str, trace=None) -> int:
    r = graph.run(_g(student_id), "application_remove", {"student_id": student_id, "doc_id": doc_id},
                  read_only=False)
    _t(trace, r)
    return r.rows[0]["removed"] if r.rows else 0


def applications(student_id: str, trace=None) -> list[dict]:
    if not exists(student_id):
        return []
    r = graph.run(_g(student_id), "recall_applications", {"student_id": student_id})
    _t(trace, r)
    return r.rows


def set_target(student_id: str, scheme_id: str, deadline: str | None, deadline_source: str, trace=None,
               pack: str | None = None) -> dict:
    r = graph.run(_g(student_id), "target_set",
                  {"student_id": student_id, "scheme_id": scheme_id, "deadline": deadline,
                   "deadline_source": deadline_source, "now": now_iso()}, read_only=False)
    _t(trace, r)
    if pack:
        # the shared registry lets the caseworker find this student when a rule for this scheme changes
        from . import agents
        agents.register_target(student_id, pack, scheme_id, trace)
    return r.rows[0]


def holdings(student_id: str, trace=None) -> list[dict]:
    if not exists(student_id):
        return []
    r = graph.run(_g(student_id), "recall_holdings", {"student_id": student_id})
    _t(trace, r)
    return r.rows


def targets(student_id: str, trace=None) -> list[dict]:
    if not exists(student_id):
        return []
    r = graph.run(_g(student_id), "recall_targets", {"student_id": student_id})
    _t(trace, r)
    return r.rows


def snapshots(student_id: str, limit: int = 10, trace=None) -> list[dict]:
    if not exists(student_id):
        return []
    r = graph.run(_g(student_id), "recall_snapshots", {"student_id": student_id, "limit": limit})
    _t(trace, r)
    return r.rows


def last_snapshot(student_id: str, scheme_id: str, trace=None) -> dict | None:
    if not exists(student_id):
        return None
    r = graph.run(_g(student_id), "snapshot_last", {"student_id": student_id, "scheme_id": scheme_id})
    _t(trace, r)
    if not r.rows:
        return None
    row = dict(r.rows[0])
    row["json"] = json.loads(row["json"]) if row.get("json") else {}
    return row


def save_snapshot(student_id: str, scheme_id: str, verdict: str, critical_days: int, exact: bool, summary: dict,
                  trace=None) -> str:
    r = graph.run(_g(student_id), "snapshot_add",
                  {"student_id": student_id, "scheme_id": scheme_id, "verdict": verdict,
                   "critical_days": critical_days, "exact": exact, "json": json.dumps(summary), "now": now_iso()},
                  read_only=False)
    _t(trace, r)
    return r.rows[0]["at"]


def reset(student_id: str) -> None:
    graph.delete_graph(_g(student_id))
    from . import agents
    agents.forget_student(student_id)


# ---- what the agents leave in a student's own graph ----------------------------------------------------------

def _rows(student_id: str, name: str, params: dict, write: bool = False, trace=None) -> list[dict]:
    if not write and not exists(student_id):
        return []
    r = graph.run(_g(student_id), name, {"student_id": student_id} | params, read_only=not write)
    _t(trace, r)
    return r.rows


def add_alert(student_id: str, alert: dict, trace=None) -> None:
    _rows(student_id, "alert_add", {"now": now_iso(), **alert}, write=True, trace=trace)


def alerts(student_id: str, limit: int = 20, trace=None) -> list[dict]:
    return [dict(r["alert"]) for r in _rows(student_id, "recall_alerts", {"limit": limit}, trace=trace)]


def alerts_seen(student_id: str, trace=None) -> int:
    rows = _rows(student_id, "alerts_seen", {}, write=True, trace=trace)
    return rows[0]["n"] if rows else 0


def add_case(student_id: str, case: dict, trace=None) -> None:
    _rows(student_id, "case_add", {"now": now_iso(), **case}, write=True, trace=trace)


def cases(student_id: str, limit: int = 5, trace=None) -> list[dict]:
    out = []
    for r in _rows(student_id, "recall_cases", {"limit": limit}, trace=trace):
        c = dict(r["review"])
        c["json"] = json.loads(c["json"]) if c.get("json") else {}
        out.append(c)
    return out


def add_proposals(student_id: str, case_id: str, rows: list[dict], trace=None) -> None:
    _rows(student_id, "proposals_expire", {"case_id": case_id, "now": now_iso()}, write=True, trace=trace)
    if rows:
        _rows(student_id, "proposal_add", {"case_id": case_id, "rows": rows, "now": now_iso()}, write=True,
              trace=trace)


def proposals(student_id: str, limit: int = 30, trace=None) -> list[dict]:
    return [dict(r["proposal"]) | {"case_id": r["case_id"]}
            for r in _rows(student_id, "recall_proposals", {"limit": limit}, trace=trace)]


def decide_proposal(student_id: str, proposal_id: str, status: str, trace=None) -> dict | None:
    rows = _rows(student_id, "proposal_decide", {"id": proposal_id, "status": status, "now": now_iso()}, write=True,
                 trace=trace)
    return dict(rows[0]["proposal"]) if rows else None


def add_task(student_id: str, task: dict, trace=None) -> dict:
    rows = _rows(student_id, "task_add", {"now": now_iso(), **task}, write=True, trace=trace)
    return dict(rows[0]["task"])


def tasks(student_id: str, trace=None) -> list[dict]:
    return [dict(r["task"]) for r in _rows(student_id, "recall_tasks", {}, trace=trace)]


def task_status(student_id: str, task_id: str, status: str, trace=None) -> dict | None:
    rows = _rows(student_id, "task_status", {"id": task_id, "status": status, "now": now_iso()}, write=True,
                 trace=trace)
    return dict(rows[0]["task"]) if rows else None


def _t(trace, run) -> None:
    if trace is not None:
        trace.query(run)
