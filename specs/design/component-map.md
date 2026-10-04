# MarketScope Component Map

| Component | Responsibility | Allowed dependencies |
|---|---|---|
| `app/domain` | business invariants, Decimal calculations | standard library only where practical |
| `app/core` | configuration, DB/session, auth, logging | infrastructure libraries |
| `app/repositories` | persistence access | `app.models`, SQLAlchemy |
| `app/services` | transactional workflows | domain, repositories, core |
| `app/api` | FastAPI transport and controller auth | services, core, schemas |
| `frontend/src` | presentation and HTTP client | browser APIs, React |
