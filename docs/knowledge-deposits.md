# Knowledge Deposits

- Financial values use `Decimal` and the `FixedDecimal` persistence type.
- `math-precision-check.sh` blocks floating-point usage in domain/service/repository financial code.
- `role-boundary-check.sh` blocks API changes that omit authentication dependencies.
- Terminal order facts use append-only order events rather than historical mutation.
- Customer-owned resources are queried with explicit customer IDs in repository methods.

## Deposits from the hardening pass

- Money crosses the HTTP boundary as decimal strings; the UI formats with BigInt string arithmetic, never `Number`.
- A retry-safe write needs three things together: client key, server fingerprint, database unique index.
- A gate that cannot run must block (exit 2), not pass. Pre-commit gates belong on PreToolUse; PostToolUse cannot prevent anything.
- Never trust a green suite built on `create_all`; run the real migrations.
- FastAPI >= 0.14x includes routers lazily: enumerate `original_router` + include prefix when auditing routes.
