# Kaagaz: rules for every session

Read PROGRESS.md and DECISIONS.md before doing anything. The full spec is KAAGAZ_SPEC.md.

## Non-negotiable (spec sections 0, 4, 7)
- Never ask the user anything. Pick the option that serves the judging criteria, log one line in DECISIONS.md.
- Prove, do not claim: every "done" needs printed evidence (test output, exit code, screenshot looked at).
- No fake anything: no invented data, hard-coded results, mocked graph, placeholder or simulated numbers.
  If it can't be done for real: `BLOCKED: <reason>` in PROGRESS.md + honest empty state in UI.
- Every rule stores source_url, source_title, retrieved_at, excerpt (<=25 words, found in saved text), confidence (official|secondary).
- Unknown processing time = null. Never guess. Verdicts depending on unknowns are lower bounds.
- Sources saved in data/sources/raw + data/sources/index.json with SHA-256. >5 MB files stay out of git.
- Fetch politely: <=1 req/s per site, respect robots.txt, cache. Use scripts/fetch_source.py.
- Example student is synthetic and labeled "Example student". No real personal data.
- Model never writes Cypher; only the fixed tool catalogue. Names are resolved before any query.
- Commit small and often. Push to private GitHub repo `kaagaz` after each phase.
- Feature freeze 18 Oct 2026 6:00 PM IST. All green by 9:00 PM IST. Run `date` each phase.
- Writing: plain simple English. NEVER use em dashes. No hype words.
- Design: tokens in spec section 7 (paper/ink/red tape/stamp blue/cleared green). Red only for critical path and late.
  No gradients, glassmorphism, sparkles, emoji icons, hero+3 cards, default component-library look.
- Never weaken, skip or delete a test to make it pass.

## Commands
- FalkorDB: `docker compose up -d falkordb` (host port 6380, Browser on 3000)
- Seed: `bash scripts/seed.sh`
- Audit: `cd backend && uv run python ../scripts/audit_data.py`
- Backend tests: `cd backend && uv run pytest`
- API dev: `cd backend && uv run uvicorn kaagaz.api:app --port 8000`
- Frontend: `cd frontend && pnpm dev` / `pnpm build` / `pnpm typecheck` / `pnpm lint`
- E2E: `cd e2e && pnpm test`
- Everything: `bash scripts/verify.sh` (must end with VERIFY: ALL CHECKS PASSED)
