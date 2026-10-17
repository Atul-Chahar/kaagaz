# KAAGAZ: Build Spec for Claude Code

You are building Kaagaz, an entry for Graph Hacks (WeMakeDevs x FalkorDB). Submissions close **18 Oct 2026, 11:59 PM IST**. You will work alone and unattended. Nobody will answer questions. Read this whole file before writing any code.

---

## 0. How you work (read first, follow always)

1. **Never ask the user anything.** When a choice is unclear, pick the option that best serves the judging criteria in section 2, write one line about it in `DECISIONS.md`, and keep going.
2. **Survive context resets.** At the start, create:
   - `CLAUDE.md`: under 40 lines. The non-negotiable rules from sections 0, 4 and 7, the run and test commands, and "read PROGRESS.md and DECISIONS.md before doing anything".
   - `PROGRESS.md`: a checklist copied from section 9. Tick items only when their check has passed. Update it after every phase.
   - `DECISIONS.md`: one line per decision, with the reason.
   After any compaction or resume, re-read those three files before acting.
3. **Prove, do not claim.** Every "done" needs evidence printed in the transcript: test output, command and exit code, or a screenshot you looked at.
4. **No fake anything.** No invented data, no hard-coded results, no mocked graph, no placeholder numbers, no "simulated" benchmark. If something cannot be done for real, mark it `BLOCKED: <reason>` in PROGRESS.md, show an honest empty state in the UI, and move on.
5. **Commit often.** `git init` at the start. Small commits with clear messages after each working step. If `gh auth status` succeeds, create a **private** GitHub repo named `kaagaz` and push after each phase (the user will make it public at submission). If not, skip pushing.
6. **Use subagents for heavy reading** (source research, data extraction, the final review) so your main context stays clean.
7. **Time box.** Run `date` at the start of each phase. Feature freeze at **18 Oct 2026, 6:00 PM IST**: after that, only fixes, tests, docs and polish. Everything in section 9 must be green by 9:00 PM IST.
8. **Writing style for every human-facing word** (UI copy, README, docs, blog): plain, simple English a student can repeat. **Never use em dashes.** No hype words ("revolutionary", "seamless", "cutting-edge", "unleash", "empower").

---

## 1. The product in one sentence

> Every scheme finder tells a student what they are eligible for. Kaagaz tells them whether they are already too late, and which certificate to apply for today.

**Who it is for:** a student applying for a government scholarship. A scholarship needs many documents. Some documents need other documents first, each from a different office, each with a legal processing time. Nobody shows the full chain or adds up the waiting time, so students find out too late.

**What Kaagaz does:**
1. The student picks a scholarship (and its deadline) and ticks the documents they already hold.
2. Kaagaz walks the requirement graph at every depth to find all hidden prerequisite documents.
3. It computes the critical path: the longest chain of legal processing days still left to do.
4. It gives a verdict: "On time, 6 days spare" or "10 days short".
5. It lists what to apply for today, in order, and suggests other scholarships the student can still make that reuse the same documents.
6. Every line shows its path through the graph and links to the official source.
7. It remembers the student across sessions. When a certificate arrives, the plan recomputes.

**Global by design:** the engine knows nothing about India. Countries, states and processes live in **rule packs** (data files). The first pack is Indian scholarships, because it has deep chains and official, legally guaranteed processing times. A second pack is a stretch goal (section 10).

---

## 2. How it will be judged (build toward this)

WeMakeDevs judges six equal criteria: impact, creativity, technical excellence, best use of the sponsor (FalkorDB), user experience, presentation. The hackathon rules add:
- The graph must do real work. If the product still works with FalkorDB removed, it fails.
- Required in the submission: public repo, README with setup steps **and the graph data model**, the Cypher queries the product depends on, a demo video, a live deployment or full local setup steps, and the track name.
- Data must be public, synthetic or our own. No private or personal data.
- AI coding tools are allowed but must be disclosed.

What won past WeMakeDevs hackathons, and what you must reproduce:
- One sharp insight in one sentence (section 1).
- **Proof against a baseline with real numbers** (section 6).
- The model never writes Cypher. It picks from a fixed tool catalogue. Names are checked against the graph before any query runs.
- Every answer carries its path. The agent can honestly say "not in the graph".
- The demo move the organizers recommend: the same question at depth 1, then at depth 4, where the hidden chain appears.
- Shipped like a product: README a stranger can run, clean UI, working demo.

Target track: **Track 1, Agents That Act on Connected Data.** (Cross-session memory also touches Track 2.)

---

## 3. Phase 1: Data feasibility test (do this before any app code)

This decides whether the idea holds. Use subagents for the research.

1. **Collect real rules** for at least 3 scholarships: at least 1 central scheme on the National Scholarship Portal (NSP) and at least 2 Karnataka state schemes (State Scholarship Portal). Then add more until you have 6 to 10 schemes if sources allow.
2. For every document a scheme needs, find **its own** requirements (what you must submit to get that document) and its **issuing office**.
3. Find **legal processing times** from official Right to Public Services sources. For Karnataka this is the Sakala list (sakala.kar.nic.in or the official Seva Sindhu / Nadakacheri pages). For central documents use the issuing body's official page.
4. Find each scheme's **application window or deadline** from its official page. If only a past year's window is published, store it with its year and label it in the UI as "last published window".
5. Save every source (section 4).
6. **Decide:**
   - **Pass** if at least one scheme has a chain 3 or more levels deep (scheme, document, prerequisite, prerequisite) AND at least one realistic case where the critical path is close to or longer than the time left before a published deadline. Build Kaagaz.
   - **Fail** if chains are almost all 1 level deep. Then switch the first rule pack to **starting a company in India** (MCA SPICe+ incorporation and the registrations after it: PAN, TAN, GST, bank account, shop and establishment, professional tax). Same engine, same UI, new copy. Write the switch and the evidence in `DECISIONS.md`.
7. Write `docs/FEASIBILITY.md`: schemes found, deepest chain, longest critical path, sources. Commit.

---

## 4. Data integrity rules (non-negotiable)

- **Every** rule (a requirement edge, a processing time, a deadline, an issuing office) stores: `source_url`, `source_title`, `retrieved_at` (ISO date), `excerpt` (the exact sentence that proves it, 25 words or fewer), and `confidence` (`official` or `secondary`).
- Prefer official government pages and PDFs (`.gov.in`, `.nic.in`, state portals, notifications). A secondary source (a college notice, a news report) is allowed only when no official one is found, and is shown with a "secondary source" tag in the UI.
- Save each fetched source in `data/sources/raw/` with a SHA-256 hash, and list it in `data/sources/index.json` (url, title, retrieved_at, hash, file). Keep files over 5 MB out of git (list them in `.gitignore`, keep the hash in the index).
- **If a processing time is not found in any source, store `null`.** Never guess. The planner treats unknown time as unknown and the UI says "No official time limit found". A verdict that depends on an unknown time is shown as a lower bound ("at least 35 days") or "can't be computed", never as a confident answer.
- The example student is synthetic and labeled "Example student" everywhere. No real personal data, ever.
- `scripts/audit_data.py` fails the build if any rule is missing a field above, if any `source_url` is not in the index, or if any excerpt is not found in the saved source text (normalize whitespace and case).
- Fetch politely: no more than 1 request per second per site, respect robots.txt, cache everything you fetch.

---

## 5. Architecture

Keep it simple and solid.

```
kaagaz/
  CLAUDE.md  PROGRESS.md  DECISIONS.md  FINAL_REPORT.md  README.md
  docker-compose.yml          # falkordb/falkordb:latest (6379, Browser on 3000) + app
  Dockerfile                  # one image: API + built frontend
  .env.example                # every env var, with comments
  backend/                    # Python 3.12, FastAPI, falkordb (official client), pydantic, uv
    kaagaz/
      api.py                  # HTTP routes
      graph.py                # FalkorDB connection, graph names, load packs
      queries/*.cypher        # EVERY query the product uses, one file each, parameterized
      tools.py                # fixed tool catalogue (see 5.3)
      planner.py              # critical path, verdict, ordering, alternatives
      memory.py               # per-student graph
      agent.py                # optional LLM layer (see 5.4)
      mcp_server.py           # same tools over MCP (stretch, section 10)
    tests/
  data/
    packs/<pack-id>/pack.yaml # jurisdiction, language, currency, documents, offices, schemes, rules
    sources/                  # raw snapshots + index.json
  frontend/                   # Vite + React + TypeScript, hand-written CSS with design tokens
  e2e/                        # Playwright tests + screenshots
  bench/                      # benchmark (section 6)
  scripts/verify.sh  scripts/seed.sh  scripts/audit_data.py
  docs/                       # FEASIBILITY, DEMO_SCRIPT, BLOG_DRAFT, SUBMISSION, screenshots/
```

### 5.1 Graph model

One shared rules graph per pack: graph name `kaagaz:rules:<pack-id>`.

```
(:Pack {id, name, jurisdiction, version})
(:Scheme {id, name, authority, window_start, window_end, window_year, source_url, ...})
(:Document {id, name, days, days_source_url, validity, ...})   // days may be null
(:Office {id, name, level})
(:AnyOf {id, label})                                            // "one of these documents"
(:Scheme)-[:REQUIRES {source_url, source_title, retrieved_at, excerpt, confidence}]->(:Document|:AnyOf)
(:Document)-[:REQUIRES {...same}]->(:Document|:AnyOf)
(:AnyOf)-[:OPTION {...same}]->(:Document)
(:Office)-[:ISSUES {days, source_url, ...}]->(:Document)
```

One graph **per student** (FalkorDB multigraph): `kaagaz:student:<student-id>`.

```
(:Student {id, label, created_at})
(:Holding {doc_id, issued_on, added_at})        // what they already have
(:Target {scheme_id, deadline, added_at})       // what they are applying for
(:PlanSnapshot {at, scheme_id, verdict, critical_days, json})   // memory of past plans
```

Because one Cypher query runs on one graph, the planner reads holdings from the student graph and passes the held document IDs as a parameter into the rules graph query. Write this down in the README as a deliberate use of multigraph isolation: a student's data can never leak into another student's graph.

### 5.2 Graph work (must be real Cypher in `queries/`)

- `prerequisites.cypher`: variable-length traversal `-[:REQUIRES|OPTION*1..$depth]->` from a scheme, returning every node with its depth and the full path (`[n IN nodes(p) | n.id]`) and the rule properties on each hop. `$depth` is a parameter (capped at 8). This powers the depth slider.
- `chain_days.cypher`: for all-of chains, sum of remaining processing days along each path from the scheme to every leaf, skipping documents in `$held`, using `reduce(...)`. Return the longest paths. Unit tests must check this against `planner.py` on the same data.
- `shared_documents.cypher`: which other schemes reuse the documents this student still needs (for "switch to scheme Y" suggestions).
- `load_bearing.cypher`: the document that appears in the prerequisite trees of the most schemes the student targets (count distinct schemes per document). If FalkorDB's `algo.pageRank` gives a clearer answer on the full pack, use it too and say so in the README.
- `fastest_option.cypher`: when an `AnyOf` has options, use `algo.SPpaths` with processing days as the weight (or a weighted path query) to pick the fastest option the student does not hold. Check FalkorDB's docs for the exact procedure signature before using it.
- `resolve_name.cypher`: exact and case-insensitive lookup of a scheme or document by id or name. Used before any other tool runs.

Read FalkorDB's docs (docs.falkordb.com, especially Cypher support, known limitations, algorithms) before writing queries. Note the documented behaviour of unreferenced relationships in patterns: bind and reference relationship aliases where it matters.

### 5.3 Planner and tool catalogue

`planner.py` computes, for one scheme and one student:
- `finish(doc) = days(doc) + max(finish(prereq))` over all-of prerequisites not held; for `AnyOf`, the minimum over its options; held documents count 0.
- Critical path = the chain that gives the maximum finish time. Verdict compares it with days left until the deadline (today from the server clock, timezone of the pack).
- Unknown days propagate as unknown. Report a lower bound plus which documents are unknown.
- An ordered "start today" list: every document whose prerequisites are all held, sorted by how much it shortens the critical path.

The **fixed tool catalogue** (the only things the agent can call), each with typed, validated arguments:
`resolve(name)`, `prerequisites(scheme_id, depth<=8)`, `plan(student_id, scheme_id)`, `explain(scheme_id, doc_id)` (path + sources), `alternatives(student_id, scheme_id)`, `remember_holding(student_id, doc_id, issued_on)`, `recall(student_id)`.

Every response has one of five outcomes, shown in the UI: **answered with a path**, **answered from memory** (with the date it was saved), **not in the graph** (the scheme or document exists, but no rule connects it the way the question assumes), **unknown name** (no query runs), **no official time found**.

Log every tool call as a trace row: tool, arguments, milliseconds, rows returned. The UI shows this trace.

### 5.4 Optional LLM layer

- Provider-agnostic: Anthropic, or any OpenAI-compatible endpoint (OpenAI, Groq, Gemini's OpenAI-compatible API, local Ollama). Configured only through env vars in `.env.example` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). Do not hard-code model names you have not checked exist.
- The LLM does exactly two jobs: turn a free-text question into one tool call from the catalogue, and write one plain sentence summarizing the tool result.
- **Check the sentence before showing it:** every document or scheme name it mentions must appear in the tool result, and any number it states must match the result. If the check fails, show a sentence built directly from the result instead.
- **The whole product must work with no LLM key.** Without a key, the "Ask" box becomes a search over scheme and document names, and everything else works the same.

---

## 6. Benchmark (the proof slide)

`bench/` measures whether the graph actually beats plain approaches.

- `bench/questions.jsonl`: 20 or more questions written from the saved sources, each with a ground-truth answer and the source IDs that prove it. Types: "list every document needed, including documents needed to get them", "which document should be applied for first", "can a student holding X and Y make a deadline N days away".
- Ground truth is written from the sources (a subagent reads the sources and writes it), then checked against the graph. Disclose in the README that the graph and the ground truth come from the same sources.
- Three systems, same model for all: (a) **LLM alone**, (b) **plain RAG**: BM25 over the same saved source text, top 8 chunks, then the LLM, (c) **Kaagaz**.
- Metrics: document recall, invented documents (named but not required), verdict accuracy, first-step accuracy.
- `bench/run_bench.py` writes `bench/results/<timestamp>.json` with model name, date and raw answers. The UI's Benchmark page reads the latest real file.
- **If no LLM key is configured, the benchmark does not run.** The page then says "Benchmark not run yet. Add an LLM key and run `make bench`." Never display numbers that did not come from a real run. Kaagaz's own deterministic scores (from the planner, no LLM) may be computed and shown on their own, labeled as such.

---

## 7. Design: make it look like nobody else's entry

Before writing UI code, load the `frontend-design` skill if it is available (and `apple-desing` for motion, if installed). Then follow this direction. The goal: a judge recognizes it in one second and it looks nothing like a generic AI dashboard.

### Concept: "Red tape, untied"
Government paperwork, redesigned with care. The visual language comes from real offices: paper slips, rubber stamps, the red cloth tape that ties office files together, carbon-copy forms. But clean, calm and modern, never kitsch.

### Tokens
- **Paper** `#F5F0E6` (background), **Paper deep** `#EAE2D3` (panels), **Ink** `#1C1A17` (text), **Ink soft** `#5B554C`.
- **Red tape** `#B8321F`: the critical path and "late" only. Nothing else is red.
- **Stamp blue** `#24467A`: links, focus rings, secondary stamps.
- **Cleared green** `#2F6B45`: "on time" and held documents only.
- Dark mode ("night office"): background `#16140F`, panels `#211E18`, text `#EFE8DA`, same accents slightly lifted to keep AA contrast. Respect `prefers-color-scheme` and offer a toggle.
- **Type:** `Fraunces` (headings, optical sizing on), `IBM Plex Sans` (body), `IBM Plex Mono` (dates, days, IDs, Cypher). Load from Google Fonts. IBM Plex also has Devanagari and other scripts, which keeps the global door open.
- 8 px spacing grid. Hairline 1 px rules in Ink at 15% instead of heavy cards. Corners 2 px (paper, not bubbles). Shadows only on the dragged or focused slip.

### Never do
Purple or blue gradients, glassmorphism, glowing "AI" sparkles, emoji as icons, a centered hero with three feature cards, a default component-library look, stock illustrations, lorem ipsum, fake testimonials, fake user counts.

### Screens
1. **Start.** One calm screen. Title, the one-sentence promise, then three steps on one page: pick a scholarship (searchable list from the graph, shows the deadline), tick what you already hold (grouped list), go. An "Example student" button loads the labeled synthetic profile for the demo.
2. **The Chain (hero screen).** A horizontal timeline from today to past the deadline.
   - Each document is a **paper slip** whose length equals its legal processing days. Prerequisites sit to the left of what they unlock. Unknown-time slips have a dashed edge and an "unknown time" tag.
   - The critical path is tied together by a **red tape** line running through its slips.
   - The deadline is a vertical dashed line with its date.
   - If the chain runs past the deadline, the overrun is hatched in red tape colour and a **rubber stamp** lands on the screen: "10 DAYS SHORT" (slight rotation, ink texture with an SVG noise filter, one short press animation). On time: a green stamp "ON TIME · 6 DAYS SPARE". Unknown: a blue stamp "AT LEAST 35 DAYS".
   - A **"Show hidden steps"** stepper (depth 1 to max). At depth 1 only direct documents show. Each step slides new slips in from the left and recomputes the verdict live. This is the demo moment, so make it smooth (under 300 ms per step) and honest.
3. **Start today.** Below the timeline: the ordered checklist. Each row: document, office, legal days, a "why" path, the source link, and an "I have this" toggle that saves to memory and recomputes.
4. **Why panel.** Click any slip: a side panel shows the path as chips (Scholarship → Caste validity certificate → Caste certificate), each hop with its excerpt, source title, link and retrieved date, plus the exact Cypher that produced it (copy button) and "Open in FalkorDB Browser".
5. **Other options.** Scholarships the student can still make, ranked by days spare and by how many needed documents they share.
6. **Ask.** A text box. Shows the outcome type, the answer, and the trace rows (tool, args, ms, rows). Works without an LLM key (name search).
7. **Benchmark.** Real results only (section 6), as a simple, clear table and one bar chart. Honest empty state if not run.
8. **Sources.** Every source in the pack: title, URL, retrieved date, hash, how many rules cite it, official or secondary.
9. **About the graph.** A small diagram of the graph model, the list of Cypher queries, and how the tracks and rules are met.

### UX rules
- A first-time visitor understands the verdict within 10 seconds with no explanation.
- All copy is plain words. Dates as "21 Nov 2026". Days as "21 days".
- Works at 390 px wide (the timeline scrolls horizontally inside its own frame with a fixed verdict above it) and at 1440 px.
- WCAG 2.1 AA: contrast, full keyboard use, visible focus, labels, `aria-live` for the verdict, `prefers-reduced-motion` turns the stamp and slide animations into simple fades.
- Every loading, empty and error state is designed and written (for example, "FalkorDB isn't reachable. Start it with `docker compose up -d`.").

---

## 8. Testing (you must run all of it)

- **Backend unit tests** (pytest): planner maths (all-of, any-of, held documents, unknown days, deadline edge cases including today and past deadlines), tool argument validation, name resolution, the LLM sentence checker (with fixed inputs, no network).
- **Integration tests** against a real FalkorDB from docker compose (no mocks of the database): seed the pack, run every query in `queries/`, check `chain_days.cypher` agrees with `planner.py`, check the per-student graph isolation (student A cannot see student B's holdings), check memory survives an app restart.
- **Data audit**: `scripts/audit_data.py` (section 4).
- **Frontend**: typecheck, lint, production build.
- **End-to-end** (Playwright, real backend, real FalkorDB): load the Example student, step the depth from 1 to max and assert the verdict changes as the data says it should, toggle "I have this" and assert the plan recomputes, open a Why panel and assert the source link is present, run Ask with no LLM key, check the Benchmark page shows only real data or the honest empty state.
- **Accessibility**: `@axe-core/playwright` on every screen, zero serious or critical violations.
- **Screenshots**: Playwright saves every screen at 1440 px and 390 px, light and dark, into `docs/screenshots/`. **Open each screenshot with your file reading tool and look at it.** Write a short critique for each in `docs/DESIGN_REVIEW.md` (alignment, spacing, hierarchy, contrast, anything that looks generic or broken), fix the problems, re-shoot, and repeat until you would show it to a design-minded judge. Do at least two rounds.

`scripts/verify.sh` runs everything in order (start FalkorDB, seed, audit, unit, integration, frontend checks, build, e2e, axe, screenshots) and ends by printing exactly `VERIFY: ALL CHECKS PASSED` and exiting 0, or prints which step failed and exits non-zero. Never weaken, skip or delete a test to make it pass. Fix the cause.

---

## 9. Phases and the PROGRESS.md checklist

1. [ ] Setup: git, CLAUDE.md, PROGRESS.md, DECISIONS.md, docker compose with FalkorDB running, skeleton backend and frontend, `verify.sh` stub.
2. [ ] Phase 1 data feasibility done, decision recorded, `docs/FEASIBILITY.md` written.
3. [ ] Rule pack built with full sourcing; `audit_data.py` passes.
4. [ ] Graph seeded; all Cypher queries written and tested against real FalkorDB.
5. [ ] Planner and tool catalogue done with unit tests.
6. [ ] Per-student memory graphs working, with isolation and restart tests.
7. [ ] API complete with trace logging.
8. [ ] UI: all 9 screens built to section 7.
9. [ ] Optional LLM layer with the sentence checker; app fully works without a key.
10. [ ] Benchmark built; run it if a key exists; honest empty state if not.
11. [ ] Full test suite, axe and screenshots passing; at least two design review rounds done.
12. [ ] Adversarial review: a subagent reviews the whole repo against this spec in a fresh context and lists gaps that affect correctness, honesty (any fake or unsourced data), or the hackathon requirements. Fix those. Ignore pure style opinions.
13. [ ] Docs and submission package (section 11).
14. [ ] Final `bash scripts/verify.sh` run after the last change, output shown, ends with `VERIFY: ALL CHECKS PASSED`.
15. [ ] `FINAL_REPORT.md` written and printed.

---

## 10. Stretch goals (only after items 1 to 11 are green, in this order)

1. **Live deployment.** If FalkorDB Cloud credentials (`FALKORDB_HOST`, `FALKORDB_PORT`, `FALKORDB_USERNAME`, `FALKORDB_PASSWORD`) and a deploy token for Render, Railway or Fly exist in the environment, deploy and put the URL in the README. Otherwise write `docs/DEPLOY.md` with exact steps. Never create accounts.
2. **MCP server** exposing the same tool catalogue, with a README snippet for adding it to Claude Code or Cursor.
3. **Second rule pack** (proves it is global), with the same sourcing rules. Pick the one with the best official sources: a student visa process (for example, a country whose official government site publishes document requirements and processing times) or the "starting a company in India" pack. Show a pack switcher on the Start screen.
4. Hindi UI strings, only if checked carefully; otherwise leave the i18n structure ready and English only.

---

## 11. Submission package

- `README.md`: the one-sentence pitch, a screenshot, quick start (`docker compose up`, then the URL), the graph data model (diagram plus the node and edge list from 5.1), every Cypher query with one line on what it does, how the graph does work the product cannot do without it, the benchmark method and latest real results (or "not run"), data sources and the integrity rules, limitations stated honestly, track: **Track 1, Agents That Act on Connected Data**, and an **AI disclosure**: "Built with Claude Code (Anthropic). I designed the idea, reviewed the code and verified the results."
- `docs/DEMO_SCRIPT.md`: a 3-minute script. 0:00 the one sentence. 0:15 the problem. 0:30 Example student, depth 1 looks fine, step to depth 4, the "10 DAYS SHORT" stamp lands. 1:30 Why panel with path, source and Cypher. 1:50 "I have this" toggle, plan recomputes from memory. 2:10 ask something not in the graph, honest answer. 2:25 benchmark slide. 2:45 repeat the sentence. Use only things that really work.
- `docs/BLOG_DRAFT.md`: a draft blog post for the best-blog side prize, written in first person as the builder (Atul), plain and honest, no em dashes, no hype. Mark it clearly as a draft for him to edit.
- `docs/SUBMISSION.md`: checklist of every required item with where it lives, and what the user must do by hand (make the repo public, record the video, submit the form on WeMakeDevs, confirm the track).
- `FINAL_REPORT.md`: what works (with evidence), what is `BLOCKED` and why, which data is official versus secondary, the latest `verify.sh` result, and the 5 things the user should check first when he tests.

---

## 12. Done means

All items in section 9 are ticked or marked `BLOCKED` with a reason, the final `bash scripts/verify.sh` run after the last change ends with `VERIFY: ALL CHECKS PASSED`, and `FINAL_REPORT.md` exists. Then stop.
