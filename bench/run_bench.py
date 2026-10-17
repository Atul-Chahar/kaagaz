"""Kaagaz benchmark (spec section 6).

Three systems, same model:
  llm_alone  - the model answers from its own knowledge
  plain_rag  - BM25 over the same saved source text (top 8 chunks), then the model answers
  kaagaz     - the model picks ONE tool from the catalogue, the tool runs on FalkorDB, the answer is read from the result

Metrics: document recall, invented documents (named but not required), verdict accuracy, first-step accuracy.

    uv run python ../bench/run_bench.py                  # needs LLM_PROVIDER / LLM_API_KEY / LLM_MODEL; writes results/<ts>.json
    uv run python ../bench/run_bench.py --deterministic  # no LLM: Kaagaz's planner answers from the structured question

With no LLM configured the LLM benchmark does not run and writes nothing. Nothing here ever invents a score.
Run from backend/ (so the kaagaz package and its env are available).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
sys.path.insert(0, str(ROOT / "backend"))

from kaagaz import agent, memory
from kaagaz.planner import MAX_DEPTH, Planner, verdict
from kaagaz.tools import Tools, Trace

PACK = "in-ka-scholarships"
STOP = {"the", "a", "an", "of", "for", "and", "or", "in", "on", "to", "by", "with", "from", "via", "your", "card",
        "certificate", "karnataka", "number", "document", "documents"}


# ---- questions and scoring ---------------------------------------------------------

def load_questions() -> list[dict]:
    return [json.loads(line) for line in (BENCH / "questions.jsonl").read_text().splitlines() if line.strip()]


def tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def match_names(names: list[str], docs: list[dict]) -> tuple[list[str], list[str]]:
    """Map free-text document names to pack ids by token overlap. Returns (matched ids, unmatched names)."""
    ids, unmatched = [], []
    for n in names:
        tn = tokens(n)
        best, score = None, 0.0
        for d in docs:
            td = tokens(d["name"]) | tokens(d["id"].replace("-", " "))
            if not tn or not td:
                continue
            j = len(tn & td) / len(tn | td)
            if j > score:
                best, score = d["id"], j
        if best and score >= 0.34:
            ids.append(best)
        else:
            unmatched.append(n)
    return ids, unmatched


def score_list(pred: set[str], unmatched: int, truth: dict) -> tuple[float, int]:
    required = set(truth.get("required", []))
    groups = [set(g) for g in truth.get("any_of", [])]
    total = len(required) + len(groups)
    hit = len(required & pred) + sum(1 for g in groups if g & pred)
    allowed = required.union(*groups) if groups else required
    invented = len(pred - allowed) + unmatched
    return (hit / total if total else 1.0), invented


def score(system: str, answers: list[dict], questions: list[dict]) -> dict:
    recall, invented, verdict_ok, first_ok = [], [], [], []
    for q, a in zip(questions, answers, strict=True):
        if q["type"] == "list_documents":
            r, inv = score_list(set(a.get("doc_ids", [])), len(a.get("unmatched", [])), q["truth"])
            recall.append(r)
            invented.append(inv)
        elif q["type"] == "first_step":
            ok = {q["truth"]["first_step"], *q["truth"].get("acceptable", [])}
            first_ok.append(1.0 if a.get("first_step") in ok else 0.0)
        elif q["type"] == "deadline":
            verdict_ok.append(1.0 if a.get("verdict") == q["truth"]["verdict"] else 0.0)

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    return {"system": system, "document_recall": mean(recall), "invented_documents": mean(invented),
            "verdict_accuracy": mean(verdict_ok), "first_step_accuracy": mean(first_ok),
            "n": {"list_documents": len(recall), "first_step": len(first_ok), "deadline": len(verdict_ok)}}


# ---- Kaagaz deterministic answers (planner, no LLM) -------------------------------------

def kaagaz_deterministic(t: Tools, q: dict) -> dict:
    g, _rows, _s = t.build_rule_graph(q["scheme_id"], MAX_DEPTH, Trace())
    held = set(q.get("held", []))
    p = Planner(g, held)
    f = p.finish(q["scheme_id"])
    if q["type"] == "list_documents":
        return {"doc_ids": p.needed()}
    if q["type"] == "first_step":
        plan = t.plan_core("bench-probe", q["scheme_id"], MAX_DEPTH, Trace(), held=held, save=False)
        return {"first_step": plan["start_today"][0]["id"] if plan["start_today"] else None}
    v = verdict(f, q["working_days_left"])
    return {"verdict": {"on_time": "yes", "late": "no", "late_at_least": "no"}.get(v.kind, "cannot_tell"),
            "critical_days": f.lb, "exact": f.exact}


def disagreements(questions: list[dict], answers: list[dict]) -> list[dict]:
    """Where the graph's answer differs from the source-written ground truth (the "checked against the graph" step)."""
    out = []
    for q, a in zip(questions, answers, strict=True):
        if q["type"] == "list_documents":
            r, inv = score_list(set(a["doc_ids"]), 0, q["truth"])
            if r < 1 or inv:
                required = set(q["truth"].get("required", []))
                groups = [set(g) for g in q["truth"].get("any_of", [])]
                allowed = required.union(*groups) if groups else required
                out.append({"id": q["id"], "missing": sorted(required - set(a["doc_ids"])),
                            "extra_in_graph": sorted(set(a["doc_ids"]) - allowed)})
        elif q["type"] == "first_step":
            ok = {q["truth"]["first_step"], *q["truth"].get("acceptable", [])}
            if a["first_step"] not in ok:
                out.append({"id": q["id"], "truth": sorted(ok), "graph": a["first_step"]})
        elif a["verdict"] != q["truth"]["verdict"]:
            out.append({"id": q["id"], "truth": q["truth"], "graph": a})
    return out


# ---- LLM systems --------------------------------------------------------------------------

ANSWER_SPEC = ('Answer ONLY with JSON: {"documents": [names of every document needed, including documents needed to '
               'get them] , "first_step": "name of the document to apply for first or null", "verdict": "yes" | "no" '
               '| "cannot_tell"}. Fill only the field the question asks for; use null or [] for the others. '
               'Processing times in Karnataka are counted in working days.')


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


def to_answer(q: dict, raw: dict, docs: list[dict]) -> dict:
    if q["type"] == "list_documents":
        ids, un = match_names([str(x) for x in raw.get("documents") or []], docs)
        return {"doc_ids": sorted(set(ids)), "unmatched": un}
    if q["type"] == "first_step":
        fs = raw.get("first_step")
        ids, _ = match_names([str(fs)], docs) if fs else ([], [])
        return {"first_step": ids[0] if ids else None}
    v = str(raw.get("verdict") or "").lower().replace(" ", "_").replace("'", "")
    return {"verdict": v if v in ("yes", "no", "cannot_tell") else None}


class BM25Index:
    def __init__(self):
        from rank_bm25 import BM25Okapi
        idx = json.loads((ROOT / "data/sources/index.json").read_text())
        self.chunks: list[tuple[str, str]] = []
        for s in idx:
            words = (ROOT / "data/sources" / s["text_file"]).read_text().split()
            for i in range(0, len(words), 120):
                self.chunks.append((s["id"], " ".join(words[i:i + 160])))
        self.bm25 = BM25Okapi([re.findall(r"[a-z0-9]+", c.lower()) for _, c in self.chunks])

    def top(self, q: str, k: int = 8) -> list[tuple[str, str]]:
        scores = self.bm25.get_scores(re.findall(r"[a-z0-9]+", q.lower()))
        best = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [self.chunks[i] for i in best]


def question_text(q: dict) -> str:
    return q["question"]


def kaagaz_llm(t: Tools, q: dict) -> tuple[dict, dict]:
    """The model routes the question to one tool; the answer is read from the tool's result."""
    sid = f"bench-{q['id'].lower()}"
    memory.reset(sid)
    memory.ensure_student(sid, "Benchmark student (synthetic)")
    for h in q.get("held", []):
        memory.add_holding(sid, h, None)
    deadline = None
    if q["type"] == "deadline":
        deadline = t.calendar.date_of(t.today(), q["working_days_left"]).isoformat()
    memory.set_target(sid, q["scheme_id"], deadline, "student" if deadline else "published_window")
    schemes = ", ".join(f"{s['id']} = {s['name']}" for s in t.pack["schemes"])
    ctx = (f"Context: student_id={sid}. The student's holdings and deadline are already saved in memory. "
           f"Scheme ids: {schemes}.")
    raw = {"route": None}
    try:
        name, args = agent.choose_tool(question_text(q), ctx)
        raw["route"] = {"tool": name, "args": args}
        res = t.call(name, args)
    except Exception as e:  # noqa: BLE001 - a routing failure is an honest wrong answer
        raw["error"] = repr(e)
        memory.reset(sid)
        return {}, raw
    d = res.data
    ans: dict = {}
    if name == "plan":
        ans = {"doc_ids": d.get("needed", []),
               "first_step": d["start_today"][0]["id"] if d.get("start_today") else None,
               "verdict": {"on_time": "yes", "late": "no", "late_at_least": "no"}.get(d["verdict"]["kind"],
                                                                                    "cannot_tell")}
    elif name == "prerequisites":
        ans = {"doc_ids": [n["id"] for n in d.get("nodes", []) if n["label"] == "Document"]}
    elif name == "explain":
        ans = {"doc_ids": [n["id"] for p in d.get("paths", [])[:1] for n in p["nodes"] if n["label"] == "Document"]}
    raw["outcome"] = res.outcome
    memory.reset(sid)
    return ans, raw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deterministic", action="store_true", help="score Kaagaz's planner alone (no LLM)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not args.deterministic and not agent.llm_configured():
        print("Benchmark not run: no LLM configured. Set LLM_PROVIDER, LLM_API_KEY and LLM_MODEL (see .env.example), "
              "then run `make bench`. No results file was written.")
        return 2
    questions = load_questions()
    if args.limit:
        questions = questions[:args.limit]
    t = Tools(PACK)
    docs = [{"id": d["id"], "name": d["name"]} for d in t.pack["documents"]]
    out_dir = BENCH / "results"
    out_dir.mkdir(exist_ok=True)
    started = dt.datetime.now(dt.UTC)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")

    if args.deterministic:
        answers = [kaagaz_deterministic(t, q) for q in questions]
        run = {"kind": "deterministic", "started_at": started.isoformat(timespec="seconds"),
               "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "model": None,
               "questions": len(questions), "pack": PACK, "today": t.today().isoformat(),
               "note": "Kaagaz planner answers from the structured question (scheme id, held ids, working days left); "
                       "no language model. Ground truth and graph come from the same saved sources.",
               "systems": [score("kaagaz_deterministic", answers, questions)],
               "disagreements": disagreements(questions, answers),
               "raw": [{"id": q["id"], "answer": a} for q, a in zip(questions, answers, strict=True)]}
        path = out_dir / f"deterministic-{stamp}.json"
        path.write_text(json.dumps(run, indent=1))
        print(f"wrote {path.relative_to(ROOT)}")
        print(json.dumps(run["systems"], indent=1))
        return 0

    cfg = agent.config()
    rag = BM25Index()
    raw_rows, sys_answers = [], {"llm_alone": [], "plain_rag": [], "kaagaz": []}
    for q in questions:
        row = {"id": q["id"], "question": q["question"]}
        alone = agent.complete("You help Indian students with scholarship paperwork. " + ANSWER_SPEC,
                               question_text(q), 900)
        row["llm_alone"] = alone
        sys_answers["llm_alone"].append(to_answer(q, parse_json(alone), docs))
        ctx = rag.top(q["question"])
        rag_prompt = "Sources:\n" + "\n---\n".join(f"[{sid}] {c}" for sid, c in ctx) + f"\n\nQuestion: {q['question']}"
        rag_out = agent.complete("Answer only from the sources given. " + ANSWER_SPEC, rag_prompt, 900)
        row["plain_rag"] = {"answer": rag_out, "chunks": [sid for sid, _ in ctx]}
        sys_answers["plain_rag"].append(to_answer(q, parse_json(rag_out), docs))
        ans, raw = kaagaz_llm(t, q)
        row["kaagaz"] = raw | {"answer": ans}
        sys_answers["kaagaz"].append(ans)
        raw_rows.append(row)
        time.sleep(0.5)
    run = {"kind": "llm", "started_at": started.isoformat(timespec="seconds"),
           "finished_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
           "model": cfg["model"], "provider": cfg["provider"], "questions": len(questions), "pack": PACK,
           "today": t.today().isoformat(),
           "systems": [score(s, a, questions) for s, a in sys_answers.items()], "raw": raw_rows}
    path = out_dir / f"{stamp}.json"
    path.write_text(json.dumps(run, indent=1))
    print(f"wrote {path.relative_to(ROOT)}")
    print(json.dumps(run["systems"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
