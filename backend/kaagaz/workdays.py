"""Working-day calendar from a rule pack.

Sakala time limits are in working days, but deadlines are calendar dates. A pack may declare
`calendar: {unit: working_days, weekly_off: [...], second_fourth_saturday_off: bool|null, holidays: [...]}`,
every part of it sourced. Days left until a deadline are then counted in working days, and a plan's working-day
offsets are mapped back to calendar dates for the timeline.

If the pack's holiday list does not reach the deadline, or a weekly rule has no source, the count can only be
too high (it may include days that are really holidays). The result says so (`complete: False`), so the UI can
warn that the spare days may be fewer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


@dataclass
class WorkCalendar:
    unit: str                      # "working_days" or "calendar_days"
    weekly_off: set[int]           # weekday numbers (Monday = 0)
    second_fourth_saturday_off: bool | None
    holidays: dict[dt.date, str]
    covers_until: dt.date | None

    @classmethod
    def from_pack(cls, pack: dict) -> WorkCalendar:
        cal = pack.get("calendar") or {}
        if cal.get("unit") != "working_days":
            return cls("calendar_days", set(), None, {}, None)
        off = {WEEKDAYS.index(d.lower()) for d in cal.get("weekly_off") or [] if cal.get("weekly_off_cite")}
        sat = cal.get("second_fourth_saturday_off") if cal.get("second_fourth_saturday_cite") else None
        hol = {}
        for h in cal.get("holidays") or []:
            if h.get("cite"):
                d = h["date"] if isinstance(h["date"], dt.date) else dt.date.fromisoformat(str(h["date"]))
                hol[d] = h.get("name", "")
        cover = cal.get("holidays_cover_until")
        if cover and not isinstance(cover, dt.date):
            cover = dt.date.fromisoformat(str(cover))
        return cls("working_days", off, sat, hol, cover)

    @property
    def working(self) -> bool:
        return self.unit == "working_days"

    def is_working(self, d: dt.date) -> bool:
        if not self.working:
            return True
        if d.weekday() in self.weekly_off:
            return False
        if self.second_fourth_saturday_off and d.weekday() == 5 and (d.day - 1) // 7 in (1, 3):
            return False
        return d not in self.holidays

    def days_between(self, today: dt.date, deadline: dt.date) -> int:
        """Working days d with today < d <= deadline (negative if the deadline has passed)."""
        if deadline < today:
            return (deadline - today).days  # past: only the sign matters (the window has closed)
        if not self.working:
            return (deadline - today).days
        n, d = 0, today
        while d < deadline:
            d += dt.timedelta(days=1)
            if self.is_working(d):
                n += 1
        return n

    def complete_until(self, deadline: dt.date | None) -> bool:
        """True if every rule needed to count working days up to the deadline is sourced."""
        if not self.working or deadline is None:
            return True
        if self.second_fourth_saturday_off is None:
            return False
        return self.covers_until is not None and deadline <= self.covers_until

    def date_of(self, today: dt.date, offset: int) -> dt.date:
        """The calendar date on which `offset` working days after today have passed."""
        if not self.working:
            return today + dt.timedelta(days=offset)
        d, n = today, 0
        while n < offset:
            d += dt.timedelta(days=1)
            if self.is_working(d):
                n += 1
        return d

    def calendar_to_working(self, today: dt.date, start: int, days: int) -> int | None:
        """Working days taken by `days` calendar days that begin `start` working days after today."""
        if not self.working:
            return None
        begin = self.date_of(today, start)
        return self.days_between(today, begin + dt.timedelta(days=days)) - start

    def holidays_between(self, a: dt.date, b: dt.date) -> list[dict]:
        return [{"date": d.isoformat(), "name": n} for d, n in sorted(self.holidays.items()) if a < d <= b]
