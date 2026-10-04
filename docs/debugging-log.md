# Debugging Log

## Environment-first resolution

The first baseline exposed a project-root/Python-package mismatch. The project was restructured so `pyproject.toml`, `.venv`, `.env`, tests, migrations, and `app/` resolve from the repository root.

The application now uses one SQLite database and an isolated in-memory SQLite database for tests. This removes external database setup from local verification and keeps the acceptance criteria deterministic.

## Hardening pass (defects found by tests, not by inspection)

| Symptom | Root cause | Fix / guard |
|---|---|---|
| Updating a watchlist while keeping any symbol failed with "watchlist update rolled back" | clear-and-reinsert violated a unique constraint inside the unit of work | apply a diff; regression test in `tests/integration/test_hardening.py` |
| ORM and migration disagreed (missing unique constraints) | tests used `create_all`, hiding drift | tests now run Alembic; `test_migrations.py` compares metadata |
| Precision hook silently passed | it shelled out to `rg`, which was not installed, and ignored exit codes | portable grep, `--all` mode, hooks fail closed (`tests/architecture/test_hooks.py`) |
| Sprint gate never fired | `current_group` was `SPRINT-01` but the contract file is `sprint-01.json`, and a missing contract exited 0 | case-normalised, fails closed; tested |
| Alembic `fileConfig` disabled app loggers | default `disable_existing_loggers=True` | set to False; logging test |
| Trade UI error invisible to assistive tech | alert lacked `role="alert"` | fixed; Playwright asserts it |
