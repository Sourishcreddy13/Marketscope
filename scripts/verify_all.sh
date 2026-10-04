#!/usr/bin/env bash
# One command that runs every gate the CI runs. Fails on the first problem.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export ENVIRONMENT=test

uv sync --frozen --quiet
python3 -m compileall -q app tests scripts migrations
uv run ruff check app tests scripts migrations
uv run mypy app
uv run lint-imports
uv run python scripts/migration_manifest.py check
bash .claude/hooks/math-precision-check.sh --all
uv run python .claude/hooks/role_boundary.py
uv run pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml

if [[ -d frontend/node_modules ]]; then
  npm --prefix frontend run lint
  npm --prefix frontend run test
  npm --prefix frontend run build
  if [[ "${SKIP_E2E:-0}" != "1" ]]; then
    (cd frontend && npx playwright install chromium)
    npm --prefix frontend run e2e
  fi
else
  echo "frontend/node_modules missing: run 'npm --prefix frontend ci' (verification is NOT complete)." >&2
  exit 1
fi
printf '\nMarketScope verification passed for all layers.\n'
