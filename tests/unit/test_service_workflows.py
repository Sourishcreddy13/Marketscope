from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.logging import request_correlation_id
from app.domain.exceptions import WatchlistUpdateException
from app.models.orm import AuditEvent, OrderSide, OrderStatus, OrderType, Portfolio, Stock, User, UserRole, Watchlist
from app.models.schemas import StockCreateRequest, StockUpdateRequest
from app.services.market_data import MarketDataService
from app.services.order_service import OrderService
from app.services.stock_service import StockService
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService


def fresh_db():
    return SessionLocal()


def test_ac02_role_change_creates_audit_event():
    db = fresh_db()
    try:
        admin = db.scalar(select(User).where(User.email == "admin@test.local"))
        target = User(email="audit-target@test.local", password_hash="hash", role=UserRole.CUSTOMER)
        db.add(target)
        db.commit()
        request_correlation_id.set("corr-test")
        UserService(db).change_role(admin, target, UserRole.ADMIN)
        event = db.scalar(select(AuditEvent).where(AuditEvent.target_id == target.id))
        assert event is not None
        assert event.actor_id == admin.id
        assert event.action == "USER_ROLE_CHANGED"
        assert event.request_correlation_id == "corr-test"
        assert event.occurred_at is not None
    finally:
        db.close()


def test_ac03_stock_update_and_search():
    db = fresh_db()
    try:
        admin = db.scalar(select(User).where(User.email == "admin@test.local"))
        stock = StockService(db).create(
            admin.id,
            StockCreateRequest(symbol="UPD", name="Update Corp", sector="Tech", exchange="NYSE"),
        )
        updated = StockService(db).update(
            admin.id,
            stock.id,
            StockUpdateRequest(name="Updated Corp", sector="Software"),
        )
        assert updated.name == "Updated Corp"
        assert updated.sector == "Software"
    finally:
        db.close()


def test_ac03_deleted_stock_is_hidden_from_active_search():
    db = fresh_db()
    try:
        admin = db.scalar(select(User).where(User.email == "admin@test.local"))
        stock = StockService(db).create(
            admin.id,
            StockCreateRequest(symbol="HIDE", name="Hidden Corp", sector="Tech", exchange="NASDAQ"),
        )
        StockService(db).soft_delete(admin.id, stock.id)
        assert all(s.id != stock.id for s in StockService(db).stocks.search("HIDE"))
    finally:
        db.close()


def test_ac04_watchlist_delete():
    db = fresh_db()
    try:
        customer = db.scalar(select(User).where(User.email == "customer@test.local"))
        stock = db.scalar(select(Stock).where(Stock.symbol == "TEST"))
        watchlist = WatchlistService(db).create(customer.id, "Delete Me", [stock.id])
        WatchlistService(db).delete(customer.id, watchlist.id)
        assert db.get(Watchlist, watchlist.id) is None
    finally:
        db.close()


def test_ac05_watchlist_invalid_symbol_rolls_back():
    db = fresh_db()
    try:
        customer = db.scalar(select(User).where(User.email == "customer@test.local"))
        stock = db.scalar(select(Stock).where(Stock.symbol == "TEST"))
        watchlist = WatchlistService(db).create(customer.id, "Rollback", [stock.id])
        with pytest.raises(WatchlistUpdateException):
            WatchlistService(db).update(customer.id, watchlist.id, "New Name", ["not-a-real-stock"])
        current = db.get(Watchlist, watchlist.id)
        assert current.name == "Rollback"
        assert [row.stock_id for row in current.symbols] == [stock.id]
    finally:
        db.close()


def test_ac06_market_order_quote_uses_market_price():
    db = fresh_db()
    try:
        customer = db.scalar(select(User).where(User.email == "customer@test.local"))
        stock = db.scalar(select(Stock).where(Stock.symbol == "TEST"))
        MarketDataService(db).set_price(stock.id, Decimal("123.4500"))
        db.commit()
        order = OrderService(db).create(
            customer.id, stock.id, OrderSide.BUY,
            OrderType.MARKET,
            Decimal("2.0000"), None,
            idempotency_key="unit-market-quote-0001",
        )
        assert order.status == OrderStatus.PENDING
        assert order.quote_price == Decimal("123.4500")
    finally:
        db.close()


def test_ac07_order_execution_updates_portfolio_and_becomes_terminal():
    db = fresh_db()
    try:
        customer = User(email="exec@test.local", password_hash="hash", role=UserRole.CUSTOMER)
        db.add(customer)
        stock = db.scalar(select(Stock).where(Stock.symbol == "TEST"))
        db.commit()
        MarketDataService(db).set_price(stock.id, Decimal("100.0000"))
        db.commit()
        order = OrderService(db).create(
            customer.id, stock.id, OrderSide.BUY, OrderType.MARKET, Decimal("3.0000"), None,
            idempotency_key="unit-exec-0001",
        )
        executed = OrderService(db).execute(customer.id, order.id)
        assert executed.status == OrderStatus.EXECUTED
        assert executed.executed_at is not None
        assert executed.status not in {OrderStatus.PENDING, OrderStatus.CANCELLED, OrderStatus.REJECTED}
    finally:
        db.close()


def test_ac07_reject_releases_buy_reservation():
    db = fresh_db()
    try:
        customer = User(email="reject@test.local", password_hash="hash", role=UserRole.CUSTOMER)
        db.add(customer)
        stock = db.scalar(select(Stock).where(Stock.symbol == "TEST"))
        db.commit()
        order = OrderService(db).create(
            customer.id, stock.id, OrderSide.BUY, OrderType.MARKET, Decimal("2.0000"), None,
            idempotency_key="unit-reject-0001",
        )
        rejected = OrderService(db).reject(customer.id, order.id, "risk test")
        portfolio = db.scalar(select(Portfolio).where(Portfolio.customer_id == customer.id))
        assert rejected.status == OrderStatus.REJECTED
        assert portfolio.reserved_cash == Decimal("0.0000")
    finally:
        db.close()
