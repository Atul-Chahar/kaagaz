"""Optional LLM layer.

The LLM does exactly two jobs:
1. turn a free-text question into ONE call from the fixed tool catalogue (it never writes Cypher), and
2. write one plain sentence about the tool result. That sentence is checked: every scheme or document name it
   mentions must appear in the result, and every number it states must appear in the result. If the check fails,
   the sentence built directly from the result is shown instead.

With no LLM configured, the Ask box is a name search over schemes and documents in the graph, and the matching
tool runs deterministically. Configuration is only through env vars: LLM_PROVIDER (anthropic | openai),
LLM_BASE_URL, LLM_API_KEY, LLM_MODEL. "openai" means any OpenAI-compatible endpoint (OpenAI, Groq, Gemini's
OpenAI-compatible API, a local Ollama).
"""

from __future__ import annotations

import json
import os
import re
import time

import httpx

from .tools import ToolError, Tools, Trace, catalogue

STOP = set("""a an and are as at be by can could do does did for from get got have has how i if in is it its me my
need needed needs of on or should the this to what when where which who why will with would you your am was were
long take takes much many any there their them they we our us about also into than then so not no yes""".split())
GENERIC = {"certificate", "card", "document", "documents", "scheme", "scholarship", "scholarships", "student",
           "students", "post", "matric", "postmatric", "account", "number"}


def config() -> dict:
    return {
        "provider": (os.environ.get("LLM_PROVIDER") or "").strip().lower(),
        "base_url": (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/"),
        "api_key": (os.environ.get("LLM_API_KEY") or "").strip(),
        "model": (os.environ.get("LLM_MODEL") or "").strip(),
    }


def llm_configured() -> bool:
    c = config()
    if c["provider"] not in ("anthropic", "openai") or not c["model"]:
        return False
    # a local OpenAI-compatible server (Ollama) may not need a key, but then it needs a base URL
    return bool(c["api_key"]) or (c["provider"] == "openai" and bool(c["base_url"]))


# ---- provider calls ---------------------------------------------------------------

class LLMError(RuntimeError):
    pass


def _post(url: str, headers: dict, body: dict) -> dict:
    for attempt in range(3):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=90)
        except httpx.HTTPError as e:
            if attempt == 2:
                raise LLMError(f"LLM request failed: {e!r}") from e
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 529) and attempt < 2:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:300]}")
        return r.json()
    raise LLMError("LLM request failed")


def complete(system: str, user: str, max_tokens: int = 600) -> str:
    """Plain text completion, used for the summary sentence and by the benchmark."""
    c = config()
    if c["provider"] == "anthropic":
        data = _post(f"{c['base_url'] or 'https://api.anthropic.com'}/v1/messages",
                     {"x-api-key": c["api_key"], "anthropic-version": "2023-06-01"},
                     {"model": c["model"], "max_tokens": max_tokens, "system": system,
                      "messages": [{"role": "user", "content": user}]})
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
    data = _post(f"{c['base_url'] or 'https://api.openai.com/v1'}/chat/completions",
                 {"Authorization": f"Bearer {c['api_key']}"} if c["api_key"] else {},
                 {"model": c["model"], "max_tokens": max_tokens,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    return (data["choices"][0]["message"].get("content") or "").strip()


def choose_tool(question: str, context: str) -> tuple[str, dict]:
    """Ask the model to pick exactly one tool from the catalogue."""
    c = config()
    tools = catalogue()
    system = ("You route a student's question about scholarship documents to exactly one tool. "
              "Use ids from the context when they fit. Never answer directly. " + context)
    if c["provider"] == "anthropic":
        data = _post(f"{c['base_url'] or 'https://api.anthropic.com'}/v1/messages",
                     {"x-api-key": c["api_key"], "anthropic-version": "2023-06-01"},
                     {"model": c["model"], "max_tokens": 400, "system": system,
                      "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
                                for t in tools],
                      "tool_choice": {"type": "any"},
                      "messages": [{"role": "user", "content": question}]})
        for b in data.get("content", []):
            if b.get("type") == "tool_use":
                return b["name"], b.get("input") or {}
        raise LLMError("model did not call a tool")
    data = _post(f"{c['base_url'] or 'https://api.openai.com/v1'}/chat/completions",
                 {"Authorization": f"Bearer {c['api_key']}"} if c["api_key"] else {},
                 {"model": c["model"], "max_tokens": 400, "tool_choice": "required",
                  "tools": [{"type": "function", "function": t} for t in tools],
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": question}]})
    calls = data["choices"][0]["message"].get("tool_calls") or []
    if not calls:
        raise LLMError("model did not call a tool")
    fn = calls[0]["function"]
    return fn["name"], json.loads(fn.get("arguments") or "{}")


# ---- sentence checker -------------------------------------------------------------

NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")


def _numbers(obj) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        out.add(str(int(obj)) if float(obj).is_integer() else str(obj))
        return out
    if isinstance(obj, str):
        for m in re.findall(r"\d+(?:\.\d+)?", obj):
            out.add(m.lstrip("0") or "0")
        return out
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _numbers(v)
    return out


def check_sentence(sentence: str, result: dict, known_names: list[str]) -> dict:
    """Return {"ok": bool, "problems": [...]} for a model-written sentence about a tool result."""
    problems = []
    blob = json.dumps(result, ensure_ascii=False).lower()
    low = sentence.lower()
    for name in sorted(set(known_names), key=len, reverse=True):
        n = name.lower().strip()
        if len(n) >= 4 and n in low and n not in blob:
            problems.append(f"names {name!r}, which is not in the tool result")
    allowed = _numbers(result)
    for m in NUM.findall(sentence):
        norm = m.lstrip("0") or "0"
        norm = norm.removesuffix(".0")
        if norm not in allowed:
            problems.append(f"states the number {m}, which is not in the tool result")
    if not sentence.strip():
        problems.append("empty sentence")
    if "—" in sentence:
        problems.append("uses an em dash")
    return {"ok": not problems, "problems": problems}


# ---- ask ----------------------------------------------------------------------------

def _words(q: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", q.lower()) if len(w) >= 3 and w not in STOP]


def name_search_route(t: Tools, question: str, student_id: str | None, scheme_id: str | None,
                      trace: Trace) -> tuple[str, dict, list[dict]]:
    """Deterministic routing with no LLM: find scheme and document names in the question."""
    words = _words(question)
    specific = [w for w in words if w not in GENERIC]
    if not specific:
        return "resolve", {"name": question.strip()[:200]}, []
    hits = t._q("search_names", {"words": specific, "limit": 25}, trace)
    for h in hits:  # generic words only break ties
        h["score"] = h["hits"] + 0.1 * sum(1 for w in words if w in GENERIC and w in h["name"].lower())
    schemes = sorted([h for h in hits if h["label"] == "Scheme"], key=lambda h: -h["score"])
    docs = sorted([h for h in hits if h["label"] == "Document"], key=lambda h: -h["score"])
    scheme = None
    if schemes:
        best = schemes[0]["score"]
        tied = [s for s in schemes if s["score"] == best]
        scheme = next((s for s in tied if s["id"] == scheme_id), tied[0])
    doc = docs[0] if docs else None
    if doc and (scheme or scheme_id):
        return "explain", {"scheme_id": scheme["id"] if scheme else scheme_id, "doc_id": doc["id"]}, hits
    if scheme:
        if student_id:
            return "plan", {"student_id": student_id, "scheme_id": scheme["id"]}, hits
        return "prerequisites", {"scheme_id": scheme["id"], "depth": 8}, hits
    if doc:
        return "resolve", {"name": doc["name"]}, hits
    return "resolve", {"name": question.strip()[:200]}, hits


def ask(t: Tools, question: str, student_id: str | None, scheme_id: str | None) -> dict:
    trace = Trace()
    mode = "llm" if llm_configured() else "name_search"
    route_error = None
    hits: list[dict] = []
    if mode == "llm":
        ctx = f"Context: student_id={student_id or 'none'}, current scheme_id={scheme_id or 'none'}."
        try:
            name, args = choose_tool(question, ctx)
        except (LLMError, KeyError, ValueError) as e:
            route_error = str(e)
            mode = "name_search"
    if mode == "name_search":
        name, args, hits = name_search_route(t, question, student_id, scheme_id, trace)
    try:
        res = t.call(name, args, trace)
    except ToolError as e:
        return {"mode": mode, "question": question, "tool": name, "args": args, "outcome": "unknown_name",
                "answer": f"That question could not be turned into a valid tool call ({e}).",
                "answer_source": "built_from_result", "trace": trace.rows, "data": None}
    answer, source, check = res.message, "built_from_result", None
    if mode == "llm":
        compact = {"outcome": res.outcome, "message": res.message, "data": _compact(res.data)}
        try:
            sentence = complete("Write ONE plain sentence (under 35 words) answering the student, using only "
                                "facts in this JSON. No em dashes. No numbers that are not in the JSON.",
                                f"Question: {question}\nTool result: {json.dumps(compact)[:6000]}", 120)
            names = [d["name"] for d in t.pack["documents"]] + [s["name"] for s in t.pack["schemes"]]
            check = check_sentence(sentence, compact, names)
            if check["ok"]:
                answer, source = sentence, "llm_checked"
            else:
                source = "built_from_result_after_failed_check"
        except LLMError as e:
            check = {"ok": False, "problems": [str(e)]}
    return {"mode": mode, "question": question, "tool": name, "args": args, "outcome": res.outcome,
            "answer": answer, "answer_source": source, "check": check, "route_error": route_error,
            "search_hits": hits[:8], "data": _compact(res.data), "trace": trace.rows}


def _compact(data: dict) -> dict:
    """Trim a tool result to what the Ask screen and the summary need."""
    d = dict(data)
    if "items" in d:
        d["items"] = [{k: i.get(k) for k in ("id", "name", "label", "days", "depth", "held", "needed", "on_critical")}
                      for i in d["items"]]
    d.pop("chain_check", None)
    return d
