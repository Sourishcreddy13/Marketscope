.PHONY: dev env lint-imports migration-check install test test-cov lint typecheck migrate seed backend frontend verify e2e

env:
	bash scripts/ensure_env.sh

install: env
	uv sync --frozen
	cd frontend && npm ci

lint-imports:
	uv run lint-imports

migration-check:
	uv run python scripts/migration_manifest.py check

test:
	uv run pytest -q

test-cov:
	uv run pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml

lint: lint-imports
	uv run ruff check app tests scripts migrations
	cd frontend && npm run lint

typecheck:
	uv run mypy app
	cd frontend && npm run build

migrate: env
	uv run alembic upgrade head

seed:
	uv run python -m scripts.seed_data

backend: env
	uv run uvicorn app.main:app --reload --reload-dir app --port 8000

frontend:
	cd frontend && npm run dev

verify:
	bash scripts/verify_all.sh

e2e:
	cd frontend && npm run e2e

dev:
	bash scripts/dev.sh
