"""FalkorDB connection, graph names, query loading and pack seeding."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import cache, lru_cache
from pathlib import Path

import yaml
from falkordb import FalkorDB
from redis.exceptions import ResponseError

from .changes import apply_changes, load_changes

ROOT = Path(__file__).resolve().parent.parent.parent
PACKS_DIR = Path(os.environ.get("KAAGAZ_PACKS_DIR", ROOT / "data" / "packs"))
QUERIES_DIR = Path(__file__).resolve().parent / "queries"
QUERY_TIMEOUT_MS = int(os.environ.get("KAAGAZ_QUERY_TIMEOUT_MS", "10000"))
CITE_FIELDS = ("source_url", "source_title", "retrieved_at", "excerpt", "confidence", "stale_since", "changed_from")


def rules_graph_name(pack_id: str) -> str:
    return f"kaagaz:rules:{pack_id}"


def student_graph_name(student_id: str) -> str:
    return f"kaagaz:student:{student_id}"


@lru_cache(maxsize=1)
def db() -> FalkorDB:
    return FalkorDB(
        host=os.environ.get("FALKORDB_HOST", "localhost"),
        port=int(os.environ.get("FALKORDB_PORT", "6380")),
        username=os.environ.get("FALKORDB_USERNAME") or None,
        password=os.environ.get("FALKORDB_PASSWORD") or None,
    )


@cache
def query_text(name: str) -> str:
    path = QUERIES_DIR / f"{name}.cypher"
    lines = [ln for ln in path.read_text().splitlines() if not ln.lstrip().startswith("//")]
    return "\n".join(lines).strip()


def query_names() -> list[str]:
    return sorted(p.stem for p in QUERIES_DIR.glob("*.cypher"))


@dataclass
class QueryRun:
    name: str
    graph: str
    params: dict
    ms: float
    rows: list[dict]


def run(graph_name: str, name: str, params: dict | None = None, read_only: bool = True) -> QueryRun:
    """Run one named query file. Returns rows as dicts keyed by the RETURN aliases."""
    params = params or {}
    g = db().select_graph(graph_name)
    t0 = time.perf_counter()
    res = (g.ro_query if read_only else g.query)(query_text(name), params, timeout=QUERY_TIMEOUT_MS)
    ms = (time.perf_counter() - t0) * 1000
    header = [h[1] if isinstance(h, (list, tuple)) else h for h in (res.header or [])]
    rows = [dict(zip(header, r)) for r in (res.result_set or [])]
    return QueryRun(name, graph_name, params, round(ms, 2), rows)


def graph_exists(name: str) -> bool:
    return name in db().list_graphs()


def delete_graph(name: str) -> bool:
    """Delete a graph if it exists. Safe when two requests race to delete the same graph."""
    try:
        db().select_graph(name).delete()
        return True
    except ResponseError as e:
        if "empty key" in str(e):
            return False  # already gone
        raise


# ---- packs -------------------------------------------------------------------

def list_packs() -> list[str]:
    return sorted(p.parent.name for p in PACKS_DIR.glob("*/pack.yaml"))


@cache
def load_pack(pack_id: str) -> dict:
    """pack.yaml with the approved rule changes (changes.yaml) applied on top."""
    pack = yaml.safe_load((PACKS_DIR / pack_id / "pack.yaml").read_text())
    return apply_changes(pack, load_changes(PACKS_DIR, pack_id))


def _cite(c: dict | None, prefix: str = "") -> dict:
    c = c or {}
    return {prefix + k: c.get(k) for k in CITE_FIELDS}


def seed_pack(pack_id: str) -> dict:
    """(Re)build the rules graph for one pack from its pack.yaml. Returns node and edge counts."""
    pack = load_pack(pack_id)
    name = rules_graph_name(pack_id)
    delete_graph(name)
    meta = pack["pack"]
    w = lambda q, params=None: run(name, q, params, read_only=False)
    w("seed_pack", {"id": meta["id"], "name": meta["name"], "jurisdiction": meta["jurisdiction"],
                    "version": str(meta["version"]), "tz": meta.get("timezone", "UTC")})
    w("seed_offices", {"rows": [{"id": o["id"], "name": o["name"], "level": o.get("level")}
                                for o in pack.get("offices", [])]})
    docs = []
    for d in pack.get("documents", []):
        row = {"id": d["id"], "name": d["name"], "days": d.get("days"), "validity": d.get("validity"),
               "office": d.get("office"), "note": d.get("note")}
        row.update(_cite(d.get("days_cite"), "days_"))
        row["service_days"] = d.get("service_days")
        row["days_unit"] = d.get("days_unit")
        row.update(_cite(d.get("service_days_cite"), "service_days_"))
        docs.append(row)
    w("seed_documents", {"rows": docs})
    w("seed_anyof", {"rows": [{"id": a["id"], "label": a["label"]} for a in pack.get("any_of", [])]})
    schemes = []
    for s in pack.get("schemes", []):
        win = s.get("window") or {}
        row = {"id": s["id"], "name": s["name"], "authority": s.get("authority"), "portal": s.get("portal"),
               "note": s.get("note"), "window_start": _iso(win.get("start")), "window_end": _iso(win.get("end")),
               "window_year": win.get("year"), "window_is_last_published": bool(win.get("is_last_published")),
               "window_note": win.get("note"), "window_renewals_only": bool(win.get("renewals_only"))}
        row.update(_cite(win.get("cite"), "window_"))
        schemes.append(row)
    w("seed_schemes", {"rows": schemes})
    for stmt in query_text("seed_indexes").split(";"):
        db().select_graph(name).query(stmt.strip())
    rules = []
    for r in pack.get("rules", []):
        row = {"src": r["from"], "dst": r["to"], "kind": r["kind"], "note": r.get("note"),
               "condition": r.get("condition")}
        row.update(_cite(r["cite"]))
        rules.append(row)
    w("seed_requires", {"rows": [r for r in rules if r["kind"] == "REQUIRES"]})
    w("seed_option", {"rows": [r for r in rules if r["kind"] == "OPTION"]})
    issues = []
    for d in pack.get("documents", []):
        if d.get("office") and d.get("office_cite"):
            row = {"office": d["office"], "doc": d["id"], "days": d.get("days"),
                   "days_source_url": (d.get("days_cite") or {}).get("source_url")}
            row.update(_cite(d["office_cite"]))
            issues.append(row)
    w("seed_issues", {"rows": issues})
    stats = run(name, "graph_stats").rows
    return {"graph": name,
            "nodes": {r["name"]: r["n"] for r in stats if r["kind"] == "node"},
            "edges": {r["name"]: r["n"] for r in stats if r["kind"] == "edge"}}


def _iso(v) -> str | None:
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v else None)
