# MarketScope Harness Extension

This project extends Claude Harness Engine for a single SQLite-backed brokerage application.

Project truth: `CLAUDE.md` and `specs/app_spec.md`.

Runtime: React + TypeScript, FastAPI + Python 3.13, SQLAlchemy + Alembic, SQLite, pytest, Vitest, Playwright.

Required domain agents: `order-lifecycle-agent`, `portfolio-analytics-agent`.
Required domain skills: `watchlist-validator`, `portfolio-pnl-calculator`.
Required project hooks: `role-boundary-check.sh`, `math-precision-check.sh`.
