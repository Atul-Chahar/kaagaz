"""The fixed tool catalogue. These are the only things the agent (or the UI) can call.

Every tool:
- validates its arguments with pydantic,
- checks names against the graph (resolve_name.cypher) before any other query runs,
- returns a ToolResult with one of five outcomes and a trace row per tool call and per query.
"""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, StringConstraints, ValidationError, field_validator

from . import graph, memory
from .planner import MAX_DEPTH, Edge, Node, Planner, RuleGraph, reduction_if_held, verdict
from .workdays import WorkCalendar

Outcome = Literal["answered_with_path", "answered_from_memory", "not_in_graph", "unknown_name", "no_official_time"]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,80}$")]
StudentId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]

DEFAULT_PACK = "in-ka-scholarships"


# ---- trace -------------------------------------------------------------------

@dataclass
class Trace:
    rows: list[dict] = field(default_factory=list)

    def query(self, run: graph.QueryRun) -> None:
        self.rows.append({"kind": "query", "tool": f"query:{run.name}", "graph": run.graph,
                          "args": _short(run.params), "ms": run.ms, "rows": len(run.rows)})

    def tool(self, name: str, args: dict, ms: float, rows: int, outcome: str) -> None:
        self.rows.append({"kind": "tool", "tool": name, "args": args, "ms": round(ms, 2), "rows": rows,
                          "outcome": outcome})


def _short(params: dict) -> dict:
    out = {}
    for k, v in params.items():
        if k == "rows":
            out[k] = f"<{len(v)} rows>"
        elif isinstance(v, list) and len(v) > 12:
            out[k] = v[:12] + [f"... {len(v) - 12} more"]
        else:
            out[k] = v
    return out


@dataclass
class ToolResult:
    tool: str
    outcome: Outcome
    data: dict
    trace: list[dict]
    message: str = ""

    def as_dict(self) -> dict:
        return {"tool": self.tool, "outcome": self.outcome, "message": self.message, "data": self.data,
                "trace": self.trace}


class ToolError(ValueError):
    pass


# ---- argument models -------------------------------------------------------------

class ResolveArgs(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=200, strip_whitespace=True)]


class PrerequisitesArgs(BaseModel):
    scheme_id: Id
    depth: int = Field(default=MAX_DEPTH, ge=1, le=MAX_DEPTH)


class PlanArgs(BaseModel):
    student_id: StudentId
    scheme_id: Id
    depth: int = Field(default=MAX_DEPTH, ge=1, le=MAX_DEPTH)
    remember: bool = Field(default=True, description="Save this plan to the student's memory.")


class ExplainArgs(BaseModel):
    scheme_id: Id
    doc_id: Id


class AlternativesArgs(BaseModel):
    student_id: StudentId
    scheme_id: Id


class RememberHoldingArgs(BaseModel):
    student_id: StudentId
    doc_id: Id
    issued_on: dt.date | None = None

    @field_validator("issued_on")
    @classmethod
    def not_future(cls, v: dt.date | None) -> dt.date | None:
        if v is not None and v > dt.date.today() + dt.timedelta(days=1):
            raise ValueError("issued_on cannot be in the future")
        return v


class RecallArgs(BaseModel):
    student_id: StudentId


ARG_MODELS: dict[str, type[BaseModel]] = {
    "resolve": ResolveArgs,
    "prerequisites": PrerequisitesArgs,
    "plan": PlanArgs,
    "explain": ExplainArgs,
    "alternatives": AlternativesArgs,
    "remember_holding": RememberHoldingArgs,
    "recall": RecallArgs,
}

TOOL_DESCRIPTIONS = {
    "resolve": "Look up a scheme or document by id or exact name (case-insensitive).",
    "prerequisites": "Every document a scheme needs, including documents needed to get them, up to a depth (1 to 8).",
    "plan": "The student's plan for one scheme: critical path, verdict against the deadline, what to apply for today.",
    "explain": "Why a scheme needs a document: the path through the requirement graph, with sources.",
    "alternatives": "Other schemes the student can still make that reuse the documents they need.",
    "remember_holding": "Save that the student now holds a document (optionally with the date it was issued).",
    "recall": "What Kaagaz remembers about the student: holdings, targets and past plans, with dates.",
}


# ---- the catalogue -----------------------------------------------------------------

class Tools:
    def __init__(self, pack_id: str = DEFAULT_PACK, today: dt.date | None = None):
        self.pack_id = pack_id
        self.rules = graph.rules_graph_name(pack_id)
        self.pack = graph.load_pack(pack_id)
        self.tz = ZoneInfo(self.pack["pack"].get("timezone", "UTC"))
        self._today = today
        self.calendar = WorkCalendar.from_pack(self.pack)
        self.pack_unit = "working_days" if self.calendar.working else "calendar_days"

    def planner(self, g: RuleGraph, held: set[str], applies: set[str] | None = None) -> Planner:
        return Planner(g, held, unit=self.pack_unit, convert=self._convert, applies=applies)

    def _convert(self, from_unit: str, start: int, days: int) -> int | None:
        if from_unit == "calendar_days" and self.pack_unit == "working_days":
            return self.calendar.calendar_to_working(self.today(), start, days)
        return None

    def today(self) -> dt.date:
        return self._today or dt.datetime.now(self.tz).date()

    def call(self, name: str, args: dict, trace: Trace | None = None) -> ToolResult:
        if name not in ARG_MODELS:
            raise ToolError(f"unknown tool {name!r}; tools are: {', '.join(ARG_MODELS)}")
        try:
            parsed = ARG_MODELS[name](**(args or {}))
        except ValidationError as e:
            raise ToolError(f"bad arguments for {name}: {e.errors(include_url=False)}") from e
        trace = trace if trace is not None else Trace()
        t0 = time.perf_counter()
        result: ToolResult = getattr(self, f"_{name}")(parsed, trace)
        rows = result.data.get("_rows", 0)
        result.data.pop("_rows", None)
        trace.tool(name, parsed.model_dump(mode="json"), (time.perf_counter() - t0) * 1000, rows, result.outcome)
        result.trace = trace.rows
        return result

    # -- helpers --
    def _q(self, name: str, params: dict, trace: Trace) -> list[dict]:
        r = graph.run(self.rules, name, params)
        trace.query(r)
        return r.rows

    def _resolve_rows(self, name: str, trace: Trace) -> list[dict]:
        return self._q("resolve_name", {"q": name}, trace)

    def _need(self, ident: str, label: str, trace: Trace) -> dict | None:
        rows = [r for r in self._resolve_rows(ident, trace) if r["label"] == label]
        return rows[0] if rows else None

    def _unknown(self, tool: str, what: str, trace: Trace) -> ToolResult:
        return ToolResult(tool, "unknown_name", {"name": what, "_rows": 0}, trace.rows,
                          f"“{what}” is not a name in this rule pack, so no query was run.")

    # -- resolve --
    def _resolve(self, a: ResolveArgs, trace: Trace) -> ToolResult:
        rows = self._resolve_rows(a.name, trace)
        if not rows:
            return self._unknown("resolve", a.name, trace)
        return ToolResult("resolve", "answered_with_path", {"matches": rows, "_rows": len(rows)}, trace.rows,
                          f"Found {rows[0]['name']}.")

    # -- prerequisites --
    def _prerequisites(self, a: PrerequisitesArgs, trace: Trace) -> ToolResult:
        scheme = self._need(a.scheme_id, "Scheme", trace)
        if scheme is None:
            return self._unknown("prerequisites", a.scheme_id, trace)
        rows = self._q("prerequisites", {"scheme_id": scheme["id"], "depth": a.depth}, trace)
        nodes = _dedupe_nodes(rows)
        docs = [n for n in nodes if n["label"] == "Document"]
        return ToolResult("prerequisites", "answered_with_path",
                          {"scheme": scheme, "depth": a.depth, "nodes": nodes, "_rows": len(rows)}, trace.rows,
                          f"{scheme['name']} needs {len(docs)} documents within {a.depth} steps.")

    # -- plan --
    def build_rule_graph(self, scheme_id: str, depth: int, trace: Trace) -> tuple[RuleGraph, list[dict], dict]:
        srows = self._q("schemes", {}, trace)
        scheme = next(r["scheme"] for r in srows if r["scheme"]["id"] == scheme_id)
        rows = self._q("prerequisites", {"scheme_id": scheme_id, "depth": depth}, trace)
        nodes = {scheme_id: Node(scheme_id, "Scheme", scheme["name"], None, dict(scheme))}
        edges: dict[tuple, Edge] = {}
        cut: set[str] = set()
        for r in rows:
            if r["id"] not in nodes:
                nodes[r["id"]] = Node(r["id"], r["label"], r["name"], r["days"], dict(r["props"]),
                                      days_unit=(r["props"] or {}).get("days_unit"))
            src, dst, typ = r["path"][-2], r["path"][-1], r["hop_types"][-1]
            edges.setdefault((src, dst, typ), Edge(src, dst, typ, dict(r["hop"] or {})))
            if r["label"] == "Document" and r["depth"] == depth and r["out_requires"] > 0:
                cut.add(r["id"])
        return RuleGraph(scheme_id, nodes, list(edges.values()), cut), rows, scheme

    def _deadline(self, student_id: str, scheme: dict, trace: Trace) -> dict:
        tgt = next((t for t in memory.targets(student_id, trace) if t["scheme_id"] == scheme["id"]), None)
        if tgt and tgt.get("deadline"):
            return {"date": tgt["deadline"], "source": tgt.get("deadline_source") or "student"}
        if scheme.get("window_end") and scheme.get("window_renewals_only"):
            # the published window is for renewals only; the rules modelled are a fresh application's
            return {"date": None, "source": "renewals_only", "renewal_window_end": scheme["window_end"]}
        if scheme.get("window_end"):
            src = "last_published_window" if scheme.get("window_is_last_published") else "published_window"
            return {"date": scheme["window_end"], "source": src}
        return {"date": None, "source": "none"}

    def plan_core(self, student_id: str, scheme_id: str, depth: int, trace: Trace, held: set[str] | None = None,
                  save: bool = True, applies: set[str] | None = None) -> dict:
        g, rows, scheme = self.build_rule_graph(scheme_id, depth, trace)
        holdings = memory.holdings(student_id, trace) if held is None else [{"doc_id": h} for h in held]
        held_ids = {h["doc_id"] for h in holdings}
        if applies is None:
            applies = memory.applies(student_id, trace) if held is None else set()
        p = self.planner(g, held_ids, applies)
        fin = p.finish(scheme_id)
        dl = self._deadline(student_id, scheme, trace)
        deadline = dt.date.fromisoformat(dl["date"]) if dl["date"] else None
        left = self.calendar.days_between(self.today(), deadline) if deadline else None
        v = verdict(fin, left)
        crit = p.critical_path()
        crit_set = set(crit)
        needed = p.needed()
        # every node with its shortest path for the "why" chips
        first_row: dict[str, dict] = {}
        for r in rows:
            if r["id"] not in first_row or len(r["path"]) < len(first_row[r["id"]]["path"]):
                first_row[r["id"]] = r
        items = []
        for nid, r in first_row.items():
            n = g.nodes[nid]
            item = {"id": nid, "label": n.label, "name": n.name, "days": n.days, "depth": r["depth"],
                    "path": r["path"], "rule": r["hop"], "office_id": r["office_id"], "office_name": r["office_name"],
                    "held": nid in held_ids, "needed": nid in needed, "on_critical": nid in crit_set,
                    "days_source": _days_source(n.props), "note": n.props.get("note"),
                    "hidden_below": nid in g.cut}
            item["days_unit"] = n.days_unit or self.pack_unit
            if n.label == "Document" and nid in needed:
                st = p.start_of(nid)
                f = p.finish(nid)
                # span = this step's own length in the pack's unit (a calendar-day limit converted to working days)
                item.update({"start": st.lb, "end": f.lb, "exact": f.exact, "span": f.lb - st.lb})
            if n.label == "AnyOf":
                item["satisfied"] = p.satisfied(nid)
                item["chosen"] = p._choice.get(nid)
                item["options"] = [e.dst for e in g.edges if e.src == nid and e.type == "OPTION"]
            items.append(item)
        items.sort(key=lambda i: (i["depth"], i["label"] != "AnyOf", i["id"]))
        ready = p.ready_now()
        start_today = []
        for d in ready:
            n = g.nodes[d]
            start_today.append({"id": d, "name": n.name, "days": n.days, "days_unit": n.days_unit or self.pack_unit,
                                "span": p.finish(d).lb - p.start_of(d).lb,
                                "office_name": first_row[d]["office_name"] if d in first_row else None,
                                "reduction": reduction_if_held(g, held_ids, d, unit=self.pack_unit,
                                                               convert=self._convert, applies=applies),
                                "on_critical": d in crit_set,
                                "path": first_row[d]["path"] if d in first_row else [scheme_id, d]})
        start_today.sort(key=lambda s: (-s["reduction"], not s["on_critical"], -(s["days"] or 0), s["id"]))
        # graph cross-check: chain_days.cypher must agree with the planner on all-of chains
        allof = RuleGraph(scheme_id, {k: v for k, v in g.nodes.items() if v.label != "AnyOf"},
                          [e for e in g.edges if g.nodes[e.dst].label != "AnyOf" and g.nodes[e.src].label != "AnyOf"])
        chain_rows = self._q("chain_days", {"scheme_id": scheme_id, "held": sorted(held_ids), "depth": depth,
                                            "applies": sorted(applies), "limit": 5}, trace)
        chain_max = chain_rows[0]["days"] if chain_rows else 0
        # chain_days.cypher sums the raw legal numbers, so compare it with the planner on raw numbers (no unit change)
        planner_allof = Planner(allof, held_ids, applies=applies).finish(scheme_id).lb
        max_depth_rows = self._q("prerequisites", {"scheme_id": scheme_id, "depth": MAX_DEPTH}, trace)
        max_depth = max((r["depth"] for r in max_depth_rows), default=0)
        # fastest_option.cypher cross-checks the planner's choice inside every open "any one of" group (full depth
        # only, so both see the same graph; comparable when no other group sits under the options)
        option_checks = []
        if depth >= max_depth:
            raw = Planner(g, held_ids, applies=applies)
            anyofs = {k for k, v in g.nodes.items() if v.label == "AnyOf"}
            for aid in sorted(anyofs):
                if p.satisfied(aid) or p._choice.get(aid) is None or aid not in {i["id"] for i in items}:
                    continue
                rows_o = self._q("fastest_option", {"anyof_id": aid, "held": sorted(held_ids),
                                                    "applies": sorted(applies)}, trace)
                below, stack = set(), [e.dst for e in g.edges if e.src == aid]
                while stack:
                    n = stack.pop()
                    if n not in below:
                        below.add(n)
                        stack += [e.dst for e in g.edges if e.src == n]
                comparable = not (below & anyofs)
                cy = rows_o[0]["total_days"] if rows_o else None
                pl = raw.finish(aid).lb
                option_checks.append({"anyof_id": aid, "cypher_choice": rows_o[0]["doc_id"] if rows_o else None,
                                      "cypher_days": cy, "planner_choice": p._choice.get(aid), "planner_days": pl,
                                      "comparable": comparable, "agree": (cy == pl) if comparable else None})
        unknown = p.unknown_needed()
        result = {
            "scheme": scheme,
            "student_id": student_id,
            "depth": depth,
            "max_depth": max_depth,
            "today": self.today().isoformat(),
            "deadline": dl,
            "days_left": left,
            "day_unit": "working days" if self.calendar.working else "days",
            "calendar_complete": self.calendar.complete_until(deadline),
            "calendar_covers_until": self.calendar.covers_until.isoformat() if self.calendar.covers_until else None,
            "holidays_ahead": self.calendar.holidays_between(self.today(), deadline) if deadline else [],
            "dates": [self.calendar.date_of(self.today(), i).isoformat()
                      for i in range(max(fin.lb, left or 0) + 12)],
            "verdict": {"kind": v.kind, "stamp": v.stamp, "critical_days": v.critical_days, "exact": v.exact,
                        "margin": v.margin},
            "critical_path": crit,
            "needed": needed,
            "held": sorted(held_ids),
            "unknown": unknown,
            "hidden_more": bool(g.cut),
            "applies": sorted(applies),
            "conditional": [{"from": e.src, "doc_id": e.dst, "name": g.nodes[e.dst].name,
                             "condition": e.props.get("condition"), "applies": e.dst in applies,
                             "held": e.dst in held_ids}
                            for e in g.edges if e.type == "REQUIRES" and e.props.get("condition")],
            "items": items,
            "start_today": start_today,
            "option_checks": option_checks,
            "chain_check": {"chain_days_cypher": chain_max, "planner_all_of": planner_allof,
                            "agree": chain_max == planner_allof, "longest_chains": chain_rows},
        }
        if save:
            result["saved_at"] = memory.save_snapshot(
                student_id, scheme_id, v.kind, v.critical_days, v.exact,
                {"stamp": v.stamp, "depth": depth, "held": sorted(held_ids), "critical_path": crit}, trace)
        result["_rows"] = len(rows)
        return result

    def _plan(self, a: PlanArgs, trace: Trace) -> ToolResult:
        scheme = self._need(a.scheme_id, "Scheme", trace)
        if scheme is None:
            return self._unknown("plan", a.scheme_id, trace)
        memory.ensure_student(a.student_id, trace=trace)
        data = self.plan_core(a.student_id, scheme["id"], a.depth, trace, save=a.remember)
        outcome: Outcome = "answered_with_path" if data["verdict"]["exact"] else "no_official_time"
        msg = _plan_sentence(data)
        return ToolResult("plan", outcome, data, trace.rows, msg)

    # -- explain --
    def _explain(self, a: ExplainArgs, trace: Trace) -> ToolResult:
        scheme = self._need(a.scheme_id, "Scheme", trace)
        if scheme is None:
            return self._unknown("explain", a.scheme_id, trace)
        doc = self._need(a.doc_id, "Document", trace)
        if doc is None:
            return self._unknown("explain", a.doc_id, trace)
        rows = self._q("explain", {"scheme_id": scheme["id"], "doc_id": doc["id"]}, trace)
        detail = self._q("document_detail", {"doc_id": doc["id"]}, trace)
        d = detail[0] if detail else {}
        data = {"scheme": scheme, "doc": doc, "paths": rows, "detail": d, "_rows": len(rows)}
        if not rows:
            return ToolResult("explain", "not_in_graph", data, trace.rows,
                              f"Both names are in the graph, but no rule says {scheme['name']} needs "
                              f"{doc['name']}.")
        names = " → ".join(n["name"] for n in rows[0]["nodes"])
        days = (d.get("doc") or {}).get("days")
        if days is None:
            return ToolResult("explain", "no_official_time", data, trace.rows,
                              f"{names}. No official time limit found for {doc['name']}.")
        return ToolResult("explain", "answered_with_path", data, trace.rows,
                          f"{names}. {doc['name']} takes up to {days} days by law.")

    # -- alternatives --
    def _alternatives(self, a: AlternativesArgs, trace: Trace) -> ToolResult:
        scheme = self._need(a.scheme_id, "Scheme", trace)
        if scheme is None:
            return self._unknown("alternatives", a.scheme_id, trace)
        held = {h["doc_id"] for h in memory.holdings(a.student_id, trace)}
        applies = memory.applies(a.student_id, trace)
        base = self.plan_core(a.student_id, scheme["id"], MAX_DEPTH, trace, held=held, save=False, applies=applies)
        shared = self._q("shared_documents", {"scheme_id": scheme["id"], "needed": base["needed"]}, trace)
        shared_by = {r["scheme_id"]: r for r in shared}
        options = []
        for s in self._q("schemes", {}, trace):
            sid = s["scheme"]["id"]
            if sid == scheme["id"]:
                continue
            sub = self.plan_core(a.student_id, sid, MAX_DEPTH, Trace(), held=held, save=False, applies=applies)
            sh = shared_by.get(sid, {"shared": [], "shared_count": 0})
            options.append({"scheme_id": sid, "name": s["scheme"]["name"], "verdict": sub["verdict"],
                            "deadline": sub["deadline"], "days_left": sub["days_left"],
                            "shared": sh["shared"], "shared_count": sh["shared_count"],
                            "needed_count": len(sub["needed"])})

        # can make it, then might make it (lower bound only), then no deadline, then short, then closed
        order = {"on_time": 0, "at_least": 1, "cannot_compute": 2, "no_deadline": 2, "late_at_least": 3, "late": 3,
                 "closed": 4}

        def rank(o: dict) -> tuple:
            v = o["verdict"]
            spare = -(v["margin"] or 0) if v["kind"] == "on_time" else (v["margin"] or 0)
            return (order[v["kind"]], spare, -o["shared_count"], o["scheme_id"])

        options.sort(key=rank)
        can = [o for o in options if o["verdict"]["kind"] == "on_time"]
        msg = (f"{len(can)} other scheme{'s' if len(can) != 1 else ''} can still be made with your documents."
               if options else "There are no other schemes in this pack.")
        return ToolResult("alternatives", "answered_with_path",
                          {"scheme": scheme, "options": options, "_rows": len(shared)}, trace.rows, msg)

    # -- memory --
    def _remember_holding(self, a: RememberHoldingArgs, trace: Trace) -> ToolResult:
        doc = self._need(a.doc_id, "Document", trace)
        if doc is None:
            return self._unknown("remember_holding", a.doc_id, trace)
        memory.ensure_student(a.student_id, trace=trace)
        row = memory.add_holding(a.student_id, doc["id"], a.issued_on.isoformat() if a.issued_on else None, trace)
        return ToolResult("remember_holding", "answered_from_memory", {"holding": row, "doc": doc, "_rows": 1},
                          trace.rows, f"Saved: you hold {doc['name']} (saved {row['added_at'][:10]}).")

    def _recall(self, a: RecallArgs, trace: Trace) -> ToolResult:
        st = memory.get_student(a.student_id, trace)
        if st is None:
            return ToolResult("recall", "not_in_graph", {"student": None, "_rows": 0}, trace.rows,
                              "Kaagaz has no saved memory for this student yet.")
        hs = memory.holdings(a.student_id, trace)
        ts = memory.targets(a.student_id, trace)
        sn = memory.snapshots(a.student_id, 5, trace)
        names = {d["id"]: d["name"] for d in self.pack["documents"]}
        for h in hs:
            h["name"] = names.get(h["doc_id"], h["doc_id"])
        last = sn[0]["at"][:10] if sn else st["created_at"][:10]
        return ToolResult("recall", "answered_from_memory",
                          {"student": st, "holdings": hs, "targets": ts, "snapshots": sn, "_rows": len(hs) + len(ts)},
                          trace.rows, f"Saved memory from {last}: {len(hs)} documents held, {len(ts)} target scheme(s).")


# ---- helpers -----------------------------------------------------------------------

def _dedupe_nodes(rows: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in rows:
        if r["id"] not in seen or r["depth"] < seen[r["id"]]["depth"]:
            seen[r["id"]] = {"id": r["id"], "label": r["label"], "name": r["name"], "days": r["days"],
                             "depth": r["depth"], "path": r["path"], "rule": r["hop"],
                             "office_name": r["office_name"]}
    return sorted(seen.values(), key=lambda n: (n["depth"], n["id"]))


def _days_source(props: dict) -> dict | None:
    if not props.get("days_source_url"):
        return None
    return {k: props.get(f"days_{k}") for k in ("source_url", "source_title", "retrieved_at", "excerpt", "confidence")}


def _plan_sentence(d: dict) -> str:
    v = d["verdict"]
    name = d["scheme"]["name"]
    if v["kind"] == "on_time":
        return f"{name}: on time, with {v['margin']} days spare."
    if v["kind"] == "late":
        return f"{name}: {v['margin']} days short of the deadline."
    if v["kind"] == "late_at_least":
        return f"{name}: at least {v['margin']} days short, and some steps have no official time limit."
    if v["kind"] == "at_least":
        return f"{name}: needs at least {v['critical_days']} days; some steps have no official time limit."
    if v["kind"] == "closed":
        return f"{name}: the application window has closed."
    if v["kind"] == "no_deadline":
        return f"{name}: no deadline is published; the chain needs {v['critical_days']} days."
    return f"{name}: the time needed can't be computed, because no official time limits were found."


def catalogue() -> list[dict]:
    """JSON-schema description of every tool, for the LLM layer and the MCP server."""
    out = []
    for name, model in ARG_MODELS.items():
        out.append({"name": name, "description": TOOL_DESCRIPTIONS[name], "parameters": model.model_json_schema()})
    return out


def as_jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: as_jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [as_jsonable(v) for v in x]
    return x
