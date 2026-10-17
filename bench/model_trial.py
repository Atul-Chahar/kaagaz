"""Pick an LLM for Kaagaz's Ask box: time real calls on Kaagaz's own two jobs, per candidate model.

For each model and each question: the model must pick the right tool with the right arguments (agent.choose_tool,
the exact code path the app uses), then write one sentence about the real tool result, which must pass
agent.check_sentence. Reports accuracy and median latency. Needs LLM_PROVIDER/LLM_BASE_URL/LLM_API_KEY in the env.

    cd backend && uv run python ../bench/model_trial.py model-a model-b ...
Writes bench/results/model-trial-<timestamp>.json (raw timings and answers, no key).
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import os
import statistics
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parent
sys.path.insert(0, str(BENCH.parent / "backend"))

import httpx

from kaagaz import agent, memory
from kaagaz.tools import Tools

SID = "model-trial-student"
CASES = [
    ("Does PostMatric for OBC Students need a caste and income certificate?",
     "explain", {"scheme_id": "ka-ssp-pms-obc", "doc_id": "caste-income-certificate-ka"}),
    ("Does PM YASASVI Top Class need a hostel certificate?",
     "explain", {"scheme_id": "nsp-pm-yasasvi-top-class-college", "doc_id": "hostel-certificate"}),
    ("What documents do I need for Vidyasiri for Minorities, including the documents needed to get them?",
     ("prerequisites", "plan"), {"scheme_id": "ka-ssp-vidyasiri-minority"}),
    ("Am I going to make the deadline for my scholarship?", "plan", {"scheme_id": "ka-ssp-pms-obc"}),
    ("I just received my caste and income certificate today.", "remember_holding",
     {"doc_id": "caste-income-certificate-ka"}),
    ("What do you remember about me?", "recall", {}),
]


def run_model(model: str, t: Tools) -> dict:
    os.environ["LLM_MODEL"] = model
    rows = []
    for q, want_tool, want_args in CASES:
        ctx = f"Context: student_id={SID}, current scheme_id=ka-ssp-pms-obc. " + agent.id_directory(t)
        row = {"question": q}
        t0 = time.perf_counter()
        try:
            name, args = agent.choose_tool(q, ctx)
            row["route_ms"] = round((time.perf_counter() - t0) * 1000)
            row["tool"], row["args"] = name, args
            tools_ok = name in (want_tool if isinstance(want_tool, tuple) else (want_tool,))
            args_ok = all(args.get(k) == v for k, v in want_args.items())
            row["route_ok"] = tools_ok and args_ok
            res = t.call(name, args)
            compact = {"outcome": res.outcome, "message": res.message, "data": agent._compact(res.data)}
            t1 = time.perf_counter()
            sentence = agent.complete(
                "Write ONE plain sentence (under 35 words) answering the student, using only facts in this JSON. "
                "No em dashes. No numbers that are not in the JSON.",
                f"Question: {q}\nTool result: {json.dumps(compact)[:6000]}", 120)
            row["sentence_ms"] = round((time.perf_counter() - t1) * 1000)
            row["sentence"] = sentence
            names = [d["name"] for d in t.pack["documents"]] + [s["name"] for s in t.pack["schemes"]]
            chk = agent.check_sentence(sentence, compact, names)
            row["sentence_ok"], row["problems"] = chk["ok"], chk["problems"]
        except Exception as e:  # noqa: BLE001 - a failure is a result for this model
            row["error"] = repr(e)[:300]
            row["route_ok"] = row["sentence_ok"] = False
        rows.append(row)
        if name_is_memory_write(row):
            memory.remove_holding(SID, "caste-income-certificate-ka")
    ok_r = [r for r in rows if r.get("route_ms")]
    ok_s = [r for r in rows if r.get("sentence_ms")]
    return {
        "model": model,
        "route_correct": sum(r["route_ok"] for r in rows),
        "sentence_passed": sum(r["sentence_ok"] for r in rows),
        "errors": sum(1 for r in rows if "error" in r),
        "median_route_ms": statistics.median(r["route_ms"] for r in ok_r) if ok_r else None,
        "median_sentence_ms": statistics.median(r["sentence_ms"] for r in ok_s) if ok_s else None,
        "rows": rows,
    }


def name_is_memory_write(row: dict) -> bool:
    return row.get("tool") == "remember_holding"


def main() -> int:
    if len(sys.argv) > 1:
        os.environ["LLM_MODEL"] = sys.argv[1]  # the model is what we are choosing; each run sets its own
    if not agent.llm_configured():
        print("No LLM configured (LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY).")
        return 2
    # fail fast in a trial: 60 s per call, no long retry chains
    agent.httpx.post = functools.partial(httpx.post, timeout=60)
    t = Tools()
    memory.reset(SID)
    memory.ensure_student(SID, "Model trial student (synthetic)")
    memory.add_holding(SID, "aadhaar", None)
    memory.set_target(SID, "ka-ssp-pms-obc", None, "published_window")
    out = []
    for m in sys.argv[1:]:
        r = run_model(m, t)
        out.append(r)
        print(f"{m:48s} route {r['route_correct']}/6  sentence {r['sentence_passed']}/6  errors {r['errors']}  "
              f"route {r['median_route_ms']} ms  sentence {r['median_sentence_ms']} ms", flush=True)
    memory.reset(SID)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    path = BENCH / "results" / f"model-trial-{stamp}.json"
    path.write_text(json.dumps({"date": stamp, "base_url": agent.config()["base_url"], "results": out}, indent=1))
    print("wrote", path.relative_to(BENCH.parent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
