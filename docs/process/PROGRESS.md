# Progress

Tick only when the check has passed (evidence in transcript). `BLOCKED: <reason>` if it can't be done for real.

1. [x] Setup: git, CLAUDE.md, PROGRESS.md, DECISIONS.md, docker compose with FalkorDB running, skeleton backend and frontend, `verify.sh` stub.
2. [x] Phase 1 data feasibility done, decision recorded, `docs/FEASIBILITY.md` written.
3. [x] Rule pack built with full sourcing; `audit_data.py` passes.
4. [x] Graph seeded; all Cypher queries written and tested against real FalkorDB.
5. [x] Planner and tool catalogue done with unit tests.
6. [x] Per-student memory graphs working, with isolation and restart tests.
7. [x] API complete with trace logging.
8. [x] UI: all 9 screens built to section 7.
9. [x] Optional LLM layer with the sentence checker; app fully works without a key.
10. [x] Benchmark built; run it if a key exists; honest empty state if not.
11. [x] Full test suite, axe and screenshots passing; at least two design review rounds done.
12. [x] Adversarial review: subagent reviews whole repo against spec in fresh context; gaps affecting correctness, honesty or hackathon requirements fixed.
13. [x] Docs and submission package (section 11).
14. [x] Final `bash scripts/verify.sh` run after the last change, output shown, ends with `VERIFY: ALL CHECKS PASSED`.
15. [x] `FINAL_REPORT.md` written and printed.

## Stretch (only after 1 to 11 green)
- [x] S1 Live deployment: BLOCKED for a live URL (no FalkorDB Cloud credentials or deploy token in the environment; no accounts created). docs/DEPLOY.md written with exact steps; docker compose stack tested locally.
- [x] S2 MCP server (backend/kaagaz/mcp_server.py, same 7 tools, tests/test_mcp.py passes in-process)
- [x] S3 Second rule pack: starting a company in Karnataka (in-ka-company), same sourcing and audit, pack switcher on Start, exact working/calendar day conversion, e2e + integration tests.
- [x] S4 i18n structure ready for the app shell (frontend/src/i18n.ts), English only: no Hindi strings, because they could not be checked carefully.


## After the first submission (18 Oct 2026)
- [x] Date switch: "See it as on 18 Oct 2026", labelled, plans viewed that way not saved (API and e2e tests).
- [x] GitHub Actions CI; image published to ghcr.io on main after CI; daily watcher workflow opening an issue.
- [x] Watcher agent: re-checks every rule's proof sentence on the live pages; one finding per sentence; warning when most of a page changes; first real run in docs/watch/latest.md (22 sources, 175 rules, 8 findings, left open).
- [x] Reviewer step: approve or reject; approval writes changes.yaml (audited), saves the new source version, rebuilds the rules graph.
- [x] Caseworker agent: multi-step review with a coded policy, proposals that run only after approval, tasks and .ics, alerts to affected students through the shared registry, cursor so each approval is handled once.
- [x] Memory over time: applications count down in the planner and in Cypher (300+ agreement cases); the caseworker compares each review with its last one.
- [x] MCP: review_case and watcher_findings.
- [x] `bash scripts/verify.sh`: VERIFY: ALL CHECKS PASSED (121 backend tests, 20 e2e, 40 screenshots, Docker build).
