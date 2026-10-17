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
11. [ ] Full test suite, axe and screenshots passing; at least two design review rounds done.
12. [ ] Adversarial review: subagent reviews whole repo against spec in fresh context; gaps affecting correctness, honesty or hackathon requirements fixed.
13. [ ] Docs and submission package (section 11).
14. [ ] Final `bash scripts/verify.sh` run after the last change, output shown, ends with `VERIFY: ALL CHECKS PASSED`.
15. [ ] `FINAL_REPORT.md` written and printed.

## Stretch (only after 1 to 11 green)
- [ ] S1 Live deployment (or docs/DEPLOY.md)
- [ ] S2 MCP server
- [ ] S3 Second rule pack
- [ ] S4 Hindi UI strings (or i18n structure ready, English only)
