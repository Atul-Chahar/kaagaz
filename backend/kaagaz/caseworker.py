"""Caseworker agent: investigates one student's case through the tool catalogue, decides what to do, and proposes
actions that run only when the student approves them. It also re-plans every student a rule change affects.

review() is a loop over the same seven tools the Ask box uses, where each next step depends on what the last one
returned:

1. recall: what the student holds and targets, and the caseworker's own earlier reviews (its memory of the case)
2. plan: the critical path and the verdict
3. explain: for each step that can start now and has no legal time limit, why it is needed (with its source)
4. alternatives: only when the verdict is late, short or closed: other schemes that reuse the same documents
5. decide: a fixed policy over those results (below), written down with the facts it used
6. propose: tasks with due dates, a plan-B checkpoint, or a switch of target; nothing is written until approved

The decision is code, so it can be tested and explained; a language model (if configured) only writes a short
case note, and that note must pass the same sentence checker as the Ask box.
"""

from __future__ import annotations

import datetime as dt
import json

from . import agent, agents, memory
from .planner import MAX_DEPTH
from .tools import ToolError, Tools, Trace

GOOD = ("on_time",)
UNSURE = ("at_least", "cannot_compute", "no_deadline")
BAD = ("late", "late_at_least", "closed")


def _n(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _step(steps: list, tool: str, why: str, found: str, outcome: str | None = None) -> None:
    steps.append({"n": len(steps) + 1, "tool": tool, "why": why, "found": found, "outcome": outcome})


def _since(t: Tools, prev: dict | None, plan: dict) -> dict | None:
    """What changed since the caseworker last looked at this case (from its own memory, not the student's)."""
    if not prev:
        return None
    before = prev.get("json") or {}
    then = dt.date.fromisoformat(prev["today"]) if prev.get("today") else None
    today = dt.date.fromisoformat(plan["today"])
    passed = t.calendar.days_between(then, today) if then and then < today else 0
    held_then, held_now = set(before.get("held") or []), set(plan["held"])
    return {"last_review": prev["at"], "last_today": prev.get("today"), "working_days_passed": passed,
            "stamp_before": prev.get("stamp"), "stamp_now": plan["verdict"]["stamp"],
            "verdict_before": prev.get("verdict"), "verdict_now": plan["verdict"]["kind"],
            "new_holdings": sorted(held_now - held_then), "dropped_holdings": sorted(held_then - held_now),
            "scheme_changed": prev.get("scheme_id") != plan["scheme"]["id"]}


def review(t: Tools, student_id: str, scheme_id: str | None = None, narrate: bool = True, as_of: bool = False) -> dict:
    """as_of: the plan is counted from a chosen date (the submission-day view). The review is kept but labelled,
    the plan is not saved as a snapshot, and "since last review" only compares reviews of the same kind."""
    trace = Trace()
    steps: list[dict] = []
    rec = t.call("recall", {"student_id": student_id}, trace)
    if rec.outcome == "not_in_graph":
        raise ToolError("Kaagaz has no saved memory for this student yet")
    targets = rec.data.get("targets") or []
    prev = next((c for c in memory.cases(student_id, 10, trace) if bool((c.get("json") or {}).get("as_of")) == as_of),
                None)
    scheme_id = scheme_id or (targets[0]["scheme_id"] if targets else None)
    _step(steps, "recall", "Start from what the student told Kaagaz and what I found last time",
          f"{_n(len(rec.data.get('holdings') or []), 'document', 'documents')} held, {_n(len(targets), 'target', 'targets')}"
          + (f"; my last review was on {prev['at'][:10]}" if prev else "; no earlier review"), rec.outcome)
    if not scheme_id:
        raise ToolError("the student has no target scheme yet; pick one on the Start screen first")

    plan_res = t.call("plan", {"student_id": student_id, "scheme_id": scheme_id, "depth": MAX_DEPTH,
                               "remember": not as_of}, trace)
    if plan_res.outcome == "unknown_name":
        raise ToolError(f"unknown scheme {scheme_id}")
    plan = plan_res.data
    v = plan["verdict"]
    _step(steps, "plan", "Walk every chain under the scheme at full depth and count the legal days",
          f"{v['stamp']}: the longest chain is {'at least ' if not v['exact'] else ''}{v['critical_days']} "
          f"{plan['day_unit']}; {plan['days_left'] if plan['days_left'] is not None else 'no'} left before the "
          f"deadline", plan_res.outcome)

    ready = plan["start_today"]
    options = {o for i in plan["items"] if i["label"] == "AnyOf" for o in (i.get("options") or [])}
    unknown_ready = [s for s in ready if s["days"] is None and s["id"] not in options]
    for s in unknown_ready[:3]:
        ex = t.call("explain", {"scheme_id": scheme_id, "doc_id": s["id"]}, trace)
        paths = ex.data.get("paths") or []
        hop = (paths[0]["rules"][-1] if paths and paths[0]["rules"] else {}) or {}
        _step(steps, "explain", f"{s['name']} can start now but has no legal time limit; check why it is needed",
              f"“{hop.get('excerpt', '')}” ({hop.get('source_title', 'no source')})", ex.outcome)

    alt = None
    if v["kind"] in BAD or (v["kind"] in UNSURE and v["kind"] != "no_deadline"):
        al = t.call("alternatives", {"student_id": student_id, "scheme_id": scheme_id}, trace)
        opts = al.data.get("options") or []
        good = [o for o in opts if o["verdict"]["kind"] == "on_time"]
        # prefer the option that reuses the most of what the student is already applying for, then the most spare
        good.sort(key=lambda o: (-o["shared_count"], -(o["verdict"]["margin"] or 0), o["scheme_id"]))
        alt = good[0] if good else None
        _step(steps, "alternatives", "The verdict is not a clear yes, so look for schemes that can still be made",
              f"{_n(len(good), 'other scheme', 'other schemes')} can be made; " + (
                  f"best fit: {alt['name']} ({alt['verdict']['stamp']}, shares {_n(alt['shared_count'], 'document', 'documents')})"
                  if alt else "none can be made with the documents needed"), al.outcome)

    today = dt.date.fromisoformat(plan["today"])
    deadline = plan["deadline"].get("date")
    margin = v["margin"] if v["kind"] == "on_time" else None
    proposals: list[dict] = []

    def task(kind: str, doc: dict | None, title: str, due: dt.date | str | None, reason: str) -> None:
        proposals.append({"id": f"p{len(proposals) + 1}", "kind": kind, "title": title,
                          "doc_id": doc["id"] if doc else None, "scheme_id": scheme_id,
                          "due": due.isoformat() if isinstance(due, dt.date) else due, "reason": reason})

    # an "any one of" group needs one of its options, so its ready options become one step
    group_of = {o: i for i in plan["items"] if i["label"] == "AnyOf" for o in (i.get("options") or [])}
    steps_now: list[dict] = []
    seen_groups: set[str] = set()
    for s in ready:
        g = group_of.get(s["id"])
        if g is None:
            steps_now.append(s | {"verb": "Apply for" if s["days"] is not None else "Gather"})
        elif g["id"] not in seen_groups:
            seen_groups.add(g["id"])
            opts = [r for r in ready if group_of.get(r["id"], {}).get("id") == g["id"]]
            timed = [o for o in opts if o["days"] is not None]
            pick = min(timed, key=lambda o: o["days"]) if timed else None
            steps_now.append({"id": pick["id"] if pick else opts[0]["id"], "days": pick["days"] if pick else None,
                              "name": ("one of: " + ", ".join(o["name"] for o in opts)) if len(opts) > 1 else
                              f"{opts[0]['name']} (or another document the same list accepts)", "verb": "Get"})
    ready = steps_now

    if v["kind"] == "closed":
        decision = {"kind": "switch", "text": (
            f"The window for {plan['scheme']['name']} has closed. "
            + (f"Switch to {alt['name']}: {alt['verdict']['stamp'].lower()}, and it reuses "
               f"{alt['shared_count']} of the documents." if alt else "No other scheme in this pack can be made "
               "with the documents still needed."))}
        if alt:
            proposals.append({"id": "p1", "kind": "switch_target", "title": f"Switch my target to {alt['name']}",
                              "doc_id": None, "scheme_id": alt["scheme_id"], "due": today.isoformat(),
                              "reason": f"{plan['scheme']['name']} is closed; {alt['name']} is "
                                        f"{alt['verdict']['stamp'].lower()}"})
    elif v["kind"] in GOOD:
        latest = t.calendar.date_of(today, margin) if margin is not None else today
        decision = {"kind": "on_track", "text": (
            f"On time with {margin} {plan['day_unit']} spare, if every step starts by {latest.isoformat()}. "
            f"Start the {'step' if len(ready) == 1 else f'{len(ready)} steps'} that can begin now.")}
        for s in ready:
            task("apply", s, f"{s['verb']} {s['name']}", latest if s["days"] is not None else today,
                 (f"Legal time {s['days']} {plan['day_unit']}; the plan has {margin} spare, so starting later than "
                  f"{latest.isoformat()} makes it late") if s["days"] is not None else
                 "No legal time limit, so start now; Kaagaz cannot tell how long it takes")
    elif v["kind"] in UNSURE:
        decision = {"kind": "start_unknowns", "text": (
            f"Kaagaz can't promise this one: {_n(len(plan['unknown']), 'step has', 'steps have')} no legal time limit. Start every "
            "step that can begin now today, the unknown ones first."
            + (f" Keep {alt['name']} in mind ({alt['verdict']['stamp'].lower()})." if alt else ""))}
        for s in sorted(ready, key=lambda s: s["days"] is not None):
            task("apply" if s["days"] is not None else "gather", s, f"{s['verb']} {s['name']}", today,
                 "No legal time limit; it decides whether the plan works" if s["days"] is None else
                 f"Legal time {s['days']} {plan['day_unit']} on a chain Kaagaz can't fully time")
    else:
        short = v["margin"] or 0
        crit_doc = next((plan["items"][i] for i, it in enumerate(plan["items"])
                         if it["id"] in plan["critical_path"] and it["label"] == "Document" and it["needed"]), None)
        decision = {"kind": "plan_b", "text": (
            f"The law lets the offices take {'at least ' if not v['exact'] else ''}{v['critical_days']} "
            f"{plan['day_unit']}, and {plan['days_left']} are left, so this is {short} short if every office uses "
            "its full time. Apply today anyway, since offices can be faster than the limit"
            + (f", and keep {alt['name']} as plan B: {alt['verdict']['stamp'].lower()}, reusing "
               f"{_n(alt['shared_count'], 'document', 'documents')}." if alt else ". No other scheme in this pack can be made."))}
        for s in ready:
            task("apply" if s["days"] is not None else "gather", s, f"{s['verb']} {s['name']} today", today,
                 "Every working day counts: the plan is already short")
        if alt and crit_doc and deadline:
            proposals.append({"id": f"p{len(proposals) + 1}", "kind": "checkpoint",
                              "title": f"If {crit_doc['name']} is not in hand by {deadline}, apply for {alt['name']}",
                              "doc_id": crit_doc["id"], "scheme_id": alt["scheme_id"], "due": deadline,
                              "reason": f"{alt['name']} closes on {alt['deadline'].get('date')} and reuses "
                                        f"{alt['shared_count']} of the documents"})
            proposals.append({"id": f"p{len(proposals) + 1}", "kind": "switch_target",
                              "title": f"Switch my target to {alt['name']} now", "doc_id": None,
                              "scheme_id": alt["scheme_id"], "due": today.isoformat(),
                              "reason": f"{alt['name']} is {alt['verdict']['stamp'].lower()}"})
    _step(steps, "decide", "Apply the caseworker's policy to what the tools returned", decision["text"])

    since = _since(t, prev, plan)
    case_id = agents.new_id("case")
    for p in proposals:
        p["id"] = f"{case_id}-{p['id']}"
    note = None
    if narrate and agent.llm_configured():
        note = _note(t, plan, decision, since)
    body = {"steps": steps, "decision": decision, "since": since, "held": plan["held"], "note": note, "as_of": as_of,
            "alternative": {"scheme_id": alt["scheme_id"], "name": alt["name"], "stamp": alt["verdict"]["stamp"]}
            if alt else None}
    memory.add_case(student_id, {"id": case_id, "scheme_id": scheme_id, "today": plan["today"], "verdict": v["kind"],
                                 "stamp": v["stamp"], "critical_days": v["critical_days"],
                                 "days_left": plan["days_left"], "decision": decision["kind"],
                                 "json": json.dumps(body)}, trace)
    memory.add_proposals(student_id, case_id, proposals, trace)
    _step(steps, "propose", "Write the proposed actions to the student's graph; none runs until approved",
          f"{_n(len(proposals), 'proposal', 'proposals')} waiting for the student")
    return {"case_id": case_id, "scheme": {"id": scheme_id, "name": plan["scheme"]["name"]}, "today": plan["today"],
            "as_of": as_of,
            "verdict": v, "decision": decision, "since": since, "steps": steps,
            "proposals": memory.proposals(student_id, 30),
            "note": note, "trace": trace.rows}


def _note(t: Tools, plan: dict, decision: dict, since: dict | None) -> dict | None:
    facts = {"scheme": plan["scheme"]["name"], "verdict": plan["verdict"], "days_left": plan["days_left"],
             "day_unit": plan["day_unit"],
             "deadline": plan["deadline"].get("date"), "decision": decision["text"], "since": since}
    try:
        text = agent.complete(
            "You write one or two plain sentences to a student about their scholarship paperwork. Use only the "
            "facts given. Day counts are in the unit given as day_unit; always name that unit. No advice beyond "
            "the decision. No greetings.", json.dumps(facts), max_tokens=400).strip()
    except agent.LLMError as e:  # the note is optional; the decision stands without it
        return {"text": None, "ok": False, "problems": [f"model call failed: {type(e).__name__}"]}
    known = [i["name"] for i in plan["items"]] + [plan["scheme"]["name"]]
    check = agent.check_sentence(text, {"plan": plan, "decision": decision, "since": since}, known)
    return {"text": text if check["ok"] else None, "ok": check["ok"], "problems": check["problems"]}


def act(t: Tools, student_id: str, proposal_id: str, approve: bool, as_of: bool = False) -> dict:
    """The student approves or rejects one proposal. Approved: the caseworker carries it out, then checks the plan
    again so the student sees the effect."""
    p = memory.decide_proposal(student_id, proposal_id, "approved" if approve else "rejected")
    if p is None:
        raise ToolError("no pending proposal with that id")
    result = {"proposal": p, "done": None}
    if approve:
        if p["kind"] == "switch_target":
            memory.set_target(student_id, p["scheme_id"], None, "published_window", pack=t.pack_id)
            result["done"] = {"target": p["scheme_id"]}
        else:
            tid = f"t-{p['kind']}-{p.get('doc_id') or 'x'}-{p['scheme_id']}"
            result["done"] = {"task": memory.add_task(student_id, {
                "id": tid, "kind": p["kind"], "title": p["title"], "doc_id": p.get("doc_id"),
                "scheme_id": p["scheme_id"], "due": p.get("due"), "reason": p.get("reason"),
                "from_proposal": p["id"]})}
        tgt = p["scheme_id"] if p["kind"] == "switch_target" else (
            memory.targets(student_id)[0]["scheme_id"] if memory.targets(student_id) else p["scheme_id"])
        after = t.call("plan", {"student_id": student_id, "scheme_id": tgt, "depth": MAX_DEPTH,
                                "remember": not as_of})
        result["plan_after"] = {"scheme_id": tgt, "stamp": after.data["verdict"]["stamp"],
                                "kind": after.data["verdict"]["kind"]}
    return result


def propagate(pack: str) -> dict:
    """After a person approves a rule change: re-plan every student whose target scheme it affects and leave each
    an alert in their own graph. Uses the caseworker's cursor in the agents graph, so each approval is handled
    once even if this runs twice."""
    agents.ensure()
    run_id = agents.start_run("caseworker", pack, "approved_finding")
    me = next(a for a in agents.overview() if a["id"] == "caseworker")
    cursor = me.get("cursor") or ""
    t = Tools(pack)
    notified = []
    newest = cursor
    for row in agents.q("agents_approved_since", {"cursor": cursor}):
        f = dict(row["finding"])
        if f.get("pack") != pack:
            continue
        newest = max(newest, f["decided_at"])
        for s in agents.q("agents_affected_students", {"id": f["id"]}):
            sid, scheme = s["student_id"], s["scheme_id"]
            if not memory.exists(sid):
                continue
            last = memory.last_snapshot(sid, scheme)
            before = last["json"].get("stamp") if last else None
            after = t.plan_core(sid, scheme, MAX_DEPTH, Trace())["verdict"]["stamp"]
            what = (f"its last date changed from {f.get('old_value')} to {f.get('new_value')}"
                    if f["kind"] == "date_changed" else
                    "a rule's source page was reworded; the rule now cites the new sentence"
                    if f["kind"] == "wording_changed" else
                    "a rule's source sentence is no longer on its page; the rule is kept and marked for review")
            memory.add_alert(sid, {"id": f"alert-{f['id']}-{scheme}", "kind": f["kind"], "scheme_id": scheme,
                                   "finding_id": f["id"], "before": before, "after": after,
                                   "message": f"A source for {t._need(scheme, 'Scheme', Trace())['name']} changed: "
                                              f"{what}. Your plan " + (f"was {before}, and is now {after}."
                                                                      if before else f"is now {after}.")})
            agents.q("agents_notified", {"finding_id": f["id"], "now": agents.now_iso(), "student_id": sid,
                                         "before": before, "after": after}, write=True)
            notified.append({"student_id": sid, "scheme_id": scheme, "finding_id": f["id"], "before": before,
                             "after": after})
    if newest != cursor:
        agents.q("agents_cursor_set", {"id": "caseworker", "cursor": newest}, write=True)
    agents.finish_run(run_id, "done", {"students_alerted": len(notified)})
    return {"run_id": run_id, "notified": notified}
