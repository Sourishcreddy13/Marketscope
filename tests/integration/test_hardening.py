"""Regression tests for the defect-log fixes (idempotency, ledger, logging, validation, rate limits)."""
import json
import logging
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.logging import JsonFormatter
from app.core.rate_limit import auth_rate_limiter
from app.models.orm import ImmutableRecordError, Order, OrderStatus, Portfolio, Trade, User
from app.services.market_data import MarketDataService


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def keyed(token, key=None):
    return {**auth(token), "Idempotency-Key": key or f"test-{uuid.uuid4().hex}"}


def stock_id(client, token, symbol="TEST"):
    rows = client.get("/api/v1/stocks", headers=auth(token)).json()
    return next(row["id"] for row in rows if row["symbol"] == symbol)


def market_buy(sid, quantity="2.0000"):
    return {"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": quantity}


# ---------------------------------------------------------------- idempotency (AC-06)


@pytest.mark.ac06
def test_order_requires_idempotency_key(client, customer_token):
    sid = stock_id(client, customer_token)
    missing = client.post("/api/v1/orders", json=market_buy(sid), headers=auth(customer_token))
    assert missing.status_code == 400
    malformed = client.post("/api/v1/orders", json=market_buy(sid), headers=keyed(customer_token, "short"))
    assert malformed.status_code == 400


@pytest.mark.ac06
def test_replayed_order_request_creates_exactly_one_order(client, customer_token, db_session):
    sid = stock_id(client, customer_token)
    headers = keyed(customer_token, "replay-key-00000001")
    first = client.post("/api/v1/orders", json=market_buy(sid), headers=headers)
    second = client.post("/api/v1/orders", json=market_buy(sid), headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.headers["Idempotent-Replay"] == "true"
    assert second.json()["id"] == first.json()["id"]
    assert db_session.scalar(select(func.count(Order.id))) == 1
    # Cash is reserved once, not twice.
    portfolio = db_session.scalar(select(Portfolio).join(User, User.id == Portfolio.customer_id).where(User.email == "customer@test.local"))
    assert portfolio.reserved_cash == Decimal("200.0000")


@pytest.mark.ac06
def test_idempotency_key_reuse_with_different_payload_is_rejected(client, customer_token, db_session):
    sid = stock_id(client, customer_token)
    headers = keyed(customer_token, "conflict-key-0000001")
    assert client.post("/api/v1/orders", json=market_buy(sid, "1.0000"), headers=headers).status_code == 201
    conflict = client.post("/api/v1/orders", json=market_buy(sid, "5.0000"), headers=headers)
    assert conflict.status_code == 422
    assert db_session.scalar(select(func.count(Order.id))) == 1


@pytest.mark.ac06
def test_idempotency_keys_are_scoped_per_customer(client, customer_token, other_customer_token):
    sid = stock_id(client, customer_token)
    key = "shared-key-00000001"
    a = client.post("/api/v1/orders", json=market_buy(sid), headers=keyed(customer_token, key))
    b = client.post("/api/v1/orders", json=market_buy(sid), headers=keyed(other_customer_token, key))
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


# ---------------------------------------------------------------- trade ledger (NFR-02)


def _place_and_execute(client, customer_token, admin_token, quantity="3.0000"):
    sid = stock_id(client, customer_token)
    placed = client.post("/api/v1/orders", json=market_buy(sid, quantity), headers=keyed(customer_token))
    order_id = placed.json()["id"]
    assert client.post(f"/api/v1/admin/orders/{order_id}/execute", headers=auth(admin_token)).status_code == 200
    return order_id


@pytest.mark.nfr02
def test_execution_writes_typed_append_only_trade_record(client, customer_token, admin_token, db_session):
    order_id = _place_and_execute(client, customer_token, admin_token)
    trade = db_session.scalar(select(Trade).where(Trade.order_id == order_id))
    assert trade is not None
    assert trade.execution_price == Decimal("100.0000")
    assert trade.quantity == Decimal("3.0000")
    assert trade.notional == Decimal("300.0000")
    assert trade.side.value == "BUY"
    assert trade.executed_at is not None
    admin = db_session.scalar(select(User).where(User.email == "admin@test.local"))
    assert trade.actor_id == admin.id
    listed = client.get("/api/v1/admin/trades", headers=auth(admin_token)).json()
    assert [row["order_id"] for row in listed] == [order_id]


@pytest.mark.nfr02
def test_trade_records_cannot_be_updated_or_deleted(client, customer_token, admin_token):
    order_id = _place_and_execute(client, customer_token, admin_token)
    db = SessionLocal()
    try:
        trade = db.scalar(select(Trade).where(Trade.order_id == order_id))
        trade.execution_price = Decimal("1.0000")
        with pytest.raises(ImmutableRecordError):
            db.flush()
        db.rollback()
        trade = db.scalar(select(Trade).where(Trade.order_id == order_id))
        db.delete(trade)
        with pytest.raises(ImmutableRecordError):
            db.flush()
        db.rollback()
    finally:
        db.close()


@pytest.mark.nfr02
def test_executed_order_cannot_be_mutated_or_deleted(client, customer_token, admin_token):
    order_id = _place_and_execute(client, customer_token, admin_token)
    db = SessionLocal()
    try:
        order = db.get(Order, order_id)
        order.status = OrderStatus.CANCELLED
        with pytest.raises(ImmutableRecordError):
            db.flush()
        db.rollback()
        order = db.get(Order, order_id)
        db.delete(order)
        with pytest.raises(ImmutableRecordError):
            db.flush()
        db.rollback()
    finally:
        db.close()


@pytest.mark.ac07
def test_double_execution_is_rejected_and_writes_one_trade(client, customer_token, admin_token, db_session):
    order_id = _place_and_execute(client, customer_token, admin_token)
    again = client.post(f"/api/v1/admin/orders/{order_id}/execute", headers=auth(admin_token))
    assert again.status_code == 409
    assert db_session.scalar(select(func.count(Trade.id))) == 1


# ---------------------------------------------------------------- transactional atomicity


@pytest.mark.ac08
def test_failed_execution_leaves_no_partial_state_on_a_reused_session(client, customer_token):
    """If execution fails validation, a session reused by the caller must not hold dirty state."""
    from app.domain.exceptions import InsufficientFundsException
    from app.services.order_service import OrderService

    sid = stock_id(client, customer_token)
    db = SessionLocal()
    try:
        customer = db.scalar(select(User).where(User.email == "customer@test.local"))
        service = OrderService(db)
        order = service.create(customer.id, sid, __import__("app.models.orm", fromlist=["OrderSide"]).OrderSide.BUY,
                               __import__("app.models.orm", fromlist=["OrderType"]).OrderType.MARKET,
                               Decimal("10.0000"), None, idempotency_key="atomic-key-0000001")
        # Drain the customer's cash behind the service's back so execution must fail.
        portfolio = db.scalar(select(Portfolio).where(Portfolio.customer_id == customer.id))
        portfolio.cash_balance = Decimal("1.0000")
        db.commit()
        reserved_before = portfolio.reserved_cash

        with pytest.raises(InsufficientFundsException):
            service.execute(customer.id, order.id)

        db.expire_all()
        portfolio = db.scalar(select(Portfolio).where(Portfolio.customer_id == customer.id))
        assert portfolio.cash_balance == Decimal("1.0000")
        assert portfolio.reserved_cash == reserved_before
        assert db.get(Order, order.id).status == OrderStatus.PENDING
        assert db.scalar(select(func.count(Trade.id))) == 0
        assert not db.dirty and not db.new
    finally:
        db.close()


# ---------------------------------------------------------------- logging / request ids (NFR-06)


@pytest.mark.nfr06
def test_request_log_has_native_structured_fields(client, caplog):
    with caplog.at_level(logging.INFO, logger="marketscope"):
        client.get("/health", headers={"X-Request-ID": "corr-abc-123"})
    record = next(r for r in caplog.records if r.getMessage() == "request_completed")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["method"] == "GET"
    assert payload["path"] == "/health"
    assert payload["status_code"] == 200
    assert isinstance(payload["duration_ms"], float)
    assert payload["message"] == "request_completed"  # no data buried in the message string
    assert "correlation_id" in payload


@pytest.mark.nfr06
def test_unhandled_error_returns_the_generated_correlation_id(app_client_no_raise, monkeypatch, customer_token):
    from app.services.order_service import OrderService

    def boom(self, customer_id):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(OrderService, "list_for_customer", boom)
    response = app_client_no_raise.get("/api/v1/orders", headers=auth(customer_token))
    assert response.status_code == 500
    body = response.json()
    assert body["request_id"] not in {"-", ""}
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert "synthetic failure" not in response.text


@pytest.mark.nfr06
def test_untrusted_request_id_header_is_replaced(client):
    response = client.get("/health", headers={"X-Request-ID": 'bad id"\n{"forged":true}'})
    assert response.headers["X-Request-ID"] != 'bad id"\n{"forged":true}'
    assert len(response.headers["X-Request-ID"]) <= 64


# ---------------------------------------------------------------- validation


@pytest.mark.ac03
def test_blank_stock_fields_are_rejected_after_trimming(client, admin_token):
    for payload in (
        {"symbol": "   ", "name": "Name", "sector": "Tech", "exchange": "X"},
        {"symbol": "ZZZ", "name": "\t", "sector": "Tech", "exchange": "X"},
        {"symbol": "ZZZ", "name": "Name", "sector": " ", "exchange": "X"},
        {"symbol": "ZZZ", "name": "Name", "sector": "Tech", "exchange": "  "},
    ):
        assert client.post("/api/v1/admin/stocks", json=payload, headers=auth(admin_token)).status_code == 422
    rows = client.get("/api/v1/admin/stocks", headers=auth(admin_token)).json()
    assert all(row["symbol"].strip() for row in rows)


@pytest.mark.ac03
def test_blank_stock_update_is_rejected(client, admin_token):
    sid = stock_id(client, admin_token)
    response = client.patch(f"/api/v1/admin/stocks/{sid}", json={"name": "   "}, headers=auth(admin_token))
    assert response.status_code == 422


@pytest.mark.ac03
def test_stock_service_rejects_blank_values_even_without_schema(db_session):
    from app.domain.exceptions import InvalidInputException
    from app.models.schemas import StockCreateRequest
    from app.services.stock_service import StockService

    request = StockCreateRequest.model_construct(symbol="  ", name="Name", sector="Sector", exchange="X")
    with pytest.raises(InvalidInputException):
        StockService(db_session).create("actor", request)


@pytest.mark.ac01
def test_invalid_email_addresses_are_rejected(client):
    for email in ("not-an-email", "a@b", "x@@y.com", "spaces in@example.com", ""):
        response = client.post("/api/v1/auth/register", json={"email": email, "password": "Password@123"})
        assert response.status_code == 422, email
        assert client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"}).status_code == 422


@pytest.mark.ac01
def test_email_is_normalized_once_at_the_boundary(client):
    created = client.post("/api/v1/auth/register", json={"email": "  MiXeD@Example.COM ", "password": "Password@123"})
    assert created.status_code == 201
    assert created.json()["user"]["email"] == "mixed@example.com"
    login = client.post("/api/v1/auth/login", json={"email": "MIXED@example.com", "password": "Password@123"})
    assert login.status_code == 200


# ---------------------------------------------------------------- abuse control


@pytest.mark.nfr04
def test_login_and_register_are_rate_limited(client, monkeypatch):
    monkeypatch.setattr(auth_rate_limiter, "max_attempts", 3)
    auth_rate_limiter.reset()
    codes = [
        client.post("/api/v1/auth/login", json={"email": "customer@test.local", "password": "wrong-password"}).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]
    blocked = client.post("/api/v1/auth/login", json={"email": "customer@test.local", "password": "wrong-password"})
    assert int(blocked.headers["Retry-After"]) >= 1
    # Registration has its own bucket.
    assert client.post("/api/v1/auth/register", json={"email": "rl@example.com", "password": "Password@123"}).status_code == 201


# ---------------------------------------------------------------- admin statistics


@pytest.mark.ac07
def test_most_traded_returns_symbols_with_counts(client, customer_token, admin_token):
    _place_and_execute(client, customer_token, admin_token, "1.0000")
    _place_and_execute(client, customer_token, admin_token, "2.0000")
    stats = client.get("/api/v1/admin/orders/stats", headers=auth(admin_token)).json()
    assert stats["most_traded_stocks"][0]["symbol"] == "TEST"
    assert stats["most_traded_stocks"][0]["executed_order_count"] == 2


# ---------------------------------------------------------------- account lifecycle (user CRUD)


@pytest.mark.ac01
def test_customer_can_close_account_without_losing_history(client, customer_token, db_session):
    response = client.request("DELETE", "/api/v1/auth/me", json={"current_password": "Customer@12345"}, headers=auth(customer_token))
    assert response.status_code == 200
    assert response.json()["role"] == "SUSPENDED"
    assert client.post("/api/v1/auth/login", json={"email": "customer@test.local", "password": "Customer@12345"}).status_code == 403
    assert db_session.scalar(select(User).where(User.email == "customer@test.local")) is not None  # never hard-deleted


@pytest.mark.ac01
def test_account_closure_requires_password_and_no_pending_orders(client, customer_token):
    wrong = client.request("DELETE", "/api/v1/auth/me", json={"current_password": "Wrong@12345"}, headers=auth(customer_token))
    assert wrong.status_code == 409
    sid = stock_id(client, customer_token)
    client.post("/api/v1/orders", json=market_buy(sid), headers=keyed(customer_token))
    pending = client.request("DELETE", "/api/v1/auth/me", json={"current_password": "Customer@12345"}, headers=auth(customer_token))
    assert pending.status_code == 409


@pytest.mark.nfr04
def test_admin_cannot_self_close(client, admin_token):
    response = client.request("DELETE", "/api/v1/auth/me", json={"current_password": "Admin@12345"}, headers=auth(admin_token))
    assert response.status_code == 409


def test_market_price_fixture_is_decimal(db_session):
    assert isinstance(MarketDataService(db_session).get_price(stock_id_from_db(db_session)), Decimal)


def stock_id_from_db(db):
    from app.models.orm import Stock

    return db.scalar(select(Stock.id).where(Stock.symbol == "TEST"))


# ---------------------------------------------------------------- watchlist edits keep unchanged symbols (AC-05)


@pytest.mark.ac05
def test_watchlist_update_can_keep_existing_symbols_while_adding_and_removing(client, customer_token):
    rows = client.get("/api/v1/stocks", headers=auth(customer_token)).json()
    a, b, c = (row["id"] for row in rows[:3])
    created = client.post("/api/v1/watchlists", json={"name": "Keep", "stock_ids": [a, b]}, headers=auth(customer_token)).json()
    url = f"/api/v1/watchlists/{created['id']}"

    added = client.patch(url, json={"name": "Keep 2", "stock_ids": [a, b, c]}, headers=auth(customer_token))
    assert added.status_code == 200
    assert sorted(added.json()["stock_ids"]) == sorted([a, b, c])

    swapped = client.patch(url, json={"stock_ids": [b, c]}, headers=auth(customer_token))
    assert swapped.status_code == 200
    assert sorted(swapped.json()["stock_ids"]) == sorted([b, c])
    assert swapped.json()["name"] == "Keep 2"

    unchanged = client.patch(url, json={"stock_ids": [b, c]}, headers=auth(customer_token))
    assert unchanged.status_code == 200


# ---------------------------------------------------------------------------- manual-test follow-ups


@pytest.mark.ac10
def test_synthetic_prices_stay_within_a_bounded_walk(db_session):
    from decimal import Decimal

    from app.models.orm import Stock
    from app.services.market_data import WALK_CEILING, WALK_FLOOR, MarketDataService

    stock = db_session.scalar(select(Stock))
    service = MarketDataService(db_session)
    service.set_price(stock.id, Decimal("100.0000"))
    reference = service.get_reference_price(stock.id)
    for _ in range(400):
        service.tick_all()
    price = service.get_price(stock.id)
    assert reference * WALK_FLOOR <= price <= reference * WALK_CEILING


@pytest.mark.ac10
def test_quotes_report_server_computed_change_against_the_previous_tick(client, admin_token, customer_token):
    from decimal import Decimal

    from app.core.db import SessionLocal
    from app.services.market_data import MarketDataService

    sid = stock_id(client, customer_token, "TEST")
    with SessionLocal() as db:
        service = MarketDataService(db)
        service.set_price(sid, Decimal("100.0000"))
        service.set_price(sid, Decimal("110.0000"))
        db.commit()
    row = next(q for q in client.get("/api/v1/market-data", headers=auth(customer_token)).json() if q["stock_id"] == sid)
    assert row["previous_price"] == "100.0000" and row["change_percent"] == "10.0000"


def test_field_validation_errors_are_readable_strings_for_the_ui(client, admin_token):
    response = client.post(
        "/api/v1/admin/stocks", json={"symbol": "   ", "name": "x", "sector": "y", "exchange": "z"}, headers=auth(admin_token)
    )
    assert response.status_code == 422
    assert "blank" in str(response.json()["detail"]).lower()


def test_default_login_limit_is_five_attempts_per_window():
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "AUTH_RATE_LIMIT_ATTEMPTS"}
    code = "from app.core.config import settings; print(settings.auth_rate_limit_attempts)"
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env).stdout.strip() == "5"
