# TDD Discipline

The repository follows red-green-refactor at the acceptance-criterion boundary.

Example for AC-08:

1. Generate a failing test proving a BUY order with notional above available cash is rejected.
2. Generate the smallest domain/service implementation that makes the test pass.
3. Refactor without weakening the test.
4. Run the complete regression suite.
5. Hand the result to the evaluator and retain the PR evidence.

## Evidence limits

Tests reference AC IDs and were written failing-first for the hardening work (see `docs/debugging-log.md`). A per-commit red/green history can only come from the real repository's git log; this archive contains no commit history, so it is not claimed here.
