# One image: the FastAPI backend serving the built React frontend.
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/Atul-Chahar/kaagaz" \
      org.opencontainers.image.description="Kaagaz: scholarship document chains on FalkorDB" \
      org.opencontainers.image.licenses="MIT"
# pdftotext lets the watcher agent read re-fetched PDF sources
RUN apt-get update -q && apt-get install -y -q --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev
COPY data/packs /app/data/packs
COPY data/sources/index.json /app/data/sources/index.json
# the saved text of every source: the watcher compares the live pages against it
COPY data/sources/text /app/data/sources/text
COPY bench /app/bench
COPY --from=web /web/dist /app/frontend/dist
ENV FALKORDB_HOST=falkordb FALKORDB_PORT=6379 KAAGAZ_SEED_ON_START=1
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "kaagaz.api:app", "--host", "0.0.0.0", "--port", "8000"]
