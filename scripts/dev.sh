#!/usr/bin/env bash
# Single-command local start: environment, migrations, seed data, backend (8000) and frontend (5173).
# Usage: bash scripts/dev.sh      (Ctrl-C stops both servers)
set -euo pipefail
cd "$(dirname "$0")/.."

bash scripts/ensure_env.sh
uv sync --quiet
uv run alembic upgrade head
uv run python -m scripts.seed_data
( cd frontend && [ -d node_modules ] || npm ci )

uv run uvicorn app.main:app --reload --reload-dir app --port 8000 &
BACKEND=$!
trap 'kill "$BACKEND" 2>/dev/null || true' EXIT INT TERM
cd frontend && npm run dev
