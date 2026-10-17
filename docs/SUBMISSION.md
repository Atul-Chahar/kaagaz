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

1. Large PDFs in git history: done. The 74 MB Sakala compendium and the two holiday-list PDFs were removed from every
   commit with `git filter-repo` and the cleaned history was force-pushed on 17 Oct 2026. A full backup of the old
   history was kept as a git bundle outside the repo. The files are still listed in `data/sources/index.json` with
   their hash, and their extracted text is still in the repo.
2. Make the GitHub repo public (Settings, General, Danger zone, Change visibility).
3. Record the demo video following `docs/DEMO_SCRIPT.md`. Read the numbers off the screen on the day you record:
   working days left go down every day.
4. LLM: see `docs/LLM_SETUP.md` (NVIDIA NIM key in `.env`, chosen model, how to re-run the benchmark).
5. Optional: deploy with `docs/DEPLOY.md` and put the URL in the README.
6. Submit the form on WeMakeDevs with the repo URL, video link and track.
7. Optional: edit and post `docs/BLOG_DRAFT.md` for the blog prize.
