# Decisions

One line per decision, with the reason.

- 2026-10-17: FalkorDB host port 6380 (not 6379), because a valkey container already holds 6379 on this machine; container still listens on 6379 inside the compose network.
- 2026-10-17: Python 3.12 pinned through uv (`uv python install 3.12`), as the spec asks; system Python is 3.14.
- 2026-10-17: No LLM key in the environment, so the LLM layer is built and tested offline but the benchmark will show the honest "not run yet" state unless a key appears.
- 2026-10-17: Source fetching goes through one script (scripts/fetch_source.py) with a file lock, robots.txt check and 1 req/s per host, so parallel research subagents can't break index.json or the politeness rule.
