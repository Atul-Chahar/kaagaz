"""Watcher agent: re-fetches every saved government source and re-checks each rule's proof sentence on it.

For each rule in the rules graph (requirement edges, issuing offices, processing times, application windows) the
watcher asks one question: is the exact sentence that proves this rule still on the live page?

- Still there: nothing to do.
- Gone, but a sentence on the new page matches it closely (dates and numbers masked): the page was reworded.
  If the rule is a scheme's last date and the date in that sentence changed, the finding is `date_changed` with the
  new date. If another number changed, it is `value_changed`. Otherwise `wording_changed`.
- Gone with no close match: `excerpt_missing`.

Findings go into the shared agents graph with the evidence (old sentence, new sentence, the re-fetched copy and its
hash). Nothing in the rules changes until a person approves a finding (decide()). Then the change is written to
data/packs/<pack>/changes.yaml with a citation to the newly saved copy, the rules graph is rebuilt, and the
caseworker re-plans every student whose target scheme it affects.

Run: uv run python -m kaagaz.watcher [--pack in-ka-scholarships] [--only source-id ...] [--limit N]
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import agents, graph
from .changes import append_change
from .sources import CHECKS, LARGE, SRC, Fetcher, load_index, save_index, saved_text
from .textnorm import norm
from .tools import DEFAULT_PACK

MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
                                          "dec"])}
DATE_NUM = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b")
DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATE_WORD = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3})[a-z]*\.?,?\s+(\d{4})\b", re.IGNORECASE)
NUMBER = re.compile(r"\d+")
MATCH_AT = 0.8      # similarity (dates and numbers masked) above which a new sentence counts as the old one reworded
MAX_WORDS = 25


# ---- text matching (pure functions, unit tested) ------------------------------------------------------------

def dates_in(text: str) -> list[str]:
    """ISO dates written in a sentence, in order (dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd, 31 Oct 2026)."""
    found: list[tuple[int, str]] = []
    for m in DATE_NUM.finditer(text):
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        found.append((m.start(), _iso(y, mo, d)))
    for m in DATE_ISO.finditer(text):
        found.append((m.start(), _iso(int(m[1]), int(m[2]), int(m[3]))))
    for m in DATE_WORD.finditer(text):
        mo = MONTHS.get(m[2].lower())
        if mo:
            found.append((m.start(), _iso(int(m[3]), mo, int(m[1]))))
    return [d for _, d in sorted(found) if d]


def _iso(y: int, m: int, d: int) -> str:
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return ""


def _soft(text: str) -> list[str]:
    """Whitespace tokens with the audit's character normalisation but the original case (for quoting)."""
    text = unicodedata.normalize("NFKC", text)
    for a, b in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "\xa0": " "}.items():
        text = text.replace(a, b)
    return text.split()


def _mask(s: str) -> str:
    return NUMBER.sub("#", s)


@dataclass
class Candidate:
    excerpt: str
    score: float


def best_match(excerpt: str, new_text: str, tokens: list[str] | None = None) -> Candidate | None:
    """The run of words on the new page that looks most like the old excerpt, scored with digits masked."""
    ex = norm(excerpt).split()
    if not ex:
        return None
    toks = tokens if tokens is not None else _soft(new_text)
    low = [t.lower() for t in toks]
    where: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(low):
        where[t].append(i)
    anchors = [(j, w) for j, w in enumerate(ex) if len(w) >= 4 and not any(c.isdigit() for c in w)] or \
        list(enumerate(ex))
    starts: set[int] = set()
    for j, w in anchors:
        for p in where.get(w, [])[:300]:
            for shift in (-2, -1, 0, 1, 2):
                starts.add(max(0, p - j + shift))
    target = _mask(" ".join(ex))
    best: Candidate | None = None
    for s in starts:
        for n in {len(ex) - 1, len(ex), len(ex) + 1}:
            if n < 1 or s + n > len(low):
                continue
            score = difflib.SequenceMatcher(None, target, _mask(" ".join(low[s:s + n])), autojunk=False).ratio()
            if best is None or score > best.score:
                best = Candidate(" ".join(toks[s:s + min(n, MAX_WORDS)]), round(score, 3))
    return best


def classify(rule: dict, new_norm: str, new_text: str, tokens: list[str] | None = None) -> dict | None:
    """None if the rule's proof sentence is still on the page; otherwise what changed, with the evidence."""
    old = rule.get("excerpt") or ""
    if not old or norm(old) in new_norm:
        return None
    cand = best_match(old, new_text, tokens)
    if cand is None or cand.score < MATCH_AT or norm(cand.excerpt) not in new_norm:
        return {"kind": "excerpt_missing", "new_excerpt": cand.excerpt if cand else None,
                "score": cand.score if cand else 0.0, "new_value": None}
    out = {"new_excerpt": cand.excerpt, "score": cand.score, "new_value": None}
    if rule["kind"] == "window" and rule.get("value"):
        before, after = dates_in(old), dates_in(cand.excerpt)
        if rule["value"] in before and rule["value"] not in after and after:
            new = after[before.index(rule["value"])] if len(after) == len(before) else (after[0] if len(after) == 1
                                                                                         else None)
            if new:
                return out | {"kind": "date_changed", "new_value": new}
            return out | {"kind": "value_changed", "note": "the dates changed, but which one is the last date "
                                                           "is not clear; check the page by hand"}
    if NUMBER.findall(old) != NUMBER.findall(cand.excerpt):
        return out | {"kind": "value_changed"}
    return out | {"kind": "wording_changed"}


# ---- the run ---------------------------------------------------------------------------------------------------

def _fid(pack: str, rule_key: str, kind: str, new_excerpt: str | None) -> str:
    return "f-" + hashlib.sha1(f"{pack}|{rule_key}|{kind}|{new_excerpt or ''}".encode()).hexdigest()[:12]


def _rules(pack: str) -> list[dict]:
    return graph.run(graph.rules_graph_name(pack), "rules_by_source", {}).rows


def _schemes_above(pack: str, node_id: str, cache: dict) -> list[str]:
    if node_id not in cache:
        rows = graph.run(graph.rules_graph_name(pack), "schemes_above", {"id": node_id}).rows
        cache[node_id] = sorted({r["scheme_id"] for r in rows})
    return cache[node_id]


def _source_row(index: list[dict], url: str, retrieved_at: str | None) -> dict | None:
    rows = [r for r in index if r["url"] == url]
    exact = [r for r in rows if str(r["retrieved_at"]) == str(retrieved_at)]
    return (exact or sorted(rows, key=lambda r: str(r["retrieved_at"])))[-1] if rows else None


def run_watch(pack: str = DEFAULT_PACK, only: list[str] | None = None, limit: int | None = None,
              trigger: str = "manual", include_large: bool = False, fetcher: Fetcher | None = None,
              progress=None) -> dict:
    run_id = agents.start_run("watcher", pack, trigger)
    index = load_index()
    by_source: dict[str, list[dict]] = defaultdict(list)
    rows_of: dict[str, dict] = {}
    for rule in _rules(pack):
        row = _source_row(index, rule["url"], rule["retrieved_at"])
        if row is None:
            continue
        by_source[row["id"]].append(rule)
        rows_of[row["id"]] = row
    # check the sources behind the schemes students are working on first (shared memory from the registry)
    want = {r["scheme_id"]: r["students"] for r in agents.q("agents_watch_priority", {"pack": pack})}
    above: dict[str, list[str]] = {}
    for rules in by_source.values():
        for rule in rules:
            rule["schemes"] = [rule["from_id"]] if rule["kind"] == "window" else _schemes_above(pack, rule["from_id"],
                                                                                                 above)
    def priority(sid: str) -> tuple:
        schemes = {s for r in by_source[sid] for s in r["schemes"]}
        # then deadlines of targeted schemes (they move most often), then other rules naming a targeted scheme
        windows = sum(1 for r in by_source[sid] if r["kind"] == "window" and r["from_id"] in want)
        direct = sum(1 for r in by_source[sid] if r["from_id"] in want)
        return (-sum(want.get(s, 0) for s in schemes), -windows, -direct, sid)

    order = sorted(by_source, key=priority)
    if only:
        order = [s for s in order if s in set(only)]
    if limit:
        order = order[:limit]
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    counts: dict[str, int] = defaultdict(int)
    raised: list[str] = []
    today = dt.date.today().isoformat()
    try:
        for n, sid in enumerate(order, 1):
            row, rules = rows_of[sid], by_source[sid]
            check = {"source_id": sid, "url": row["url"], "title": row["title"], "at": agents.now_iso(),
                     "rules_checked": len(rules), "rules_missing": 0, "saved_retrieved_at": str(row["retrieved_at"])}
            if "web.archive.org" in row["url"]:
                check["status"] = "archived_copy"   # an archived snapshot never changes
            elif (row.get("size") or 0) > LARGE and not include_large:
                check["status"] = "skipped_large"
            else:
                got = fetcher.fetch(row["url"], CHECKS / run_id, sid)
                check.update({"status": got.status, "http": got.http, "tls_verified": got.tls_verified,
                              "new_sha256": got.sha256, "error": got.error})
                if got.status == "ok":
                    old = saved_text(row)
                    new_norm = norm(got.text or "")
                    check["status"] = "same_text" if old is not None and norm(old) == new_norm else "text_changed"
                    check["same_file"] = got.sha256 == row["sha256"]
                    check["new_text_file"] = str(got.text_path.relative_to(SRC)) if got.text_path else None
                    tokens = _soft(got.text or "")
                    for rule in rules:
                        res = classify(rule, new_norm, got.text or "", tokens)
                        if res is None:
                            continue
                        check["rules_missing"] += 1
                        fid = _fid(pack, rule["rule_key"], res["kind"], res.get("new_excerpt"))
                        props = {"pack": pack, "kind": res["kind"], "rule_key": rule["rule_key"],
                                 "rule_kind": rule["kind"], "from_id": rule["from_id"], "to_id": rule["to_id"],
                                 "source_id": sid, "source_url": row["url"], "source_title": row["title"],
                                 "old_excerpt": rule["excerpt"], "old_value": rule.get("value"),
                                 "new_excerpt": res.get("new_excerpt"), "new_value": res.get("new_value"),
                                 "score": res.get("score"), "note": res.get("note"), "checked_on": today,
                                 "check_run": run_id, "new_text_file": check["new_text_file"],
                                 "new_raw_file": str(got.raw_path.relative_to(SRC)) if got.raw_path else None,
                                 "new_sha256": got.sha256, "tls_verified": got.tls_verified}
                        agents.q("agents_finding_upsert", {"run_id": run_id, "id": fid, "props": props,
                                                           "now": agents.now_iso(), "pack": pack,
                                                           "scheme_ids": rule["schemes"]}, write=True)
                        raised.append(fid)
                        counts[f"finding_{res['kind']}"] += 1
            counts[check["status"]] += 1
            agents.q("agents_check_add", {"run_id": run_id, "props": {k: v for k, v in check.items() if v is not None}},
                     write=True)
            if progress:
                progress(n, len(order), check)
    except Exception as e:  # a crashed run is recorded as failed, then re-raised
        agents.finish_run(run_id, "failed", {"error": f"{type(e).__name__}: {e}", **counts})
        raise
    finally:
        if own:
            fetcher.close()
    summary = {"sources": len(order), "rules": sum(len(by_source[s]) for s in order), "findings": len(set(raised)),
               **counts}
    agents.finish_run(run_id, "done", summary)
    return agents.run_detail(run_id) or {"run": {"id": run_id}}


# ---- a person decides -------------------------------------------------------------------------------------------

def _promote(f: dict) -> dict:
    """Save the re-fetched copy as a new version of the source (new id, same URL, today's date) and return its
    index row. Reused if that copy was already promoted by another finding from the same check."""
    index = load_index()
    for r in index:
        if r["url"] == f["source_url"] and r.get("sha256") == f["new_sha256"]:
            return r
    old = next(r for r in index if r["id"] == f["source_id"])
    day = str(f["checked_on"])
    base = re.sub(r"-v\d{8}$", "", old["id"])
    new_id = f"{base}-v{day.replace('-', '')}"
    raw_src, text_src = SRC / f["new_raw_file"], SRC / f["new_text_file"]
    raw_dst = SRC / "raw" / f"{new_id}{raw_src.suffix}"
    text_dst = SRC / "text" / f"{new_id}.txt"
    shutil.copyfile(raw_src, raw_dst)
    shutil.copyfile(text_src, text_dst)
    text = text_dst.read_text()
    row = {k: v for k, v in old.items() if k not in ("id", "file", "text_file", "sha256", "size", "text_chars",
                                                      "retrieved_at", "large_not_in_git")}
    row.update({"id": new_id, "retrieved_at": day, "sha256": hashlib.sha256(raw_dst.read_bytes()).hexdigest(),
                "file": f"raw/{raw_dst.name}", "text_file": f"text/{text_dst.name}", "size": raw_dst.stat().st_size,
                "large_not_in_git": False, "text_chars": len(text), "previous_version": old["id"],
                "saved_by": "watcher (approved by a person)"})
    save_index([r for r in index if r["id"] != new_id] + [row])
    return row


def _old_confidence(pack: dict, rule_key: str) -> str:
    from .changes import _target
    hit = _target(pack, rule_key)
    return ((hit[1].get(hit[0]) or {}).get("confidence") if hit else None) or "official"


def decide(fid: str, approve: bool, note: str = "") -> dict:
    f = agents.finding(fid)
    if f is None:
        raise KeyError(fid)
    if f["status"] != "open":
        raise ValueError(f"finding {fid} is already {f['status']}")
    pack = f["pack"]
    applied = None
    if approve:
        if f["kind"] in ("date_changed", "wording_changed"):
            ex = f.get("new_excerpt") or ""
            text_file = SRC / (f.get("new_text_file") or "")
            if len(ex.split()) > MAX_WORDS or not text_file.exists() or norm(ex) not in norm(text_file.read_text()):
                raise ValueError("the new sentence is not in the re-fetched copy any more; run the watcher again")
            row = _promote(f)
            cite = {"source_url": row["url"], "source_title": row["title"], "retrieved_at": row["retrieved_at"],
                    "excerpt": ex, "confidence": _old_confidence(graph.load_pack(pack), f["rule_key"])}
            change = {"kind": "window_end" if f["kind"] == "date_changed" else "excerpt", "rule_key": f["rule_key"],
                      "cite": cite}
            if f["kind"] == "date_changed":
                change["value"] = f["new_value"]
        else:
            # the proof is gone (or a number changed): keep the rule, flag it for a person to rework the pack
            change = {"kind": "stale", "rule_key": f["rule_key"], "checked_at": str(f["checked_on"]),
                      "source_url": f["source_url"], "found": f.get("new_excerpt")}
        change |= {"finding_id": fid, "approved_at": agents.now_iso(), "note": note or None}
        append_change(graph.PACKS_DIR, pack, change)
        graph.load_pack.cache_clear()
        graph.seed_pack(pack)
        applied = change
    agents.ensure()
    decided = agents.q("agents_finding_decide", {"id": fid, "status": "approved" if approve else "rejected",
                                                 "now": agents.now_iso(), "note": note or None}, write=True)
    out = {"finding": dict(decided[0]["finding"]) if decided else f, "applied": applied}
    if approve:
        from . import caseworker
        out["propagation"] = caseworker.propagate(pack)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pack", default=DEFAULT_PACK)
    ap.add_argument("--only", nargs="*", help="source ids to check")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--include-large", action="store_true")
    ap.add_argument("--trigger", default="cli")
    ap.add_argument("--report", help="write a Markdown report here")
    ap.add_argument("--json", help="write the run as JSON here")
    a = ap.parse_args(argv)

    def show(n: int, total: int, c: dict) -> None:
        print(f"[{n}/{total}] {c['source_id']}: {c['status']} ({c['rules_checked']} rules, "
              f"{c.get('rules_missing', 0)} not found)", flush=True)

    res = run_watch(a.pack, a.only, a.limit, a.trigger, a.include_large, progress=show)
    found = [agents.finding(f) for f in res["findings"]]
    if a.json:
        Path(a.json).write_text(json.dumps({"run": res["run"], "checks": res["checks"], "findings": found},
                                           indent=2, ensure_ascii=False, default=str) + "\n")
    if a.report:
        Path(a.report).write_text(report(res, found))
    s = res["run"].get("summary") or {}
    print(f"watcher: {s.get('sources', 0)} sources, {s.get('rules', 0)} rules, {s.get('findings', 0)} findings")
    return 0


def report(res: dict, found: list[dict | None]) -> str:
    run = res["run"]
    s = run.get("summary") or {}
    lines = [f"# Watcher run {run['id']}", "",
             (f"Started {run.get('started_at')}, finished {run.get('finished_at')}. "
              f"{s.get('sources', 0)} sources and {s.get('rules', 0)} rules checked; {s.get('findings', 0)} findings."),
             "", "| Source | Status | Rules | Proof sentence not found |", "|---|---|---|---|"]
    for c in res["checks"]:
        lines.append(f"| [{c['source_id']}]({c['url']}) | {c['status']} | {c.get('rules_checked', 0)} | "
                     f"{c.get('rules_missing', 0)} |")
    if any(found):
        lines += ["", "## Findings (each needs a person to approve or reject it)", ""]
        for f in filter(None, found):
            lines += [f"### {f['kind']}: `{f['rule_key']}` ({f['status']})", "",
                      f"- Source: {f['source_title']} ({f['source_url']})",
                      f"- Saved sentence: \"{f['old_excerpt']}\"",
                      (f"- On the page now: \"{f.get('new_excerpt') or 'no close match'}\" (similarity "
                       f"{f.get('score')})")]
            if f.get("new_value"):
                lines.append(f"- Value: {f.get('old_value')} -> {f['new_value']}")
            lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
