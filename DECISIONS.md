# Decisions

One line per decision, with the reason.

- 2026-10-17: FalkorDB host port 6380 (not 6379), because a valkey container already holds 6379 on this machine; container still listens on 6379 inside the compose network.
- 2026-10-17: Python 3.12 pinned through uv (`uv python install 3.12`), as the spec asks; system Python is 3.14.
- 2026-10-17: No LLM key in the environment, so the LLM layer is built and tested offline but the benchmark will show the honest "not run yet" state unless a key appears.
- 2026-10-17: Source fetching goes through one script (scripts/fetch_source.py) with a file lock, robots.txt check and 1 req/s per host, so parallel research subagents can't break index.json or the politeness rule.
- 2026-10-17: FalkorDB rejects a parameter as a variable-length upper bound (`*1..$depth` gives "Encountered unhandled type in inlined properties") and label unions (`(n:D|A)`). prerequisites.cypher uses the literal bound `*1..16` and filters `WHERE dep <= $depth`, so $depth stays a real parameter.
- 2026-10-17: "Depth" counts REQUIRES hops only. An OPTION hop (AnyOf to its choices) does not use up a step, so depth 1 shows a scheme's direct documents including the choices inside an "any one of" group.
- 2026-10-17: The 74 MB Sakala compendium PDF was committed by mistake in an early commit. It is now untracked and in .gitignore (hash and text kept). Rewriting git history to remove the old blob needs the user's approval, so it is listed in FINAL_REPORT.md for the user to decide before making the repo public.
- 2026-10-17: Sakala limits are working days, so verdicts count working days to the deadline using the official 2026 Karnataka holiday list (DPAR notification) plus Sundays and 2nd/4th Saturdays. Past 31 Dec 2026 the 2027 list is not published; the UI says the count may be slightly high.
- 2026-10-17: UIDAI's "normally up to 180 days" for Aadhaar is a calendar-day service standard, not a legal limit. It is stored as service_days (shown in the Why panel) and never summed; Aadhaar's legal days stay null.
- 2026-10-17: Rules with a condition stay in the graph with the condition shown, except conditions the pack says do not apply to a college student (meta.yaml exclude_conditions, e.g. Aadhaar birth certificate rule for people born after 1 Oct 2023).
- 2026-10-17: Documents named by a cited rule but described nowhere get a names-only entry (data/research/names.yaml): no days, no office. Nothing invented.
- 2026-10-17: Demo profile = Example student on Fee Reimbursement for Minorities (deadline 30 Nov 2026). With the real data, depth 1 says ON TIME 9 DAYS SPARE and depth 2 reveals that the caste and income certificate needs a proof of residence with no official time, so the honest verdict becomes AT LEAST 21 DAYS. The red "12 DAYS SHORT" stamp is real too: every 31 Oct 2026 scheme that needs the caste and income certificate (21 working days, 9 left). The spec's sample "depth 4 shows 10 DAYS SHORT" is not what the data says, so the demo script follows the data.
- 2026-10-17: Real students see the full depth by default; the Example student opens at depth 1 so the demo can step down. Both can use the stepper.
- 2026-10-17: Kaagaz does not check eligibility (caste, income, marks). "Other options" ranks by time and shared documents and says so in plain words.
- 2026-10-17: The Wayback Machine copy of the official UIDAI FAQ is used because uidai.gov.in returned HTTP 500 to the fetcher; it is still the official page's text, so confidence stays official, and the URL shows the archive.
