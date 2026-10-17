"""Planner maths on small hand-built graphs (test fixtures only, not product data)."""

import datetime as dt

import pytest

from kaagaz.planner import (
    CycleError,
    Edge,
    Finish,
    Node,
    Planner,
    RuleGraph,
    days_left,
    reduction_if_held,
    verdict,
)


def doc(i, days):
    return Node(i, "Document", i.upper(), days)


def graph(nodes, edges, root="S"):
    ns = {"S": Node("S", "Scheme", "Scheme")}
    ns.update({n.id: n for n in nodes})
    return RuleGraph(root, ns, [Edge(a, b, t) for a, b, t in edges])


# S -> A(10) -> B(5) -> C(20) ; S -> D(30)
CHAIN = graph(
    [doc("A", 10), doc("B", 5), doc("C", 20), doc("D", 30)],
    [("S", "A", "REQUIRES"), ("A", "B", "REQUIRES"), ("B", "C", "REQUIRES"), ("S", "D", "REQUIRES")],
)


def test_all_of_takes_longest_chain():
    p = Planner(CHAIN, set())
    assert p.finish("S") == Finish(35, True)
    assert p.critical_path() == ["S", "A", "B", "C"]


def test_held_document_counts_zero_and_cuts_its_chain():
    p = Planner(CHAIN, {"B"})
    # A chain is now just A = 10, so D (30) is critical
    assert p.finish("S") == Finish(30, True)
    assert p.critical_path() == ["S", "D"]
    assert "C" not in p.needed()


def test_any_of_takes_fastest_option():
    g = graph(
        [doc("A", 10), doc("X1", 40), doc("X2", 7), Node("X", "AnyOf", "one of")],
        [("S", "A", "REQUIRES"), ("A", "X", "REQUIRES"), ("X", "X1", "OPTION"), ("X", "X2", "OPTION")],
    )
    p = Planner(g, set())
    assert p.finish("S") == Finish(17, True)
    assert p.critical_path() == ["S", "A", "X", "X2"]
    assert p.needed() == ["A", "X2"]


def test_any_of_satisfied_when_one_option_held():
    g = graph(
        [doc("A", 10), doc("X1", 40), doc("X2", 7), Node("X", "AnyOf", "one of")],
        [("S", "A", "REQUIRES"), ("A", "X", "REQUIRES"), ("X", "X1", "OPTION"), ("X", "X2", "OPTION")],
    )
    p = Planner(g, {"X1"})
    assert p.finish("S") == Finish(10, True)
    assert p.ready_now() == ["A"]


def test_unknown_days_give_a_lower_bound_and_are_listed():
    g = graph([doc("A", None), doc("B", 12)], [("S", "A", "REQUIRES"), ("A", "B", "REQUIRES")])
    p = Planner(g, set())
    assert p.finish("S") == Finish(12, False)
    assert p.unknown_needed() == ["A"]


def test_unknown_option_does_not_hide_a_known_faster_option():
    # known option 5, unknown option with bound 9: the minimum is exactly 5
    g = graph(
        [doc("K", 5), doc("U", None), doc("U2", 9), Node("X", "AnyOf", "one of")],
        [("S", "X", "REQUIRES"), ("X", "K", "OPTION"), ("X", "U", "OPTION"), ("U", "U2", "REQUIRES")],
    )
    assert Planner(g, set()).finish("S") == Finish(5, True)


def test_unknown_option_that_might_be_faster_makes_min_inexact():
    g = graph(
        [doc("K", 5), doc("U", None), Node("X", "AnyOf", "one of")],
        [("S", "X", "REQUIRES"), ("X", "K", "OPTION"), ("X", "U", "OPTION")],
    )
    f = Planner(g, set()).finish("S")
    assert f == Finish(0, False)


def test_shared_prerequisite_is_counted_once_in_needed():
    g = graph(
        [doc("A", 3), doc("B", 4), doc("C", 9)],
        [("S", "A", "REQUIRES"), ("S", "B", "REQUIRES"), ("A", "C", "REQUIRES"), ("B", "C", "REQUIRES")],
    )
    p = Planner(g, set())
    assert sorted(p.needed()) == ["A", "B", "C"]
    assert p.finish("S") == Finish(13, True)
    assert p.ready_now() == ["C"]
    assert p.start_of("B") == Finish(9, True)


def test_cycle_is_an_error_not_a_hang():
    g = graph([doc("A", 1), doc("B", 1)], [("S", "A", "REQUIRES"), ("A", "B", "REQUIRES"), ("B", "A", "REQUIRES")])
    with pytest.raises(CycleError):
        Planner(g, set()).finish("S")


def test_ready_now_sorted_by_reduction():
    p = Planner(CHAIN, set())
    assert set(p.ready_now()) == {"C", "D"}
    assert reduction_if_held(CHAIN, set(), "C") == 5   # 35 -> 30 (D becomes critical)
    assert reduction_if_held(CHAIN, set(), "D") == 0


# ---- verdict and deadline edge cases ------------------------------------------

TODAY = dt.date(2026, 10, 17)


def test_days_left_today_and_past():
    assert days_left(TODAY, TODAY) == 0
    assert days_left(dt.date(2026, 10, 16), TODAY) == -1
    assert days_left(None, TODAY) is None


def test_verdict_on_time_and_late():
    v = verdict(Finish(20, True), 26)
    assert (v.kind, v.margin, v.stamp) == ("on_time", 6, "ON TIME · 6 DAYS SPARE")
    v = verdict(Finish(36, True), 26)
    assert (v.kind, v.margin, v.stamp) == ("late", 10, "10 DAYS SHORT")


def test_verdict_exactly_on_deadline_is_on_time_with_zero_spare():
    v = verdict(Finish(26, True), 26)
    assert (v.kind, v.margin) == ("on_time", 0)


def test_verdict_deadline_today():
    assert verdict(Finish(0, True), 0).kind == "on_time"
    assert verdict(Finish(1, True), 0).stamp == "1 DAY SHORT"


def test_verdict_past_deadline_is_closed():
    assert verdict(Finish(3, True), -1).kind == "closed"


def test_verdict_unknown_is_a_lower_bound_never_on_time():
    v = verdict(Finish(35, False), 60)
    assert (v.kind, v.stamp) == ("at_least", "AT LEAST 35 DAYS")
    v = verdict(Finish(35, False), 20)
    assert (v.kind, v.stamp) == ("late_at_least", "AT LEAST 15 DAYS SHORT")
    assert verdict(Finish(0, False), 20).kind == "cannot_compute"


def test_verdict_without_deadline():
    assert verdict(Finish(12, True), None).kind == "no_deadline"
    assert verdict(Finish(0, False), None).stamp == "TIME UNKNOWN"  # never "AT LEAST 0 DAYS"



def test_working_days_in_a_calendar_day_pack_are_a_lower_bound():
    g = graph([Node("A", "Document", "A", 40, days_unit="working_days"), doc("B", 30)],
              [("S", "A", "REQUIRES"), ("S", "B", "REQUIRES")])
    assert Planner(g, set(), unit="calendar_days").finish("S") == Finish(40, False)


def test_calendar_days_in_a_working_day_pack_are_converted_or_marked_unknown():
    g = graph([Node("A", "Document", "A", 30, days_unit="calendar_days"), doc("B", 5)],
              [("S", "A", "REQUIRES"), ("A", "B", "REQUIRES")])
    # without a calendar there is no safe bound: count nothing for A and mark the answer as a lower bound
    assert Planner(g, set(), unit="working_days").finish("S") == Finish(5, False)
    # with a converter the step is exact; the converter sees the step's start (after B: 5)
    seen = []

    def convert(unit, start, days):
        seen.append((unit, start, days))
        return 21
    assert Planner(g, set(), unit="working_days", convert=convert).finish("S") == Finish(26, True)
    assert seen == [("calendar_days", 5, 30)]


def test_critical_path_never_runs_through_a_held_document():
    g = graph([doc("A", 21), doc("H", 5), doc("U", None)],
              [("S", "A", "REQUIRES"), ("A", "H", "REQUIRES"), ("A", "U", "REQUIRES")])
    p = Planner(g, {"H"})
    assert p.critical_path() == ["S", "A", "U"]
    p = Planner(g, {"H", "U"})
    assert p.critical_path() == ["S", "A"]
