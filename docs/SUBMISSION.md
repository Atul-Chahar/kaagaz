# Submission checklist (Graph Hacks, WeMakeDevs x FalkorDB)

Submissions close **18 Oct 2026, 11:59 PM IST**.

## Required items and where they live

| Required | Where | Status |
|---|---|---|
| Public repo | https://github.com/Atul-Chahar/kaagaz (currently **private**) | You must make it public |
| README with setup steps | `README.md`, "Quick start" and "Local development" | Done |
| README with the graph data model | `README.md`, "Graph data model" (node and edge list plus diagram); also the About the graph screen | Done |
| The Cypher queries the product depends on | `backend/kaagaz/queries/*.cypher` (one file each), listed with one line each in `README.md` | Done |
| Demo video | Script in `docs/DEMO_SCRIPT.md` (3 minutes) | You must record it |
| Live deployment or full local setup steps | Local: `docker compose up -d --build` (tested). Live: steps in `docs/DEPLOY.md` | Local done; live needs your accounts |
| Track name | Track 1, Agents That Act on Connected Data (stated at the top of `README.md`) | Confirm on the form |
| Data is public, synthetic or own | Public government sources (`data/sources/index.json`); the Example student is synthetic | Done |
| AI tools disclosed | `README.md`, "AI disclosure" | Done |

## What you must do by hand

1. **Before making the repo public**, decide about the 74 MB Sakala compendium PDF. It was committed in an early
   commit and is now untracked (in `.gitignore`), but the old blob is still in git history. If you want it gone,
   rewrite history (for example `git filter-repo --path data/sources/raw/sakala-compendium-en.pdf --invert-paths`)
   and force-push. It is a public government PDF, so leaving it is not a data problem, only a size one.
2. Make the GitHub repo public (Settings, General, Danger zone, Change visibility).
3. Record the demo video following `docs/DEMO_SCRIPT.md`. Read the numbers off the screen on the day you record:
   working days left go down every day.
4. Optional but strong: add an LLM key to `.env` (`LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`; see `.env.example`), run
   `make bench`, check `bench/results/<timestamp>.json`, and commit it. The Benchmark page and README then show the
   real three-system numbers. Update the "Benchmark" section of the README with the numbers from that file.
5. Optional: deploy with `docs/DEPLOY.md` and put the URL in the README.
6. Submit the form on WeMakeDevs with the repo URL, video link and track.
7. Optional: edit and post `docs/BLOG_DRAFT.md` for the blog prize.
