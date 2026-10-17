# Decisions

One line per decision, with the reason.

- 2026-10-17: FalkorDB host port 6380 (not 6379), because a valkey container already holds 6379 on this machine; container still listens on 6379 inside the compose network.
- 2026-10-17: Python 3.12 pinned through uv (`uv python install 3.12`), as the spec asks; system Python is 3.14.
- 2026-10-17: No LLM key in the environment, so the LLM layer is built and tested offline but the benchmark will show the honest "not run yet" state unless a key appears.
- 2026-10-17: Source fetching goes through one script (scripts/fetch_source.py) with a file lock, robots.txt check and 1 req/s per host, so parallel research subagents can't break index.json or the politeness rule.
- 2026-10-17: FalkorDB rejects a parameter as a variable-length upper bound (`*1..$depth` gives "Encountered unhandled type in inlined properties") and label unions (`(n:D|A)`). prerequisites.cypher uses the literal bound `*1..16` and filters `WHERE dep <= $depth`, so $depth stays a real parameter.
- 2026-10-17: "Depth" counts REQUIRES hops only. An OPTION hop (AnyOf to its choices) does not use up a step, so depth 1 shows a scheme's direct documents including the choices inside an "any one of" group.
