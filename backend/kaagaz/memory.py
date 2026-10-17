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


def set_target(student_id: str, scheme_id: str, deadline: str | None, deadline_source: str, trace=None) -> dict:
    r = graph.run(_g(student_id), "target_set",
                  {"student_id": student_id, "scheme_id": scheme_id, "deadline": deadline,
                   "deadline_source": deadline_source, "now": now_iso()}, read_only=False)
    _t(trace, r)
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


def _t(trace, run) -> None:
    if trace is not None:
        trace.query(run)
