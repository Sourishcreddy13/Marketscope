# MarketScope — Start Here

This repository is a complete baseline implementation of the MarketScope capstone using the intentionally simple runtime:

`React + TypeScript → FastAPI → SQLAlchemy → SQLite`

## 1. Prerequisites

- Python 3.13
- `uv`
- Node.js 24 LTS (or compatible current LTS)
- npm
- Git

## 2. First-time setup

From this repository root:

```bash
git init
cp .env.example .env
uv venv --python 3.13
source .venv/bin/activate
uv sync
uv run alembic upgrade head
uv run python -m scripts.seed_data
cd frontend
npm install
cd ..
```

## 3. Run the application

Terminal 1:

```bash
uv run uvicorn app.main:app --reload --reload-dir app --port 8000
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open `http://127.0.0.1:5173`.

Backend health: `http://127.0.0.1:8000/health`.
Swagger: `http://127.0.0.1:8000/docs`.

## 4. Demo accounts

| Role | Email | Password |
|---|---|---|
| ADMIN | `admin@marketscope.local` | `Admin@12345` |
| CUSTOMER | `customer@marketscope.local` | `Customer@12345` |
| CUSTOMER | `analyst@marketscope.local` | `Analyst@12345` |

All demo data is synthetic.

## 5. Verify the backend

```bash
uv run pytest -q
uv run pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml
```

Expected baseline: 57 tests passing and about 86% backend coverage.

## 6. Verify the frontend

```bash
cd frontend
npm run test
npm run build
npm run lint
npm run e2e
```

The build environment used to assemble this repository could not complete npm package installation, so these frontend commands are the first local runtime verification to perform after extraction.

## 7. Claude Harness

Read `CLAUDE.md` and `specs/app_spec.md` before asking Claude to change the application.

The project-specific Harness substrate is under `.claude/` and includes the MarketScope agents, skills, commands, and hooks. `.mcp.json` configures Playwright MCP.

Use the Harness in local-process mode. Do not introduce MySQL, MongoDB, Docker, Redis, Kafka, or another persistence system merely to satisfy a Harness workflow.
