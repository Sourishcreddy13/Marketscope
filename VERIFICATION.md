# Verification (measured, `bash scripts/verify_all.sh`)

| Gate | Result |
|---|---|
| ruff, mypy (strict app), import-linter (5 contracts) | pass |
| Migration manifest (append-only) / math-precision / role-boundary hooks | pass |
| pytest (unit, integration, architecture, hooks, agent substrate) | 157 passed, 90% line coverage |
| Frontend eslint, vitest, tsc+vite build | pass, 22 unit tests |
| Playwright E2E (chromium) | 29 passed, real visual snapshots committed |
| Production LOC (non-blank: app+migrations+scripts py ≈ 2.5k, frontend/src ≈ 0.8k) | > 3,000 |

## Not verifiable from this archive (needs the real repository / secrets)
- Git/PR history, per-commit TDD red→green history, a recorded Harness sprint cycle with evaluator report.
- A live Claude Code review job in CI (`scripts/ci/claude_review.sh` is wired but needs `ANTHROPIC_API_KEY`).
