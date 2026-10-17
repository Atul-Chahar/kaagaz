"""Working-day calendar maths (fixtures only)."""

import datetime as dt

from kaagaz.workdays import WorkCalendar

CITE = {"source_id": "x"}


def cal(sat=True, holidays=(), cover="2026-12-31"):
    return WorkCalendar.from_pack({"calendar": {
        "unit": "working_days", "weekly_off": ["sunday"], "weekly_off_cite": CITE,
        "second_fourth_saturday_off": sat, "second_fourth_saturday_cite": CITE if sat is not None else None,
        "holidays": [{"date": d, "name": "h", "cite": CITE} for d in holidays], "holidays_cover_until": cover}})


def test_no_calendar_means_calendar_days():
    c = WorkCalendar.from_pack({})
    assert not c.working
    assert c.days_between(dt.date(2026, 10, 17), dt.date(2026, 10, 31)) == 14


def test_sundays_and_second_fourth_saturdays_are_off():
    c = cal()
    assert not c.is_working(dt.date(2026, 10, 18))   # Sunday
    assert not c.is_working(dt.date(2026, 10, 10))   # 2nd Saturday
    assert not c.is_working(dt.date(2026, 10, 24))   # 4th Saturday
    assert c.is_working(dt.date(2026, 10, 17))       # 3rd Saturday
    assert c.is_working(dt.date(2026, 10, 31))       # 5th Saturday


def test_days_between_counts_after_today_up_to_deadline():
    c = cal(holidays=["2026-10-20"])
    # 18 Sun off, 19 on, 20 holiday, 21-23 on (3), 24 4th Sat off, 25 Sun off, 26-31 on (6)
    assert c.days_between(dt.date(2026, 10, 17), dt.date(2026, 10, 31)) == 1 + 3 + 6
    assert c.days_between(dt.date(2026, 10, 17), dt.date(2026, 10, 17)) == 0
    assert c.days_between(dt.date(2026, 10, 17), dt.date(2026, 10, 16)) < 0


def test_date_of_maps_offsets_back():
    c = cal(holidays=["2026-10-20"])
    t = dt.date(2026, 10, 17)
    assert c.date_of(t, 0) == t
    assert c.date_of(t, 1) == dt.date(2026, 10, 19)
    assert c.date_of(t, 2) == dt.date(2026, 10, 21)
    assert c.days_between(t, c.date_of(t, 10)) == 10


def test_unsourced_rules_are_ignored_and_marked_incomplete():
    c = WorkCalendar.from_pack({"calendar": {"unit": "working_days", "weekly_off": ["sunday"],
                                             "second_fourth_saturday_off": True}})
    assert c.is_working(dt.date(2026, 10, 18))  # no cite for weekly_off, so not applied
    assert c.complete_until(dt.date(2026, 10, 31)) is False


def test_complete_only_while_holiday_list_covers_deadline():
    c = cal(cover="2026-12-31")
    assert c.complete_until(dt.date(2026, 12, 31))
    assert not c.complete_until(dt.date(2027, 1, 31))
