# Kaagaz: final report

Date: 17 Oct 2026, 3:45 PM IST. Repo: https://github.com/Atul-Chahar/kaagaz (private; you make it public).

> Every scheme finder tells a student what they are eligible for. Kaagaz tells them whether they are already too late,
> and which certificate to apply for today.

## Latest verify.sh result

`bash scripts/verify.sh`, run after the last code change (17 Oct 2026, 3:45 PM IST), exit code 0:

```
--> ok: start FalkorDB (docker compose)
--> ok: seed rule packs
audit: 2 pack(s); checked 173 requirement rules, 9 processing times, 11 windows, 28 issuing offices, 8 calendar facts, 60 sources
--> ok: data audit
--> ok: backend lint
61 passed, 33 deselected      --> ok: backend unit tests
33 passed, 61 deselected      --> ok: integration tests (real FalkorDB)
--> ok: frontend typecheck / frontend lint / frontend production build
15 passed                     --> ok: end-to-end + accessibility (Playwright, axe)
32 passed                     --> ok: screenshots (1440/390, light/dark)
--> ok: docker image builds
VERIFY: ALL CHECKS PASSED
```

## What works (with the evidence that proves it)

| Feature | Evidence |
|---|---|
| Real rule pack: 11 Karnataka and central scholarships, 41 documents, 143 sourced rules, real 2026-27 deadlines | `data/packs/in-ka-scholarships/pack.yaml`; `scripts/audit_data.py` checks every excerpt is in the saved source text and every hash matches (audit OK above); 6 tests prove the audit fails on bad data |
| Requirement graph in FalkorDB, walked at every depth | `prerequisites.cypher`; integration test checks depth 1 equals the direct rules and that results grow with depth |
| Critical path and verdict in working days on the official Karnataka calendar | `planner.py`, `workdays.py`; 20 planner and 7 working-day calendar unit tests incl. deadline today, past deadlines, unknown days, mixed units; `chain_days.cypher` agrees with the planner on 100+ cases (integration test) |
| Honest unknowns: null days give lower bounds ("AT LEAST 21 DAYS"), never guesses | planner tests; e2e checks the depth-2 stamp says "AT LEAST" |
| The demo moment: depth 1 "ON TIME · 9 DAYS SPARE", depth 2 "AT LEAST 21 DAYS" | e2e test steps depth 1 to max and checks every stamp equals the API's |
| Red "12 DAYS SHORT" for schemes closing 31 Oct 2026 (21 working days needed, 9 left) | screenshot `docs/screenshots/chain-late-1440-light.png`; reviewer recomputed it independently |
| Start today list, "I have this" saved to memory, plan recomputes, survives reload and API restart | e2e test; integration test restarts uvicorn and reads the holding back |
| Per-student graphs (`kaagaz:student:<id>`), isolation | integration test: A's graph cannot see B's holding |
| Why panel: path chips, source sentence, title, link, retrieved date, official/secondary tag, the Cypher, Browser link | e2e test checks the source link and Cypher |
| Conditional rules ("only if you live in a hostel") counted only when the student says they apply | integration + e2e tests |
| Fixed tool catalogue (7 tools), names resolved before queries, 5 outcomes, trace rows | validation tests, API tests, e2e Ask test |
| Ask without an LLM key (name search), "not in the graph" and "unknown name" | e2e test; API tests |
| Optional LLM layer with a checked sentence (fact numbers, names, verdict direction) | `agent.py`; tests incl. a real plan payload; run live with `openai/gpt-oss-20b` on NVIDIA NIM (`docs/LLM_SETUP.md`) |
| Benchmark: 29 questions written from sources by a separate pass; deterministic planner scores; honest LLM empty state | `bench/`; Benchmark page; e2e test |
| Second rule pack (company in Karnataka), pack switcher, exact calendar-to-working-day conversion | integration + e2e tests; `company-chain-*` screenshots |
| MCP server with the same tools | `tests/test_mcp.py` (in-process client) |
| Accessibility: axe on every screen, keyboard, focus, aria-live verdict, reduced motion, no sideways scroll at 390 px | e2e tests |
| Docker: `docker compose up -d --build` runs FalkorDB, Browser and the app | compose stack smoke-tested (health, Example student, plan, Browser HTTP 200); image build in verify |
| Design: three screenshot review rounds | `docs/DESIGN_REVIEW.md`, 36 screenshots in `docs/screenshots/` |
| Adversarial review: 11 findings, all fixed | `docs/ADVERSARIAL_REVIEW.md` |

## BLOCKED or not done, and why

- **Live deployment: BLOCKED.** No FalkorDB Cloud credentials or deploy token were in the environment, and no
  accounts were created. `docs/DEPLOY.md` has exact steps.
- **Three-system LLM benchmark: run** on 17 Oct 2026 with `openai/gpt-oss-20b` (NVIDIA NIM), 29 questions, 0 failed
  calls (`bench/results/20261017T171028Z.json`). Kaagaz: recall 93%, verdict 92% (12 of 13), first step 3 of 9,
  7.43 invented documents per answer (the model sent most "list" questions to `prerequisites`). Model alone: 9%,
  38%, 1 of 9, 8.86. Plain RAG: 5%, 46%, 2 of 9, 3.71. Table and caveats in the README.
- **Hindi UI strings: not added.** They could not be checked carefully; the i18n structure for the app shell is ready.
- **Large files in git history: fixed (17 Oct 2026).** The three large PDFs were removed from every commit with
  `git filter-repo` and the history was force-pushed with your permission. A backup bundle of the old history was
  kept outside the repo.

## LLM (NVIDIA NIM), added 17 Oct 2026 evening

- Chosen model: `openai/gpt-oss-20b`. In a 6-question trial of Kaagaz's own two jobs it picked the right tool and
  ids 5 of 6 times and wrote a sentence that passed the checker 5 of 6 times; median 3.6 s to route, 8.1 s per
  sentence. 12 models were tried; most were not usable on this key (404) or timed out. Details and how to run it:
  `docs/LLM_SETUP.md`.
- The trial found and fixed two real bugs: reasoning tokens used up the 120-token sentence budget (empty answers),
  and the model was never given the scheme and document ids (it could only call `resolve`). It also found two false
  alarms in the sentence checker (a "Category-1" inside a document name, and a date's month), now fixed with tests.
- The free endpoint queues every request in a queue shared by all users (about 40 requests a minute per key), so one
  call can wait a long time. The benchmark now asks 8 questions at once and records a failed call as a wrong answer:
  the full run took 2 min 39 s instead of 29 min.

## Official versus secondary data

- Scholarship pack: 138 of 143 requirement rules official, 5 secondary (all from one SSP e-attestation FAQ hosted by
  Mangalore University, because the SSP's own PDFs only open in a browser session). All 6 processing times and all
  11 deadlines are official (Sakala compendium 05-05-2026; NSP and SSP pages).
- Company pack: 29 of 30 rules official; GST registration (CGST Rule 9) and shops and establishments (Sakala) times
  are official; the professional tax time (30 calendar days) is secondary (PRS copy of the Act; the official sites
  returned 403 or were unreachable).
- Calendar: the 2026 Karnataka holiday list and the second/fourth Saturday rule are official (DPAR notification).
  The 2027 list is not out, so January 2027 counts may be slightly high; the UI says so.
- Two sources are Wayback Machine copies of official pages (UIDAI FAQ, MCA SPICe+ FAQ) because the live sites
  blocked the fetcher; they are labelled with the archive URL.
- Many steps have no official time at all (Aadhaar, bank account, seeding, NSP OTR, address and ID proofs, MCA
  incorporation); they stay null.

## Five things to check first when you test

1. `docker compose up -d --build`, open http://localhost:8000, press **Load the Example student**: green stamp at
   depth 1, press **One step deeper**, blue "AT LEAST 21 DAYS". Numbers change daily (working days left shrink).
2. Click the slip, check the Why panel's source links open the right government pages, and open one excerpt's source
   to judge it yourself (Sources page lists all 60 with hashes).
3. Pick **PostMatric for OBC Students** on Start, tick the documents in `docs/DEMO_SCRIPT.md` (1:05), and confirm the
   red "12 DAYS SHORT" and the hatched overrun. Then try the **Rule pack** switcher and the Example founder.
4. Read `docs/FEASIBILITY.md` and the README's "Limitations" so you can answer judges' questions about unknown times,
   conditional rules and the CSSS renewal-only window.
5. Make the repo public, then
   record the video from `docs/DEMO_SCRIPT.md` and submit (checklist in `docs/SUBMISSION.md`).
