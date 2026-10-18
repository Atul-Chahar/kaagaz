#!/usr/bin/env bash
# Runs every check in order. Ends with exactly "VERIFY: ALL CHECKS PASSED" (exit 0), or names the failed step (exit 1).
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
export FALKORDB_HOST=${FALKORDB_HOST:-localhost} FALKORDB_PORT=${FALKORDB_PORT:-6380}
# the checks always run with no LLM key, so the no-key paths are what is tested
export LLM_PROVIDER= LLM_API_KEY= LLM_MODEL= LLM_BASE_URL=

step() {
  local name="$1"; shift
  echo
  echo "==> $name"
  local t0=$SECONDS
  if "$@"; then
    echo "--> ok: $name ($((SECONDS - t0))s)"
  else
    echo "VERIFY FAILED at step: $name"
    exit 1
  fi
}

start_falkordb() {
  docker compose up -d falkordb >/dev/null 2>&1 || return 1
  for _ in $(seq 1 60); do
    if docker compose exec -T falkordb redis-cli ping 2>/dev/null | grep -q PONG; then return 0; fi
    sleep 1
  done
  return 1
}

step "start FalkorDB (docker compose)" start_falkordb
step "seed rule packs" bash scripts/seed.sh
step "data audit" bash -c "cd backend && uv run python ../scripts/audit_data.py"
step "backend lint" bash -c "cd backend && uv run ruff check kaagaz tests ../scripts ../bench/run_bench.py"
step "backend unit tests" bash -c "cd backend && uv run pytest -q -m 'not integration'"
step "integration tests (real FalkorDB)" bash -c "cd backend && uv run pytest -q -m integration"
step "frontend typecheck" bash -c "cd frontend && pnpm -s typecheck"
step "frontend lint" bash -c "cd frontend && pnpm -s lint"
step "frontend production build" bash -c "cd frontend && pnpm -s build"
step "end-to-end + accessibility (Playwright, axe)" bash -c "cd e2e && npx playwright test app.spec.ts"
step "screenshots (1440/390, light/dark)" bash -c "cd e2e && npx playwright test screenshots.spec.ts && test \$(ls $ROOT/docs/screenshots/*.png | wc -l) -ge 44"
step "docker image builds" bash -c "docker build -q -t kaagaz-app:verify . >/dev/null"

echo
echo "VERIFY: ALL CHECKS PASSED"
exit 0
