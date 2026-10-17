# Deploying Kaagaz

No FalkorDB Cloud credentials or deploy tokens were available while building, so there is no live deployment yet.
These are the exact steps to make one. Nothing here needs code changes: the app reads everything from env vars.

## What runs

- One container: the FastAPI backend, which also serves the built React frontend (`Dockerfile` at the repo root).
- One FalkorDB: either FalkorDB Cloud or the `falkordb/falkordb` image.
- On start the app rebuilds the shared rules graph from `data/packs/*/pack.yaml` (`KAAGAZ_SEED_ON_START=1`).
  Student graphs (`kaagaz:student:<id>`) are never touched by this.

## Option A: one machine with Docker (simplest)

```bash
git clone <your repo url> kaagaz && cd kaagaz
docker compose up -d --build
# app: http://<host>:8000   FalkorDB Browser: http://<host>:3000
```

Put a reverse proxy with HTTPS in front of port 8000 if it is public. Do not expose 6380 or 3000 publicly.

## Option B: FalkorDB Cloud + Render (or Railway, or Fly)

1. Create a FalkorDB Cloud instance (from falkordb.com) and note its host, port, username and password.
2. Create a new Web Service from this repo, using the Dockerfile. Set these env vars:

   | Variable | Value |
   |---|---|
   | `FALKORDB_HOST` | your FalkorDB Cloud host |
   | `FALKORDB_PORT` | your FalkorDB Cloud port |
   | `FALKORDB_USERNAME` | your FalkorDB Cloud username |
   | `FALKORDB_PASSWORD` | your FalkorDB Cloud password |
   | `KAAGAZ_SEED_ON_START` | `1` |
   | `FALKORDB_BROWSER_URL` | the Browser URL shown in your FalkorDB Cloud console |
   | `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | optional, see `.env.example` |

3. The container listens on port 8000. Health check path: `/api/health` (returns `"ok": true` once seeded).
4. Open the service URL, press "Load the Example student", and check the stamp appears.

Railway: "Deploy from GitHub repo", it picks up the Dockerfile; set the same variables. Fly: `fly launch`
(it reads the Dockerfile), then `fly secrets set FALKORDB_HOST=... FALKORDB_PORT=... FALKORDB_USERNAME=...
FALKORDB_PASSWORD=...`, and set `internal_port = 8000` in `fly.toml`.

## After deploying

- Put the URL in README.md under "Live demo".
- `curl https://<url>/api/health` should show `"falkordb": true` and the pack as seeded.
