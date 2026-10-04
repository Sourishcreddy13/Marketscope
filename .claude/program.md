# MarketScope Harness Program

## Mission

Build MarketScope entirely through Claude Code agents under human specification and PR supervision.

The capstone source is the requirements authority for application scope. The repository root `specs/app_spec.md` is the executable domain truth.

## Fixed project decisions

- Frontend: React + TypeScript
- Backend: Python + FastAPI
- Transactional database: SQLite
- Analytics/read models: SQLite tables in the same transactional database
- E2E: Playwright
- Browser protocol: Playwright MCP
- Python package/dependency manager: uv
- CI: GitLab CI
- Verification mode: local processes

## Non-negotiable constraints

1. No hand-written production code, migrations, or tests.
2. Specs, CLAUDE files, `.claude/` substrate, sprint contracts, architecture docs, and evidence are human-maintainable.
3. Spec-Is-Truth: when code and spec disagree, fix the spec intentionally or regenerate the code.
4. No direct commits to `main`; every application change reaches `main` through a reviewed PR.
5. Synthetic data only.
6. Fixed-point Decimal arithmetic for all authoritative financial values.
7. Executed orders, execution/trade records, order events, audits, market ticks, and merged migration history are append-only.
8. Authentication/authorization is enforced at the FastAPI controller boundary.
9. Every AC has an explicit AC-NN test reference.
10. Architecture rules are executable tests and hook checks.

## Sprint sequence

### Group SPRINT-01 — Foundation

Stories:
- user-management
- stock-catalog

Primary ACs: AC-01, AC-02, AC-03
Primary NFRs: NFR-03, NFR-04, NFR-05, NFR-06, NFR-07, NFR-08

### Group SPRINT-02 — Watchlist + Portfolio

Stories:
- watchlist
- portfolio

Primary ACs: AC-04, AC-05, AC-09
Primary NFRs: NFR-01, NFR-04, NFR-05, NFR-06, NFR-08

### Group SPRINT-03 — Order Lifecycle

Stories:
- order

Primary ACs: AC-06, AC-07, AC-08
Primary NFRs: NFR-01, NFR-02, NFR-04, NFR-06, NFR-08

### Group SPRINT-04 — Analytics + UI Hardening

Stories:
- analytics
- cross-cutting UI/evidence hardening

Primary ACs: AC-09, AC-10 and regression coverage for AC-01..AC-08
Primary NFRs: NFR-01..NFR-08

## Agent sequence per group

```text
planner
  -> domain specialist (where applicable)
  -> generator / implementer
  -> test-engineer
  -> security-reviewer
  -> evaluator
  -> design-critic in Full mode
  -> self-healing/ratching when failed
  -> PR
```

## Group gates

A group is complete only when:

- all assigned AC checks pass,
- relevant NFR checks pass,
- unit/integration tests pass,
- coverage is at or above baseline and 80% hard floor,
- architecture checks pass,
- Playwright checks pass,
- design checks pass in Full mode,
- evaluator writes `VERDICT: PASS`,
- the change is in a PR-ready commit.

## Self-healing

Maximum 3 attempts per error category. Diagnose before fixing. Fix the smallest failing issue. Preserve learned rules. Never weaken a contract or delete evidence to make an evaluator pass.

## No-go conditions

Stop and escalate when:

- the specification is contradictory and cannot be resolved from the source contract,
- the same error category fails three times without progress,
- architecture boundaries are bypassed repeatedly,
- financial arithmetic still uses floating point after remediation attempts,
- executed-order mutability is detected,
- a production change is proposed outside the agent workflow.

## Human steering knobs

The supervisor may edit this file, sprint contracts, specifications, learned rules, and substrate configuration while the autonomous loop runs.
