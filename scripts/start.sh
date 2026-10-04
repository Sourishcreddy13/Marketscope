#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

bash scripts/ensure_env.sh
uv run alembic upgrade head
uv run python -m scripts.seed_data

cleanup() {
  kill "${BACKEND_PID:-0}" "${FRONTEND_PID:-0}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
(
  cd frontend
  npm run dev
) &
FRONTEND_PID=$!

wait
