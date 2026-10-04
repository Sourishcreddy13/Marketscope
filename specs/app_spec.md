# MarketScope Root Specification

## Spec-Is-Truth
This document is the authoritative contract for MarketScope. When generated code and this specification disagree, the code is wrong. A deliberate specification change requires regeneration of affected tests and implementation through Claude Code.

## Scope
MarketScope is a self-serve retail brokerage and portfolio analytics platform using synthetic data and stubbed execution. It supports registration/login, role administration, stock catalog administration, watchlists, market/limit BUY/SELL orders, order lifecycle, portfolio valuation, daily statistics, sector exposure, and operational order statistics.

Real exchange connectivity, real order matching, real broker accounts, T+1 settlement, real-time WebSockets, margin/leverage, derivatives, FX, document KYC, advanced tax computation, production secret management, and multi-region deployment are out of scope.

## Technology
- React + TypeScript + Vite
- Python 3.13 + FastAPI
- SQLAlchemy + Alembic
- SQLite only
- pytest + pytest-cov
- Vitest for frontend unit tests
- Playwright + Playwright MCP for E2E validation

## Domain Models

### User
`id`, `email`, `password_hash`, `role`, `created_at`, `updated_at`, `last_role_change_at`, `last_role_change_by`.

Roles: `CUSTOMER`, `ADMIN`, `SUSPENDED`.

Email is validated with `email-validator` (syntax and special-use domains; deliverability is not checked) and normalised to lower case. A customer may close their own account (`DELETE /auth/me`, password required): the account is soft-closed to `SUSPENDED`, never physically deleted, and is refused while orders are PENDING. ADMIN accounts cannot be closed this way. `/auth/login` and `/auth/register` are rate limited per client address (default 5 attempts per 60 seconds, `AUTH_RATE_LIMIT_ATTEMPTS`). A suspended user who supplies the correct password receives HTTP 403 "this account is suspended"; a wrong password or unknown email always receives 401 "invalid credentials" so emails cannot be probed.

A new registration always creates an active `CUSTOMER`. Passwords use Argon2. Passwords and password hashes are never logged or returned by APIs.

### Stock
`id`, `symbol`, `name`, `sector`, `exchange`, `status`, `created_at`, `updated_at`.

Status: `ACTIVE`, `DELETED`.

ADMIN has full CRUD except physical deletion. Delete is a state change `ACTIVE -> DELETED`. Customers only browse ACTIVE stocks. Symbol, name, sector and exchange must be non-blank after trimming.

> **Requirements-resolution note (AC-03).** The capstone brief words the soft-delete status as `DELISTED` in one place and the supervisor's domain model uses `DELETED`. Resolution: the persisted and API value is **`DELETED`** (this spec is the source of truth). The brief's "delisted" is the business meaning of the same state; no `DELISTED` enum value exists. Decided by the supervisor; revisit only by changing this note, the enum, and AC-03 tests together.

### Watchlist
`id`, `customer_id`, `name`, `created_at`, `updated_at` and the many-to-many `watchlist_symbols` relation.

A customer owns at most 10 watchlists. Every watchlist contains at least one ACTIVE symbol. Rename/add/remove/delete operations are atomic. A failed composite operation leaves the previous state unchanged and raises `WatchlistUpdateException`.

### Portfolio
One portfolio per customer: `id`, `customer_id`, `cash_balance`, `reserved_cash`, timestamps.

`available_cash = cash_balance - reserved_cash`.

Holdings contain `stock_id`, `quantity`, `average_buy_price`, and timestamps.

### Order
`id`, `customer_id`, `stock_id`, `side`, `order_type`, `quantity`, `limit_price`, `quote_price`, `status`, timestamps, rejection reason.

Sides: `BUY`, `SELL`.
Types: `MARKET`, `LIMIT`.
Statuses: `PENDING`, `EXECUTED`, `CANCELLED`, `REJECTED`.

Administrators must give a reason when rejecting an order; the customer sees it in their order history. Every valid placement enters PENDING with a server-generated timestamp.

**Idempotency.** `POST /orders` requires an `Idempotency-Key` header (8-64 chars of `A-Za-z0-9_.:-`). A repeat with the same key and the same request returns the original order (HTTP 200, `Idempotent-Replay: true`) and changes nothing. The same key with a different request is HTTP 422. Uniqueness is enforced by a database index on `(customer_id, idempotency_key)`.

**Atomicity.** Each order operation is one unit of work: validate everything first, then mutate, commit once, roll back on any failure.

### Trade
Append-only execution ledger, one row per executed order (`order_id` unique): `customer_id`, `stock_id`, `side`, `quantity`, `execution_price`, `notional`, `executed_at`, `actor_id`, `request_correlation_id`. ORM `before_update`/`before_delete` listeners raise `ImmutableRecordError`. ADMIN reads it at `GET /admin/trades`; `GET /admin/stocks/most-traded` reports symbols with counts.

### OrderEvent
Append-only order transition history. Contains `order_id`, `from_status`, `to_status`, `actor_id`, timestamp, reason.

### AuditEvent
Append-only audit history for role changes, administrative catalog changes, and administrative order outcomes. Contains actor, action, target, timestamp, and request correlation ID.

### MarketTick
Append-only synthetic market-price history: stock, price, timestamp. The latest tick is authoritative for the stub market price. Ticks run every `MARKET_TICK_INTERVAL_SECONDS` (default 15) as a random walk of at most +/-2% per tick, bounded to 70%-130% of the stock's first price. Quote responses include `previous_price` and a server-computed `change_percent`. Daily movers list only strictly positive (gainers) or negative (losers) positions.

## Fixed-Point Mathematics
All authoritative calculations use Python `Decimal`, four decimal places, and `ROUND_HALF_UP`.

SQLite persistence uses `FixedDecimal`, which stores the quantized value as an integer scaled by 10,000. The application never stores financial values using SQLite REAL, FLOAT, DOUBLE, or Python binary floating point.

Financial fields are price, quantity, quote price, limit price, cash, reserved cash, available cash, invested value, current value, order notional, absolute P&L, and percentage P&L.

`order_notional = quote_price * quantity`.

BUY placement fails with `InsufficientFundsException` when `order_notional > available_cash`.

Portfolio calculations:
- `holding_invested_value = quantity * average_buy_price`
- `holding_current_value = quantity * current_market_price`
- `absolute_pnl = current_value - total_invested`
- `percent_pnl = (absolute_pnl / total_invested) * 100`

When total invested is zero, percent P&L is zero.

Average BUY price is weighted by quantity. SELL leaves average buy price unchanged.

## Order State Machine
Only these transitions are valid:
- `PENDING -> EXECUTED`
- `PENDING -> CANCELLED`
- `PENDING -> REJECTED`

Every other transition raises `InvalidOrderStateException`.

MARKET orders execute at the accepted quote price. LIMIT BUY executes only when current market price is less than or equal to limit price; LIMIT SELL executes only when current market price is greater than or equal to limit price.

A customer may not sell more than their unreserved current holding. A customer may not submit a new sell order that exceeds quantity remaining after other pending sell orders are reserved.

## Authentication and Authorization
Authentication is enforced at controller level. ADMIN endpoints require `require_admin`. Customers access only their own orders, watchlists, portfolio, and analytics. SUSPENDED users cannot log in or call authenticated customer/admin endpoints.

## Append-Only Rules
- Executed orders are immutable.
- Order events are append-only.
- Execution/trade facts are append-only.
- Audit events are append-only.
- Market ticks are append-only.
- Merged migration files are never edited.
- Stock deletion is soft-delete.

Mutable records are limited to explicitly mutable business state such as PENDING order status, user role, active stock metadata, and watchlist name/membership.

## Configuration
`JWT_SECRET` has no default: the app refuses to start without a secret of at least 32 characters that is not a documented placeholder (only `ENVIRONMENT=test` has a built-in test secret). `scripts/ensure_env.sh` generates `.env`. The synthetic market ticker runs in a single worker (file-lock leader).

## Logging
Structured JSON logs are emitted with `request_correlation_id`. Unhandled 500s return the same correlation id in the body and `X-Request-ID`. Credentials, hashes, tokens, and secrets are excluded.

## Acceptance Criteria Traceability

| ID | Contract | Test requirement |
|---|---|---|
| AC-01 | Registration creates ACTIVE CUSTOMER | At least one test with `AC-01` |
| AC-02 | ADMIN role update with actor/timestamp audit | At least one test with `AC-02` |
| AC-03 | Stock CRUD and soft-delete to DELETED | At least one test with `AC-03` |
| AC-04 | Watchlist max 10 and at least one symbol | At least one test with `AC-04` |
| AC-05 | Watchlist updates are atomic | At least one test with `AC-05` |
| AC-06 | MARKET/LIMIT BUY/SELL enters PENDING | At least one test with `AC-06` |
| AC-07 | PENDING lifecycle is enforced | At least one test with `AC-07` |
| AC-08 | Insufficient BUY funds fail deterministically | At least one test with `AC-08` |
| AC-09 | Portfolio statistics endpoint | At least one test with `AC-09` |
| AC-10 | Top 5 gainers/losers | At least one test with `AC-10` |

## NFR Traceability

| ID | Requirement | Automated enforcement |
|---|---|---|
| NFR-01 | Fixed-point financial math | Decimal domain, FixedDecimal persistence, math hook, tests |
| NFR-02 | Trade/executed-order append-only | Order events, no terminal mutation API, architecture tests |
| NFR-03 | Strong password KDF; no plaintext logging | Argon2, logging tests |
| NFR-04 | Controller authentication and role partitioning | FastAPI dependencies, role-boundary hook/tests |
| NFR-05 | Append-only migrations | Alembic policy + architecture test |
| NFR-06 | Structured JSON + correlation IDs | Logging middleware + test |
| NFR-07 | Health 200 within 1s after startup | health integration test |
| NFR-08 | Architecture rules automated | tests/architecture + Harness architecture hook |

## Review hardening (spec clarifications)

- `PATCH /admin/stocks/{id}` may change `symbol` (normalized to upper case, unique); a clash returns 409.
- `GET /admin/stocks/most-traded` (ADMIN) returns `[{stock_id, symbol, executed_order_count}]`, the same data as `most_traded_stocks` in `/admin/orders/stats`.
- A customer may own at most ten watchlists; a watchlist has no per-watchlist symbol limit. Duplicate names return 409.
- `trades`, `order_events`, `audit_events`, `market_ticks` are append-only and executed orders immutable at the database level (SQLite triggers, migration 0003).
- Responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a restrictive CSP outside `/docs`.
- Session tokens are bearer JWTs kept in `localStorage`; this is an accepted limitation of the capstone scope.
