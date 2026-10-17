"""Critical path planner.

Works on the sub-graph that prerequisites.cypher returns for one scheme at one depth:
nodes (Scheme, Document, AnyOf) and REQUIRES / OPTION edges. Pure Python, no database access,
so the maths can be unit tested on its own and checked against chain_days.cypher.

finish(doc)   = 0 if held, else days(doc) + max(finish(child)) over its REQUIRES children
finish(anyof) = 0 if any option is held, else min(finish(option))
finish(scheme)= max(finish(child))

Unknown processing days (null) never become a guess: they count as 0 in a lower bound and the
result is marked inexact, with the unknown documents listed.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

MAX_DEPTH = 8


@dataclass(frozen=True)
class Node:
    id: str
    label: Literal["Scheme", "Document", "AnyOf"]
    name: str
    days: int | None = None
    props: dict = field(default_factory=dict, compare=False, hash=False)
    # unit of `days` when it differs from the unit the pack counts in ("working_days" / "calendar_days"); None = same
    days_unit: str | None = None


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    type: Literal["REQUIRES", "OPTION"]
    props: dict = field(default_factory=dict, compare=False, hash=False)


@dataclass
class RuleGraph:
    root: str
    nodes: dict[str, Node]
    edges: list[Edge]
    # documents at the depth limit that have prerequisites the query did not return
    cut: set[str] = field(default_factory=set)

    def children(self, nid: str) -> list[Edge]:
        return [e for e in self.edges if e.src == nid]


@dataclass(frozen=True)
class Finish:
    lb: int          # days, exact value when exact is True, else a lower bound
    exact: bool


ZERO = Finish(0, True)


class CycleError(ValueError):
    pass


# convert(from_unit, start, days) -> the same duration in the pack's unit, for a step starting `start` pack-units
# from today. Returns None when it cannot be converted exactly (then the planner keeps a safe lower bound).
Converter = Callable[[str, int, int], int | None]


class Planner:
    def __init__(self, graph: RuleGraph, held: set[str] | frozenset[str], unit: str | None = None,
                 convert: Converter | None = None, applies: set[str] | frozenset[str] | None = None):
        self.g = graph
        self.held = set(held)
        # a REQUIRES edge with a condition ("only if the student has a disability") counts only when the student
        # has said it applies to them (its target document id is in `applies`)
        self.applies = set(applies or ())
        self.unit = unit
        self.convert = convert
        self._memo: dict[str, Finish] = {}
        self._choice: dict[str, str | None] = {}   # AnyOf id -> chosen option id (None if satisfied)
        self._via: dict[str, str | None] = {}      # node id -> child id that sets its finish
        self._stack: set[str] = set()
        self._kids: dict[str, list[Edge]] = {}
        for e in graph.edges:
            if e.type == "REQUIRES" and e.props.get("condition") and e.dst not in self.applies:
                continue
            self._kids.setdefault(e.src, []).append(e)

    # ---- core recursion -------------------------------------------------
    def finish(self, nid: str) -> Finish:
        if nid in self._memo:
            return self._memo[nid]
        if nid in self._stack:
            raise CycleError(f"cycle through {nid}")
        self._stack.add(nid)
        node = self.g.nodes[nid]
        kids = self._kids.get(nid, [])
        if node.label == "AnyOf":
            res = self._anyof(nid, kids)
        elif node.label == "Document" and nid in self.held:
            self._via[nid] = None
            res = ZERO
        else:
            best = self._max_children(nid, [e for e in kids if e.type == "REQUIRES"])
            if node.label == "Document":
                days, exact_days = self._days(node, best.lb)
                res = Finish((days or 0) + best.lb, best.exact and days is not None and exact_days)
            else:
                res = best
        self._stack.discard(nid)
        self._memo[nid] = res
        return res

    def _days(self, node: Node, start: int) -> tuple[int | None, bool]:
        """The document's legal time in the pack's unit, and whether that number is exact."""
        if node.days is None or not node.days_unit or not self.unit or node.days_unit == self.unit:
            return node.days, True
        if self.convert is not None:
            converted = self.convert(node.days_unit, start, node.days)
            if converted is not None:
                return converted, True
        if node.days_unit == "working_days" and self.unit == "calendar_days":
            return node.days, False  # N working days take at least N calendar days: a safe lower bound
        return 0, False  # no safe bound without a calendar: count nothing, mark unknown

    def _max_children(self, nid: str, kids: list[Edge]) -> Finish:
        best, via, exact = 0, None, True
        for e in kids:
            f = self.finish(e.dst)
            exact = exact and f.exact
            # strict > keeps the first child on ties; prefer an inexact child on a tie (it may be longer)
            if via is None or f.lb > best or (f.lb == best and not f.exact and self._memo[via].exact):
                best, via = f.lb, e.dst
        self._via[nid] = via
        return Finish(best, exact)

    def _anyof(self, nid: str, kids: list[Edge]) -> Finish:
        options = [e.dst for e in kids if e.type == "OPTION"]
        if any(o in self.held for o in options):
            self._choice[nid] = None
            self._via[nid] = None
            return ZERO
        if not options:
            self._choice[nid] = None
            self._via[nid] = None
            return Finish(0, False)
        scored = [(self.finish(o), o) for o in options]
        # fastest option: smallest bound, then exact before inexact, then id for a stable order
        scored.sort(key=lambda t: (t[0].lb, not t[0].exact, t[1]))
        f, chosen = scored[0]
        exact = f.exact and all(other.lb >= f.lb for other, _ in scored[1:])
        self._choice[nid] = chosen
        self._via[nid] = chosen
        return Finish(f.lb, exact)

    # ---- derived views --------------------------------------------------
    def satisfied(self, nid: str) -> bool:
        node = self.g.nodes[nid]
        if node.label == "Document":
            return nid in self.held
        if node.label == "AnyOf":
            return any(e.dst in self.held for e in self._kids.get(nid, []) if e.type == "OPTION")
        return False

    def critical_path(self) -> list[str]:
        self.finish(self.g.root)
        path, cur = [self.g.root], self._via.get(self.g.root)
        while cur is not None:
            path.append(cur)
            cur = self._via.get(cur)
        return path

    def needed(self) -> list[str]:
        """Documents still to obtain, following the chosen option inside each AnyOf."""
        self.finish(self.g.root)
        out: list[str] = []
        seen: set[str] = set()

        def walk(nid: str) -> None:
            if nid in seen:
                return
            seen.add(nid)
            node = self.g.nodes[nid]
            if node.label == "Document":
                if nid in self.held:
                    return
                out.append(nid)
            if node.label == "AnyOf":
                ch = self._choice.get(nid)
                if ch:
                    walk(ch)
                return
            for e in self._kids.get(nid, []):
                if e.type == "REQUIRES":
                    walk(e.dst)

        walk(self.g.root)
        return out

    def start_of(self, nid: str) -> Finish:
        """Earliest day this document's application can start (its prerequisites done)."""
        self.finish(nid)
        kids = [e for e in self._kids.get(nid, []) if e.type == "REQUIRES"]
        best, exact = 0, True
        for e in kids:
            f = self.finish(e.dst)
            best = max(best, f.lb)
            exact = exact and f.exact
        return Finish(best, exact)

    def ready_now(self) -> list[str]:
        """Needed documents whose prerequisites are all already held."""
        out = []
        for nid in self.needed():
            kids = [e for e in self._kids.get(nid, []) if e.type == "REQUIRES"]
            if all(self.satisfied(e.dst) for e in kids):
                out.append(nid)
        return out

    def unknown_needed(self) -> list[str]:
        return [n for n in self.needed() if self.g.nodes[n].days is None]


# ---- verdict ----------------------------------------------------------------

VerdictKind = Literal["on_time", "late", "at_least", "late_at_least", "closed", "no_deadline", "cannot_compute"]


@dataclass
class Verdict:
    kind: VerdictKind
    critical_days: int
    exact: bool
    days_left: int | None
    margin: int | None  # spare days (>=0) or short days (>0) depending on kind
    stamp: str


def days_left(deadline: dt.date | None, today: dt.date) -> int | None:
    if deadline is None:
        return None
    return (deadline - today).days


def verdict(f: Finish, left: int | None) -> Verdict:
    if left is None:
        return Verdict("no_deadline", f.lb, f.exact, None, None,
                       f"{f.lb} DAYS NEEDED" if f.exact else f"AT LEAST {f.lb} DAYS")
    if left < 0:
        return Verdict("closed", f.lb, f.exact, left, None, "WINDOW CLOSED")
    if f.exact:
        if f.lb > left:
            return Verdict("late", f.lb, True, left, f.lb - left, f"{f.lb - left} {_d(f.lb - left)} SHORT")
        return Verdict("on_time", f.lb, True, left, left - f.lb,
                       f"ON TIME · {left - f.lb} {_d(left - f.lb)} SPARE")
    if f.lb > left:
        return Verdict("late_at_least", f.lb, False, left, f.lb - left,
                       f"AT LEAST {f.lb - left} {_d(f.lb - left)} SHORT")
    if f.lb == 0:
        return Verdict("cannot_compute", 0, False, left, None, "CAN'T BE COMPUTED")
    return Verdict("at_least", f.lb, False, left, None, f"AT LEAST {f.lb} {_d(f.lb)}")


def _d(n: int) -> str:
    return "DAY" if n == 1 else "DAYS"


def reduction_if_held(graph: RuleGraph, held: set[str], doc: str, **kw) -> int:
    """How many days the critical path would drop if this document were already in hand."""
    base = Planner(graph, held, **kw).finish(graph.root).lb
    after = Planner(graph, set(held) | {doc}, **kw).finish(graph.root).lb
    return base - after
