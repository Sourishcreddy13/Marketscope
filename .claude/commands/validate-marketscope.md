---
name: validate-marketscope
description: Run MarketScope-specific precision, watchlist, authorization, architecture, AC traceability, and test gates before evaluator handoff.
---

# /validate-marketscope

Run the following in order:

1. Validate all changed watchlist fixtures/payloads using `.claude/skills/watchlist-validator`.
2. Validate financial test vectors using `.claude/skills/portfolio-pnl-calculator`.
3. Run `.claude/hooks/math-precision-check.sh` through the git-commit hook path or invoke it with an equivalent hook payload.
4. Run `.claude/hooks/role-boundary-check.sh` through the git-commit hook path or invoke it with an equivalent hook payload.
5. Run backend unit/integration tests.
6. Run frontend typecheck/lint/tests.
7. Run architecture tests.
8. Run `trace-ac-tests`.
9. Report every result against AC-NN and NFR-NN identifiers.

The command is verification-first. It must not weaken tests or specifications to obtain a green result.
