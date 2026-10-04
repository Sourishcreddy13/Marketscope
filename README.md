# MarketScope

MarketScope is a synthetic retail brokerage and portfolio analytics application implemented as a deliberately simple full stack:

**React + TypeScript → FastAPI → SQLAlchemy → SQLite**

The repository also contains a Claude Harness Engine substrate for AI-native implementation and change management.

## Requirements

- Python 3.13
- `uv`
- Node.js 24 LTS or a compatible current LTS
- npm

No MySQL, MongoDB, Redis, or Docker is required.

## Quick start

From the repository root:

```bash
bash scripts/ensure_env.sh        # creates .env with a generated JWT_SECRET (never committed)
uv venv --python 3.13
source .venv/bin/activate
uv sync --frozen
uv run alembic upgrade head
uv run python -m scripts.seed_data
```

Terminal 1:

```bash
uv run uvicorn app.main:app --reload --reload-dir app --port 8000
```

Or start everything with one command (env, migrations, seed, backend and frontend): `make dev`.


Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| ADMIN | `admin@marketscope.local` | `Admin@12345` |
| CUSTOMER | `customer@marketscope.local` | `Customer@12345` |
| CUSTOMER | `analyst@marketscope.local` | `Analyst@12345` |

All data is synthetic.

## Backend verification

```bash
uv run pytest -q
```

Coverage:

```bash
uv run pytest --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml
```

Lint/type checks:

```bash
uv run ruff check app tests scripts migrations
uv run mypy app
```

Frontend:

```bash
cd frontend
npm install
npm run test
npm run build
npm run e2e
```

## Application behavior

- Registration creates a CUSTOMER and an initial portfolio.
- ADMIN controls user roles and stock catalog records.
- Stock deletion is logical (`DELETED`), never physical.
- Customers can maintain up to 10 watchlists.
- Watchlist mutations are atomic.
- MARKET/LIMIT BUY/SELL orders enter PENDING.
- Valid lifecycle transitions are PENDING → EXECUTED/CANCELLED/REJECTED.
- BUY orders reserve cash; cancellation/rejection releases it.
- SELL orders are limited to currently unreserved holdings.
- Executed orders and event history are append-only.
- Market prices are synthetic and stored as append-only ticks.
- Portfolio valuation and P&L use Python Decimal and four decimal places.

## Repository rules

Read `CLAUDE.md` before making changes. Read `specs/app_spec.md` before changing domain behavior.

The intended agent workflow is:

`Planner → Domain Specialist → Implementer → Test Engineer → Security Reviewer → Evaluator → Fix Loop → PR`

No direct commits to `main` are permitted by the project process.


## Security configuration

- `JWT_SECRET` must be set (>= 32 characters, not a placeholder) or the backend refuses to start. `scripts/ensure_env.sh` generates one; `make env` does the same.
- Orders require an `Idempotency-Key` header; the UI sends one per submit and reuses it on retry.
- First E2E run needs the browser: `cd frontend && npx playwright install chromium` (verify_all.sh does this for you).
- Run the whole gate suite with `make verify` (backend lint/types/import-linter/migration manifest/tests, frontend lint/unit/build/E2E).
- Frontend installs use `npm ci` against `package-lock.json`; Python installs use `uv sync --frozen`.

## Agent substrate

`.claude/` holds hooks (fail-closed gates, PR-only branch protection), agents, the trust-boundary policy (`.claude/policies/trust-boundary.md`) and the handoff schema. `python scripts/agent_runtime.py --print-state` shows the runtime state agents are given; `--agent <name> --dry-run` builds their SDK options without calling the API.
