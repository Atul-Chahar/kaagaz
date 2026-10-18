"""Rule changes a person approved after the watcher agent found them (data/packs/<pack>/changes.yaml).

pack.yaml stays as it was built. An approved change is applied on top of it when the pack loads, so a reseed keeps
it, and scripts/audit_data.py audits the merged result: every changed rule still needs a saved source and an
excerpt found in that source's saved text.

Kinds:
- window_end: a scheme's last date changed on its source page (new date and new cite)
- excerpt: a rule's proof sentence was reworded on the source page (new cite, same value)
- stale: the proof sentence is no longer on the source page; the rule is kept but marked for review
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

import yaml

KINDS = ("window_end", "excerpt", "stale")


def changes_path(packs_dir: Path, pack_id: str) -> Path:
    return packs_dir / pack_id / "changes.yaml"


def load_changes(packs_dir: Path, pack_id: str) -> list[dict]:
    p = changes_path(packs_dir, pack_id)
    if not p.exists():
        return []
    return (yaml.safe_load(p.read_text()) or {}).get("changes") or []


def append_change(packs_dir: Path, pack_id: str, change: dict) -> None:
    p = changes_path(packs_dir, pack_id)
    rows = load_changes(packs_dir, pack_id)
    rows.append(change)
    header = ("# Rule changes approved by a person after the watcher agent found them on the live source pages.\n"
              "# Applied on top of pack.yaml when the pack loads; audited by scripts/audit_data.py.\n")
    p.write_text(header + yaml.safe_dump({"changes": rows}, sort_keys=False, allow_unicode=True, width=120))


def _target(pack: dict, rule_key: str) -> tuple[str, dict] | None:
    """Find the rule a key names. Keys: window:<scheme>, days:<doc>, office:<doc>, REQUIRES:<from>><to>,
    OPTION:<from>><to>. Returns (cite field name, the dict holding it)."""
    kind, _, ref = rule_key.partition(":")
    if kind == "window":
        s = next((s for s in pack.get("schemes", []) if s["id"] == ref), None)
        return ("cite", s.setdefault("window", {})) if s else None
    if kind in ("days", "office"):
        d = next((d for d in pack.get("documents", []) if d["id"] == ref), None)
        return (f"{kind}_cite", d) if d else None
    if kind in ("REQUIRES", "OPTION"):
        src, _, dst = ref.partition(">")
        r = next((r for r in pack.get("rules", []) if r["kind"] == kind and r["from"] == src and r["to"] == dst),
                 None)
        return ("cite", r) if r else None
    return None


def apply_changes(pack: dict, changes: list[dict]) -> dict:
    """Return a copy of the pack with the approved changes applied, in order. Unknown targets are skipped here
    (the audit reports them)."""
    out = copy.deepcopy(pack)
    for c in changes:
        hit = _target(out, c.get("rule_key", ""))
        if hit is None:
            continue
        field, holder = hit
        if c["kind"] == "window_end":
            before = holder.get("end")
            holder["end"] = dt.date.fromisoformat(str(c["value"]))
            holder[field] = dict(c["cite"]) | {"changed_from": str(before) if before else None}
        elif c["kind"] == "excerpt":
            holder[field] = c["cite"]
        elif c["kind"] == "stale":
            cite = dict(holder.get(field) or {})
            cite["stale_since"] = str(c["checked_at"])
            holder[field] = cite
    return out


def unknown_targets(pack: dict, changes: list[dict]) -> list[str]:
    return [c.get("rule_key", "?") for c in changes if c.get("kind") not in KINDS or _target(pack, c.get("rule_key", ""))
            is None]
