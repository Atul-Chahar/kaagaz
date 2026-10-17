"""Data audit (spec section 4). Exits non-zero if any rule in any pack breaks the integrity rules.

Checks, for every pack in data/packs/*/pack.yaml:
- every rule (REQUIRES / OPTION edge, processing time, application window, issuing office) has
  source_url, source_title, retrieved_at (ISO date), excerpt (<= 25 words) and confidence (official|secondary)
- every source_url is in data/sources/index.json, and title / retrieved_at match the index
- every excerpt is found in that source's saved text (whitespace and case normalised)
- every saved source file still has the SHA-256 recorded in the index (unless it is a >5 MB file kept out of git)
- days are null or a positive integer; no requirement cycles; ids are unique; the example student is labelled
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import norm

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "sources"
FIELDS = ("source_url", "source_title", "retrieved_at", "excerpt", "confidence")

errors: list[str] = []
checked = {"rules": 0, "days": 0, "windows": 0, "offices": 0, "sources": 0}


def err(msg: str) -> None:
    errors.append(msg)


index_rows = json.loads((SRC / "index.json").read_text())
by_url = {r["url"]: r for r in index_rows}
text_cache: dict[str, str] = {}


def source_text(row: dict) -> str:
    if row["id"] not in text_cache:
        text_cache[row["id"]] = norm((SRC / row["text_file"]).read_text())
    return text_cache[row["id"]]


def check_cite(c: dict | None, where: str) -> None:
    if not isinstance(c, dict):
        err(f"{where}: missing source")
        return
    for f in FIELDS:
        if not c.get(f):
            err(f"{where}: missing {f}")
    if c.get("confidence") not in ("official", "secondary"):
        err(f"{where}: confidence must be official or secondary, got {c.get('confidence')!r}")
    try:
        dt.date.fromisoformat(str(c.get("retrieved_at")))
    except ValueError:
        err(f"{where}: retrieved_at is not an ISO date: {c.get('retrieved_at')!r}")
    ex = c.get("excerpt") or ""
    if len(ex.split()) > 25:
        err(f"{where}: excerpt has {len(ex.split())} words (max 25)")
    row = by_url.get(c.get("source_url"))
    if row is None:
        err(f"{where}: source_url not in index: {c.get('source_url')}")
        return
    if row["title"] != c.get("source_title"):
        err(f"{where}: source_title differs from index ({row['title']!r})")
    if str(row["retrieved_at"]) != str(c.get("retrieved_at")):
        err(f"{where}: retrieved_at differs from index ({row['retrieved_at']})")
    if ex and norm(ex) not in source_text(row):
        err(f"{where}: excerpt not found in saved source {row['id']}: {ex!r}")


def audit_sources() -> None:
    ids = [r["id"] for r in index_rows]
    if len(ids) != len(set(ids)):
        err("index.json: duplicate source ids")
    for r in index_rows:
        checked["sources"] += 1
        for f in ("id", "url", "title", "retrieved_at", "sha256", "file", "text_file"):
            if not r.get(f):
                err(f"index {r.get('id')}: missing {f}")
        raw = SRC / r["file"]
        if raw.exists():
            if hashlib.sha256(raw.read_bytes()).hexdigest() != r["sha256"]:
                err(f"index {r['id']}: sha256 does not match {r['file']}")
        elif not r.get("large_not_in_git"):
            err(f"index {r['id']}: raw file missing: {r['file']}")
        if not (SRC / r["text_file"]).exists():
            err(f"index {r['id']}: text file missing: {r['text_file']}")


def audit_pack(path: Path) -> None:
    pack = yaml.safe_load(path.read_text())
    pid = pack["pack"]["id"]
    docs = {d["id"]: d for d in pack.get("documents", [])}
    anyof = {a["id"] for a in pack.get("any_of", [])}
    schemes = {s["id"]: s for s in pack.get("schemes", [])}
    offices = {o["id"] for o in pack.get("offices", [])}
    all_ids = list(docs) + list(anyof) + list(schemes) + list(offices)
    if len(all_ids) != len(set(all_ids)):
        err(f"{pid}: duplicate ids")

    for d in docs.values():
        where = f"{pid}/document/{d['id']}"
        days = d.get("days")
        if days is not None:
            checked["days"] += 1
            if not isinstance(days, int) or days <= 0:
                err(f"{where}: days must be null or a positive integer, got {days!r}")
            check_cite(d.get("days_cite"), f"{where}/days")
        if d.get("service_days") is not None:
            check_cite(d.get("service_days_cite"), f"{where}/service_days")
        if d.get("office"):
            checked["offices"] += 1
            if d["office"] not in offices:
                err(f"{where}: unknown office {d['office']}")
            check_cite(d.get("office_cite"), f"{where}/office")
    for s in schemes.values():
        w = s.get("window") or {}
        if w.get("end") or w.get("start"):
            checked["windows"] += 1
            check_cite(w.get("cite"), f"{pid}/scheme/{s['id']}/window")
            if not w.get("year"):
                err(f"{pid}/scheme/{s['id']}/window: missing year")
    kids: dict[str, list[str]] = {}
    for r in pack.get("rules", []):
        checked["rules"] += 1
        where = f"{pid}/rule/{r['from']}->{r['to']}"
        if r["kind"] not in ("REQUIRES", "OPTION"):
            err(f"{where}: bad kind {r['kind']}")
        if r["from"] not in docs and r["from"] not in anyof and r["from"] not in schemes:
            err(f"{where}: unknown from")
        if r["to"] not in docs and r["to"] not in anyof:
            err(f"{where}: unknown to")
        if r["kind"] == "OPTION" and r["from"] not in anyof:
            err(f"{where}: OPTION must start at an AnyOf")
        check_cite(r.get("cite"), where)
        kids.setdefault(r["from"], []).append(r["to"])

    # cycle check
    state: dict[str, int] = {}

    def visit(n: str, trail: list[str]) -> None:
        if state.get(n) == 1:
            err(f"{pid}: requirement cycle {' -> '.join(trail + [n])}")
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for k in kids.get(n, []):
            visit(k, trail + [n])
        state[n] = 2

    for s in schemes:
        visit(s, [])

    cal = pack.get("calendar")
    if cal:
        checked["calendar"] = 0
        for k in ("unit_cite", "weekly_off_cite", "second_fourth_saturday_cite"):
            if cal.get(k):
                checked["calendar"] += 1
                check_cite(cal[k], f"{pid}/calendar/{k}")
        for h in cal.get("holidays") or []:
            checked["calendar"] += 1
            check_cite(h.get("cite"), f"{pid}/calendar/holiday/{h.get('date')}")
    for x in pack.get("excluded_rules") or []:
        check_cite(x.get("cite"), f"{pid}/excluded/{x['from']}->{x['to']}")

    ex = pack.get("example_student")
    if ex:
        if ex.get("label") != "Example student":
            err(f"{pid}: example student must be labelled 'Example student'")
        for h in ex.get("holdings", []):
            if h not in docs:
                err(f"{pid}: example student holds unknown document {h}")
        if ex.get("scheme_id") not in schemes:
            err(f"{pid}: example student targets unknown scheme")


def main() -> int:
    audit_sources()
    packs = sorted((ROOT / "data" / "packs").glob("*/pack.yaml"))
    if not packs:
        err("no packs found")
    for p in packs:
        audit_pack(p)
    print(f"audit: {len(packs)} pack(s); checked {checked['rules']} requirement rules, {checked['days']} processing "
          f"times, {checked['windows']} windows, {checked['offices']} issuing offices, {checked.get('calendar', 0)} "
          f"calendar facts, {checked['sources']} sources")
    if errors:
        for e in errors:
            print("AUDIT FAIL:", e)
        print(f"audit: {len(errors)} problem(s)")
        return 1
    print("audit: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
