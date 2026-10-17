.PHONY: up down seed audit test e2e build bench bench-deterministic verify dev

up:            ## FalkorDB + app in docker
	docker compose up -d --build
down:
	docker compose down
seed:
	bash scripts/seed.sh
audit:
	cd backend && uv run python ../scripts/audit_data.py
test:
	cd backend && uv run pytest
e2e:
	cd frontend && pnpm build && cd ../e2e && npx playwright test
build:
	cd frontend && pnpm build
bench:         ## needs LLM_PROVIDER, LLM_API_KEY, LLM_MODEL
	cd backend && uv run python ../bench/run_bench.py
bench-deterministic:
	cd backend && uv run python ../bench/run_bench.py --deterministic
verify:
	bash scripts/verify.sh
dev:           ## API on :8000 (serves frontend/dist); run `cd frontend && pnpm dev` for hot reload on :5173
	cd backend && uv run uvicorn kaagaz.api:app --reload --port 8000
