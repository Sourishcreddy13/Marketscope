"""Regression tests for the principal-architect review findings."""
import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.core.security import create_access_token
from app.domain.exceptions import InvalidOrderStateException
from app.models.orm import APPEND_ONLY_TRIGGERS, Order, OrderSide, OrderType, Portfolio, Stock, StockStatus, User, UserRole
from app.services.order_service import OrderService


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def keyed(token):
    return {**auth(token), "Idempotency-Key": f"test-{uuid.uuid4().hex}"}


def stock_id(client, token, symbol="TEST"):
    return next(r["id"] for r in client.get("/api/v1/stocks", headers=auth(token)).json() if r["symbol"] == symbol)


def place_and_execute(client, customer_token, admin_token):
    sid = stock_id(client, customer_token)
    order = client.post(
        "/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1.0000"}, headers=keyed(customer_token)
    ).json()
    assert client.post(f"/api/v1/admin/orders/{order['id']}/execute", headers=auth(admin_token)).status_code == 200
    return order["id"], sid


# ------------------------------------------------------------------ spec endpoint (AC-08)


def test_most_traded_endpoint_is_admin_only_and_ranked(client, customer_token, admin_token):
    assert client.get("/api/v1/admin/stocks/most-traded", headers=auth(customer_token)).status_code == 403
    place_and_execute(client, customer_token, admin_token)
    rows = client.get("/api/v1/admin/stocks/most-traded", headers=auth(admin_token)).json()
    assert rows[0]["symbol"] == "TEST" and rows[0]["executed_order_count"] == 1


# ------------------------------------------------------------------ stock CRUD (AC-03)


@pytest.mark.ac03
def test_admin_can_rename_symbol_and_clashes_are_conflicts(client, admin_token):
    sid = stock_id(client, admin_token, "TEST")
    ok = client.patch(f"/api/v1/admin/stocks/{sid}", json={"symbol": " newt "}, headers=auth(admin_token))
    assert ok.status_code == 200 and ok.json()["symbol"] == "NEWT"
    clash = client.patch(f"/api/v1/admin/stocks/{sid}", json={"symbol": "bank"}, headers=auth(admin_token))
    assert clash.status_code == 409
    blank = client.patch(f"/api/v1/admin/stocks/{sid}", json={"symbol": "   "}, headers=auth(admin_token))
    assert blank.status_code == 422


# ------------------------------------------------------------------ watchlists (AC-04)


@pytest.mark.ac04
def test_duplicate_watchlist_name_is_409_not_500(app_client_no_raise, customer_token):
    client = app_client_no_raise
    sid = stock_id(client, customer_token)
    body = {"name": "Core", "stock_ids": [sid]}
    assert client.post("/api/v1/watchlists", json=body, headers=auth(customer_token)).status_code == 201
    again = client.post("/api/v1/watchlists", json=body, headers=auth(customer_token))
    assert again.status_code == 409


@pytest.mark.ac04
def test_eleventh_watchlist_is_refused(client, customer_token):
    sid = stock_id(client, customer_token)
    for index in range(10):
        assert client.post("/api/v1/watchlists", json={"name": f"L{index}", "stock_ids": [sid]}, headers=auth(customer_token)).status_code == 201
    assert client.post("/api/v1/watchlists", json={"name": "L10", "stock_ids": [sid]}, headers=auth(customer_token)).status_code == 409


# ------------------------------------------------------------------ browser security headers


def test_api_sets_security_headers_and_docs_stay_usable(client):
    api = client.get("/health")
    assert api.headers["X-Content-Type-Options"] == "nosniff"
    assert api.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in api.headers["Content-Security-Policy"]
    docs = client.get("/docs")
    assert docs.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" not in docs.headers


# ------------------------------------------------------------------ reads never write


def test_portfolio_read_does_not_create_a_missing_portfolio(client, db_session):
    user = User(email="noportfolio@test.local", password_hash="x", role=UserRole.CUSTOMER)
    db_session.add(user)
    db_session.commit()
    token = create_access_token(user.id, user.role.value)
    response = client.get("/api/v1/portfolio", headers=auth(token))
    assert response.status_code == 200
    db_session.expire_all()
    assert db_session.query(Portfolio).filter(Portfolio.customer_id == user.id).count() == 0


# ------------------------------------------------------------------ database-level append-only (NFR-02)


@pytest.mark.ac06
def test_raw_sql_cannot_alter_or_remove_ledger_records(client, customer_token, admin_token, db_session):
    order_id, _ = place_and_execute(client, customer_token, admin_token)
    for statement in (
        "UPDATE trades SET quantity = 1",
        "DELETE FROM trades",
        f"UPDATE orders SET quantity = 1 WHERE id = '{order_id}'",
        f"DELETE FROM orders WHERE id = '{order_id}'",
        "UPDATE order_events SET reason = 'x'",
        "DELETE FROM audit_events",
        "UPDATE market_ticks SET price = 1",
    ):
        with pytest.raises(DatabaseError):
            db_session.execute(text(statement))
            db_session.commit()
        db_session.rollback()


def test_pending_orders_remain_mutable_for_the_state_machine(client, customer_token):
    sid = stock_id(client, customer_token)
    order = client.post(
        "/api/v1/orders", json={"stock_id": sid, "side": "BUY", "order_type": "MARKET", "quantity": "1.0000"}, headers=keyed(customer_token)
    ).json()
    assert client.post(f"/api/v1/orders/{order['id']}/cancel", headers=auth(customer_token)).status_code == 200


def test_every_declared_trigger_is_installed(db_session):
    names = {row[0] for row in db_session.execute(text("SELECT name FROM sqlite_master WHERE type = 'trigger'"))}
    assert {f"trg_{name}" for name, _ in APPEND_ONLY_TRIGGERS} <= names


# ------------------------------------------------------------------ concurrent state transitions


def test_two_concurrent_executions_yield_exactly_one_winner(tmp_path):
    """Two sessions race to execute one PENDING order; one wins, the other gets a clean state error."""
    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False, "timeout": 30})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as setup:
        admin = User(email="a@race.local", password_hash="x", role=UserRole.ADMIN)
        customer = User(email="c@race.local", password_hash="x", role=UserRole.CUSTOMER)
        stock = Stock(symbol="RACE", name="Race", sector="S", exchange="X", status=StockStatus.ACTIVE)
        setup.add_all([admin, customer, stock])
        setup.flush()
        setup.add(Portfolio(customer_id=customer.id, cash_balance=Decimal("100000.0000")))
        setup.commit()
        from app.services.market_data import MarketDataService

        MarketDataService(setup).set_price(stock.id, Decimal("10.0000"))
        setup.commit()
        order = OrderService(setup).create(
            customer.id, stock.id, OrderSide.BUY, OrderType.MARKET, Decimal("1.0000"), None, idempotency_key="race-key-0000001"
        )
        admin_id, order_id = admin.id, order.id

    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt() -> None:
        with factory() as session:
            barrier.wait()
            try:
                OrderService(session).execute(admin_id, order_id)
                outcomes.append("ok")
            except InvalidOrderStateException:
                outcomes.append("state")
            except Exception as exc:  # noqa: BLE001 - any other failure is the bug under test
                outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["ok", "state"]
    with factory() as check:
        assert check.query(Order).filter(Order.status == "EXECUTED").count() == 1
    engine.dispose()
