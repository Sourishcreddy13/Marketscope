from __future__ import annotations

import time
import uuid
from decimal import Decimal

from sqlalchemy import select

from app.models.orm import AuditEvent, Order, Portfolio, User


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def order_auth(token: str) -> dict[str, str]:
    """Auth headers plus a fresh Idempotency-Key, as required by POST /orders."""
    return {**auth(token), "Idempotency-Key": f"test-{uuid.uuid4().hex}"}


def stock_id(client, token, symbol="TEST"):
    rows = client.get("/api/v1/stocks", headers=auth(token)).json()
    return next(row["id"] for row in rows if row["symbol"] == symbol)


def test_health_is_fast_and_correlated(client):
    started = time.perf_counter()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["database"] == "sqlite"
    assert response.headers["X-Request-ID"]
    assert time.perf_counter() - started < 1


def test_ac01_registration_creates_active_customer_and_token(client, db_session):
    response = client.post("/api/v1/auth/register", json={"email": "new-user@test.local", "password": "Password@123"})
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["role"] == "CUSTOMER"
    assert body["access_token"]
    user = db_session.scalar(select(User).where(User.email == "new-user@test.local"))
    portfolio = db_session.scalar(select(Portfolio).where(Portfolio.customer_id == user.id))
    assert user is not None
    assert portfolio is not None


def test_ac01_duplicate_email_is_rejected(client):
    client.post("/api/v1/auth/register", json={"email": "duplicate@test.local", "password": "Password@123"})
    response = client.post("/api/v1/auth/register", json={"email": "duplicate@test.local", "password": "Password@123"})
    assert response.status_code == 409


def test_nfr03_password_hash_not_exposed_and_login_works(client):
    body = client.post("/api/v1/auth/login", json={"email": "customer@test.local", "password": "Customer@12345"}).json()
    assert body["access_token"]
    assert "password_hash" not in body["user"]
    assert "Customer@12345" not in str(body)


def test_nfr04_customer_cannot_access_admin_boundaries(client, customer_token):
    assert client.get("/api/v1/admin/users", headers=auth(customer_token)).status_code == 403
    assert client.post("/api/v1/admin/market-data/tick", headers=auth(customer_token)).status_code == 403


def test_ac02_admin_role_change_is_audited(client, admin_token, db_session):
    created = client.post("/api/v1/auth/register", json={"email": "role-target@test.local", "password": "Password@123"})
    target_id = created.json()["user"]["id"]
    response = client.patch(f"/api/v1/admin/users/{target_id}/role", json={"role": "SUSPENDED"}, headers=auth(admin_token))
    assert response.status_code == 200
    assert response.json()["role"] == "SUSPENDED"
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.target_id == target_id).order_by(AuditEvent.occurred_at.desc()))
    assert event is not None
    assert event.actor_id != target_id
    assert event.action == "USER_ROLE_CHANGED"
    assert event.occurred_at is not None


def test_ac02_suspended_user_cannot_login(client, admin_token):
    created = client.post("/api/v1/auth/register", json={"email": "suspended@test.local", "password": "Password@123"})
    target_id = created.json()["user"]["id"]
    assert client.patch(f"/api/v1/admin/users/{target_id}/role", json={"role": "SUSPENDED"}, headers=auth(admin_token)).status_code == 200
    response = client.post("/api/v1/auth/login", json={"email": "suspended@test.local", "password": "Password@123"})
    assert response.status_code == 403
    assert "suspended" in response.json()["detail"]
    # The suspension is only revealed to someone who proves they own the account.
    wrong = client.post("/api/v1/auth/login", json={"email": "suspended@test.local", "password": "Wrong@Password1"})
    assert wrong.status_code == 401 and wrong.json()["detail"] == "invalid credentials"


def test_profile_update_requires_current_password_for_password_change(client, customer_token):
    response = client.patch("/api/v1/auth/me", json={"new_password": "NewPassword@123"}, headers=auth(customer_token))
    assert response.status_code == 409
    ok = client.patch("/api/v1/auth/me", json={"current_password": "Customer@12345", "new_password": "NewPassword@123"}, headers=auth(customer_token))
    assert ok.status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "customer@test.local", "password": "NewPassword@123"}).status_code == 200


def test_ac03_admin_has_stock_crud_and_soft_delete(client, admin_token, customer_token):
    create = client.post("/api/v1/admin/stocks", json={"symbol": "CRUD", "name": "CRUD Co", "sector": "Technology", "exchange": "NASDAQ"}, headers=auth(admin_token))
    assert create.status_code == 201
    stock_id_value = create.json()["id"]
    update = client.patch(f"/api/v1/admin/stocks/{stock_id_value}", json={"name": "CRUD Updated"}, headers=auth(admin_token))
    assert update.status_code == 200
    assert update.json()["name"] == "CRUD Updated"
    listing = client.get("/api/v1/admin/stocks", headers=auth(admin_token)).json()
    assert any(row["id"] == stock_id_value for row in listing)
    deleted = client.delete(f"/api/v1/admin/stocks/{stock_id_value}", headers=auth(admin_token))
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "DELETED"
    active = client.get("/api/v1/stocks?q=CRUD", headers=auth(customer_token)).json()
    assert all(row["id"] != stock_id_value for row in active)


def test_ac04_watchlist_create_and_ten_limit(client, customer_token):
    ids = [stock_id(client, customer_token, "TEST"), stock_id(client, customer_token, "BANK")]
    created = client.post("/api/v1/watchlists", json={"name": "Primary", "stock_ids": ids[:1]}, headers=auth(customer_token))
    assert created.status_code == 201
    for index in range(2, 11):
        assert client.post("/api/v1/watchlists", json={"name": f"List {index}", "stock_ids": [ids[0]]}, headers=auth(customer_token)).status_code == 201
    rejected = client.post("/api/v1/watchlists", json={"name": "Eleventh", "stock_ids": [ids[0]]}, headers=auth(customer_token))
    assert rejected.status_code == 409


def test_ac05_watchlist_update_is_atomic_and_delete_works(client, customer_token):
    sid = stock_id(client, customer_token)
    created = client.post("/api/v1/watchlists", json={"name": "Atomic", "stock_ids": [sid]}, headers=auth(customer_token))
    wid = created.json()["id"]
    failed = client.patch(f"/api/v1/watchlists/{wid}", json={"name": "", "stock_ids": ["missing"]}, headers=auth(customer_token))
    assert failed.status_code == 409
    current = next(row for row in client.get("/api/v1/watchlists", headers=auth(customer_token)).json() if row["id"] == wid)
    assert current["name"] == "Atomic"
    assert current["stock_ids"] == [sid]
    assert client.delete(f"/api/v1/watchlists/{wid}", headers=auth(customer_token)).status_code == 204


def test_ac06_market_and_limit_orders_enter_pending(client, customer_token):
    sid = stock_id(client, customer_token)
    market = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "2.0000"}, headers=order_auth(customer_token))
    assert market.status_code == 201
    assert market.json()["status"] == "PENDING"
    assert market.json()["created_at"]
    limit = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "LIMIT", "quantity": "1.0000", "limit_price": "95.0000"}, headers=order_auth(customer_token))
    assert limit.status_code == 201
    assert limit.json()["quote_price"] == "95.0000"


def test_ac07_invalid_transition_is_rejected(client, admin_token, customer_token, db_session):
    sid = stock_id(client, customer_token)
    created = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1.0000"}, headers=order_auth(customer_token))
    oid = created.json()["id"]
    assert client.post(f"/api/v1/admin/orders/{oid}/execute", headers=auth(admin_token)).status_code == 200
    second = client.post(f"/api/v1/admin/orders/{oid}/execute", headers=auth(admin_token))
    assert second.status_code == 409
    event_count = db_session.query(Order).filter(Order.id == oid).count()
    assert event_count == 1


def test_ac07_customer_can_cancel_pending_and_reserved_cash_is_released(client, customer_token):
    sid = stock_id(client, customer_token)
    portfolio_before = client.get("/api/v1/portfolio", headers=auth(customer_token)).json()
    created = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "2.0000"}, headers=order_auth(customer_token))
    assert created.status_code == 201
    during = client.get("/api/v1/portfolio", headers=auth(customer_token)).json()
    assert Decimal(during["available_cash"]) < Decimal(portfolio_before["available_cash"])
    cancelled = client.post(f"/api/v1/orders/{created.json()['id']}/cancel", headers=auth(customer_token))
    assert cancelled.status_code == 200
    after = client.get("/api/v1/portfolio", headers=auth(customer_token)).json()
    assert Decimal(after["available_cash"]) == Decimal(portfolio_before["available_cash"])


def test_ac08_buy_rejects_when_quote_notional_exceeds_available_cash(client, customer_token):
    sid = stock_id(client, customer_token)
    response = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1000000"}, headers=order_auth(customer_token))
    assert response.status_code == 409
    assert "available cash" in response.text.lower()


def test_sell_cannot_exceed_owned_position(client, customer_token, admin_token):
    sid = stock_id(client, customer_token)
    buy = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "3.0000"}, headers=order_auth(customer_token))
    assert buy.status_code == 201
    assert client.post(f"/api/v1/admin/orders/{buy.json()['id']}/execute", headers=auth(admin_token)).status_code == 200
    sell = client.post("/api/v1/orders", json={"stock_id": sid, "side": "SELL", "order_type": "MARKET", "quantity": "4.0000"}, headers=order_auth(customer_token))
    assert sell.status_code == 400


def test_ac09_portfolio_statistics_returns_required_customer_scoped_fields(client, customer_token, admin_token):
    sid = stock_id(client, customer_token)
    buy = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "2.0000"}, headers=order_auth(customer_token))
    assert client.post(f"/api/v1/admin/orders/{buy.json()['id']}/execute", headers=auth(admin_token)).status_code == 200
    body = client.get("/api/v1/portfolio", headers=auth(customer_token)).json()
    assert {"total_invested", "current_value", "absolute_pnl", "percent_pnl"}.issubset(body)
    assert any(row["symbol"] == "TEST" for row in body["holdings"])


def test_ac10_daily_stats_are_top_five_and_customer_scoped(client, customer_token, admin_token, other_customer_token):
    sid = stock_id(client, customer_token, "TEST")
    buy = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1.0000"}, headers=order_auth(customer_token))
    assert client.post(f"/api/v1/admin/orders/{buy.json()['id']}/execute", headers=auth(admin_token)).status_code == 200
    body = client.get("/api/v1/portfolio/daily-stats", headers=auth(customer_token)).json()
    assert len(body["top_5_gainers"]) <= 5
    assert len(body["top_5_losers"]) <= 5
    # A flat position is neither a gainer nor a loser.
    assert body["top_5_gainers"] == [] and body["top_5_losers"] == []
    other = client.get("/api/v1/portfolio/daily-stats", headers=auth(other_customer_token)).json()
    assert other["top_5_gainers"] == []
    assert other["top_5_losers"] == []


def test_market_data_is_persistent_and_admin_tick_is_protected(client, customer_token, admin_token):
    quotes = client.get("/api/v1/market-data", headers=auth(customer_token))
    assert quotes.status_code == 200
    assert quotes.json()
    assert client.post("/api/v1/admin/market-data/tick", headers=auth(customer_token)).status_code == 403
    tick = client.post("/api/v1/admin/market-data/tick", headers=auth(admin_token))
    assert tick.status_code == 200
    assert tick.json()["updated_symbols"] >= 1


def test_customer_cannot_read_another_customers_orders(client, customer_token, other_customer_token):
    sid = stock_id(client, customer_token)
    response = client.post("/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1.0000"}, headers=order_auth(customer_token))
    assert response.status_code == 201
    other_orders = client.get("/api/v1/orders", headers=auth(other_customer_token)).json()
    assert all(row["customer_id"] != response.json()["customer_id"] for row in other_orders)
