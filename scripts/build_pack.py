"""Build data/packs/<pack-id>/pack.yaml from the research fragments in data/research/.

Every cite in a fragment names a saved source by id; this script copies that source's url, title and
retrieved_at from data/sources/index.json into the rule, so each rule in pack.yaml carries all five fields
(source_url, source_title, retrieved_at, excerpt, confidence). Nothing is invented here: a document that is
referenced but described nowhere makes the build fail.

Usage: backend/.venv/bin/python scripts/build_pack.py [--pack in-ka-scholarships]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
INDEX = {r["id"]: r for r in json.loads((ROOT / "data/sources/index.json").read_text())}

# Fragment priority for scalar document facts (first wins): the documents research is the authority on
# documents, the scheme research on schemes. Order matters only when two fragments disagree.
PRIORITY = ["documents.yaml", "documents2.yaml", "karnataka.yaml", "nsp.yaml", "names.yaml"]


def expand(cite: dict | None, where: str) -> dict | None:
    if not cite:
        return None
    sid = cite.get("source_id")
    if sid not in INDEX:
        sys.exit(f"build_pack: {where}: unknown source_id {sid!r}")
    src = INDEX[sid]
    return {
        "source_id": sid,
        "source_url": src["url"],
        "source_title": src["title"],
        "retrieved_at": src["retrieved_at"],
        "excerpt": cite["excerpt"],
        "confidence": cite["confidence"],
    }


def expand_calendar(cal: dict, where: str) -> dict:
    out = dict(cal)
    for k in list(out):
        if k.endswith("_cite"):
            out[k] = expand(out[k], f"{where}/calendar/{k}")
    out["holidays"] = [dict(h, cite=expand(h.get("cite"), f"{where}/calendar/{h.get('date')}"))
                       for h in cal.get("holidays") or []]
    return out


def fragments(research: Path = RESEARCH) -> list[tuple[str, dict]]:
    files = sorted(research.glob("*.yaml"), key=lambda p: (PRIORITY.index(p.name) if p.name in PRIORITY else 99, p.name))
    return [(p.name, yaml.safe_load(p.read_text()) or {}) for p in files]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default="in-ka-scholarships")
    ap.add_argument("--research", default=None, help="fragment folder (default data/research)")
    args = ap.parse_args()
    pack_dir = ROOT / "data" / "packs" / args.pack
    research = Path(args.research) if args.research else RESEARCH
    meta = yaml.safe_load((pack_dir / "meta.yaml").read_text())
    exclude_conditions = {c["condition"] for c in meta.get("exclude_conditions", [])}
    assumed_conditions = {c["condition"] for c in meta.get("assumed_conditions", [])}

    offices: dict[str, dict] = {}
    docs: dict[str, dict] = {}
    schemes: dict[str, dict] = {}
    any_of: dict[str, dict] = {}
    rules: dict[tuple, dict] = {}
    conflicts: list[str] = []
    excluded: list[dict] = []

    def add_rule(src: str, dst: str, kind: str, cite: dict | None, where: str, note: str | None = None,
                 condition: str | None = None):
        c = expand(cite, where)
        if c is None:
            sys.exit(f"build_pack: {where}: rule {src} -> {dst} has no cite")
        key = (src, dst, kind)
        if key not in rules:
            rules[key] = {"from": src, "to": dst, "kind": kind, "cite": c, **({"note": note} if note else {}),
                          **({"condition": condition} if condition else {})}

    def add_requires(owner: str, reqs: list[dict], where: str):
        for r in reqs or []:
            if r.get("condition") in exclude_conditions:
                # A rule that only applies to people the pack does not model (meta.yaml exclude_conditions, e.g.
                # "born on or after 1.10.2023" for a college student) is kept out of the graph and listed in
                # pack.yaml so the exclusion is visible. Other conditional rules stay, with their condition shown.
                excluded.append({"from": owner, "to": r.get("doc") or r.get("any_of", {}).get("id"),
                                 "condition": r["condition"], "cite": expand(r.get("cite"), f"{where}/{owner}")})
                continue
            cond, note = r.get("condition"), r.get("note")
            if cond in assumed_conditions:
                # true for everyone the pack models (meta.yaml assumed_conditions): a plain rule, the assumption noted
                note = f"{note + ' ' if note else ''}Applies to everyone this pack models: {cond}."
                cond = None
            if "doc" in r:
                add_rule(owner, r["doc"], "REQUIRES", r.get("cite"), f"{where}/{owner}", note, cond)
            elif "any_of" in r:
                a = r["any_of"]
                any_of.setdefault(a["id"], {"id": a["id"], "label": a["label"]})
                add_rule(owner, a["id"], "REQUIRES", r.get("cite"), f"{where}/{owner}", r.get("note"))
                for o in r.get("options", []):
                    add_rule(a["id"], o["doc"], "OPTION", o.get("cite"), f"{where}/{a['id']}", o.get("note"))
            else:
                sys.exit(f"build_pack: {where}/{owner}: requirement without doc or any_of: {r}")

    for fname, frag in fragments(research):
        for o in frag.get("offices", []) or []:
            if o["id"] not in offices:
                offices[o["id"]] = {"id": o["id"], "name": o["name"], "level": o.get("level"),
                                    "cite": expand(o.get("office_cite"), f"{fname}/office/{o['id']}")}
        for d in frag.get("documents", []) or []:
            cur = docs.setdefault(d["id"], {"id": d["id"]})
            for k in ("name", "office", "days", "days_unit", "validity", "note", "service_days"):
                v = d.get(k)
                if v is None:
                    continue
                if cur.get(k) is None:
                    cur[k] = v
                elif k in ("days", "office") and cur[k] != v:
                    conflicts.append(f"{d['id']}.{k}: kept {cur[k]!r}, {fname} says {v!r}")
                elif k == "note" and v not in cur[k]:
                    cur[k] = f"{cur[k]} {v}"
            if d.get("note_assumption"):
                cur["note"] = (f"{cur.get('note') or ''} {d['note_assumption']}").strip()
            for k in ("office_cite", "days_cite", "validity_cite", "service_days_cite"):
                if d.get(k) and not cur.get(k) and (k != "days_cite" or cur.get("days") == d.get("days")):
                    cur[k] = expand(d[k], f"{fname}/doc/{d['id']}/{k}")
            add_requires(d["id"], d.get("requires"), fname)
        for extra in frag.get("document_offices", []) or []:
            cur = docs.setdefault(extra["doc"], {"id": extra["doc"]})
            if extra.get("office") and not cur.get("office"):
                cur["office"] = extra["office"]
                cur["office_cite"] = expand(extra.get("office_cite"), f"{fname}/document_offices/{extra['doc']}")
            if extra.get("note"):
                cur["note"] = (cur.get("note", "") + " " + extra["note"]).strip()
        for s in frag.get("schemes", []) or []:
            if s["id"] in schemes:
                sys.exit(f"build_pack: scheme {s['id']} defined twice")
            win = dict(s.get("window") or {})
            if win.get("cite"):
                win["cite"] = expand(win["cite"], f"{fname}/scheme/{s['id']}/window")
            schemes[s["id"]] = {"id": s["id"], "name": s["name"], "authority": s.get("authority"),
                                "portal": s.get("portal"), "note": s.get("note"), "window": win}
            add_requires(s["id"], s.get("requires"), fname)

    calendar = None
    for fname, frag in fragments(research):
        if frag.get("calendar"):
            calendar = expand_calendar(frag["calendar"], fname)

    # every referenced node must be described somewhere
    known = set(docs) | set(any_of) | set(schemes)
    for (src, dst, _kind) in rules:
        if dst not in known:
            sys.exit(f"build_pack: rule {src} -> {dst}: {dst} is not described in any fragment")
    missing_names = [d for d, v in docs.items() if not v.get("name")]
    if missing_names:
        sys.exit(f"build_pack: documents without a name: {missing_names}")
    for d in docs.values():
        if d.get("office") and d["office"] not in offices:
            sys.exit(f"build_pack: document {d['id']} names unknown office {d['office']}")
        if d.get("days") is not None and not d.get("days_cite"):
            sys.exit(f"build_pack: document {d['id']} has days but no days_cite")
        if d.get("office") and not d.get("office_cite"):
            d["office_cite"] = None

    ids = list(docs) + list(any_of) + list(schemes) + list(offices)
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        sys.exit(f"build_pack: ids used by more than one node: {sorted(dupes)}")

    pack = {
        "pack": meta["pack"],
        "offices": sorted(offices.values(), key=lambda o: o["id"]),
        "documents": sorted(docs.values(), key=lambda d: d["id"]),
        "any_of": sorted(any_of.values(), key=lambda a: a["id"]),
        "schemes": sorted(schemes.values(), key=lambda s: s["id"]),
        "rules": sorted(rules.values(), key=lambda r: (r["from"], r["kind"], r["to"])),
        "example_student": meta.get("example_student"),
        "calendar": calendar,
        "groups": meta.get("groups", []),
        "excluded_rules": excluded,
    }
    out = pack_dir / "pack.yaml"
    header = "# GENERATED by scripts/build_pack.py from data/research/*.yaml. Edit the fragments, not this file.\n"
    out.write_text(header + yaml.safe_dump(pack, sort_keys=False, allow_unicode=True, width=120))
    print(f"wrote {out.relative_to(ROOT)}: {len(schemes)} schemes, {len(docs)} documents, {len(any_of)} any-of, "
          f"{len(offices)} offices, {len(rules)} rules")
    for c in conflicts:
        print("CONFLICT", c)


if __name__ == "__main__":
    main()
