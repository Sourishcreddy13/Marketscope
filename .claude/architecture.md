# MarketScope Architecture Contract

Runtime: React/TypeScript → FastAPI → Services → Domain → Repositories → SQLite.

Layer ranks:
1. `app/domain` — business invariants and value types
2. `app/core` — configuration, security, logging, database infrastructure
3. `app/repositories` — persistence access
4. `app/services` — transactional orchestration
5. `app/api` — HTTP transport and controller-level authorization

Rules:
- Domain must not import API, services, or repositories.
- Repositories must not contain business policy.
- Services may use domain and repositories, never HTTP response objects.
- API routes call services and enforce authentication/authorization.
- Financial calculations are Decimal-only.
- SQLite is the sole runtime datastore.
