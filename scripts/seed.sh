#!/usr/bin/env bash
# Seed every rule pack into FalkorDB (rules graph kaagaz:rules:<pack-id>).
set -euo pipefail
cd "$(dirname "$0")/../backend"
uv run python -m kaagaz.seed
