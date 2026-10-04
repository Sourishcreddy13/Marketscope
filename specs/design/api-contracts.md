# MarketScope API Contract Index

The FastAPI routes are the transport contract. Domain behavior is defined by `specs/app_spec.md`.

## Public
- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`

## Customer
- `GET /api/v1/auth/me`
- `PATCH /api/v1/auth/me`
- `GET /api/v1/stocks`
- `GET /api/v1/market-data`
- `GET /api/v1/watchlists`
- `POST /api/v1/watchlists`
- `PATCH /api/v1/watchlists/{id}`
- `DELETE /api/v1/watchlists/{id}`
- `GET /api/v1/orders`
- `POST /api/v1/orders`
- `POST /api/v1/orders/{id}/cancel`
- `GET /api/v1/portfolio`
- `GET /api/v1/portfolio/daily-stats`
- `GET /api/v1/portfolio/sector-exposure`

## Admin
All routes under `/api/v1/admin/**` require `ADMIN` at the controller boundary.
