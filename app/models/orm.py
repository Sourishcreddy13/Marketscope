from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, event, inspect
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.enums import OrderSide, OrderStatus, OrderType, StockStatus, UserRole
from app.models.types import FixedDecimal

__all__ = ["OrderSide", "OrderStatus", "OrderType", "StockStatus", "UserRole"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# Migration 0001 (append-only, never edited) created both a UNIQUE constraint and a unique index for
# these columns, so the models declare both to stay drift-free (see tests/integration/test_migrations.py).
class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SqlEnum(UserRole, native_enum=False), default=UserRole.CUSTOMER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    last_role_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_role_change_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = (UniqueConstraint("symbol", name="uq_stocks_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(128), index=True)
    exchange: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[StockStatus] = mapped_column(SqlEnum(StockStatus, native_enum=False), default=StockStatus.ACTIVE, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class Watchlist(Base):
    __tablename__ = "watchlists"
    __table_args__ = (UniqueConstraint("customer_id", "name", name="uq_watchlist_customer_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    symbols: Mapped[list["WatchlistSymbol"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan", lazy="selectin"
    )


class WatchlistSymbol(Base):
    __tablename__ = "watchlist_symbols"
    __table_args__ = (UniqueConstraint("watchlist_id", "stock_id", name="uq_watchlist_stock"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    watchlist_id: Mapped[str] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"), index=True)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), index=True)
    watchlist: Mapped[Watchlist] = relationship(back_populates="symbols")


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint("customer_id", name="uq_portfolios_customer_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    cash_balance: Mapped[Decimal] = mapped_column(FixedDecimal(), default=Decimal("100000.0000"))
    reserved_cash: Mapped[Decimal] = mapped_column(FixedDecimal(), default=Decimal("0.0000"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    holdings: Mapped[list["PortfolioHolding"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan", lazy="selectin"
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "stock_id", name="uq_portfolio_stock"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("portfolios.id"), index=True)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(FixedDecimal(), default=Decimal("0.0000"))
    average_buy_price: Mapped[Decimal] = mapped_column(FixedDecimal(), default=Decimal("0.0000"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("uq_orders_customer_idempotency", "customer_id", "idempotency_key", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), index=True)
    side: Mapped[OrderSide] = mapped_column(SqlEnum(OrderSide, native_enum=False))
    order_type: Mapped[OrderType] = mapped_column(SqlEnum(OrderType, native_enum=False))
    quantity: Mapped[Decimal] = mapped_column(FixedDecimal())
    limit_price: Mapped[Decimal | None] = mapped_column(FixedDecimal(), nullable=True)
    quote_price: Mapped[Decimal] = mapped_column(FixedDecimal())
    status: Mapped[OrderStatus] = mapped_column(SqlEnum(OrderStatus, native_enum=False), default=OrderStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Trade(Base):
    """Append-only execution ledger: one immutable row per executed order (NFR-02)."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), index=True)
    side: Mapped[OrderSide] = mapped_column(SqlEnum(OrderSide, native_enum=False))
    quantity: Mapped[Decimal] = mapped_column(FixedDecimal())
    execution_price: Mapped[Decimal] = mapped_column(FixedDecimal())
    notional: Mapped[Decimal] = mapped_column(FixedDecimal())
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    request_correlation_id: Mapped[str] = mapped_column(String(64), default="-")


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(100))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    request_correlation_id: Mapped[str] = mapped_column(String(64), default="-")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class MarketTick(Base):
    __tablename__ = "market_ticks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    stock_id: Mapped[str] = mapped_column(ForeignKey("stocks.id"), index=True)
    price: Mapped[Decimal] = mapped_column(FixedDecimal())
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)


class ImmutableRecordError(RuntimeError):
    """Raised when code attempts to mutate or delete an append-only record."""


@event.listens_for(Trade, "before_update")
@event.listens_for(Trade, "before_delete")
def _trades_are_append_only(_mapper, _connection, target: Trade) -> None:
    raise ImmutableRecordError("trade records are append-only (NFR-02)")


@event.listens_for(Order, "before_delete")
def _orders_are_never_deleted(_mapper, _connection, target: Order) -> None:
    raise ImmutableRecordError("orders are never deleted (NFR-02)")


@event.listens_for(Order, "before_update")
def _executed_orders_are_immutable(_mapper, _connection, target: Order) -> None:
    status_history = inspect(target).attrs.status.history
    previous = status_history.deleted[0] if status_history.deleted else target.status
    if previous == OrderStatus.EXECUTED:
        raise ImmutableRecordError("executed orders are immutable (NFR-02)")


# ---------------------------------------------------------------------------- database-level append-only
# The ORM listeners above stop application code; these SQLite triggers stop everything else (raw SQL,
# Core statements, a future persistence layer). Migration 0003 installs the same triggers on existing databases.
APPEND_ONLY_TRIGGERS: tuple[tuple[str, str], ...] = (
    ("trades_no_update", "CREATE TRIGGER IF NOT EXISTS trg_trades_no_update BEFORE UPDATE ON trades BEGIN SELECT RAISE(ABORT, 'trades are append-only'); END"),
    ("trades_no_delete", "CREATE TRIGGER IF NOT EXISTS trg_trades_no_delete BEFORE DELETE ON trades BEGIN SELECT RAISE(ABORT, 'trades are append-only'); END"),
    ("orders_executed_no_update", "CREATE TRIGGER IF NOT EXISTS trg_orders_executed_no_update BEFORE UPDATE ON orders WHEN OLD.status = 'EXECUTED' BEGIN SELECT RAISE(ABORT, 'executed orders are immutable'); END"),
    ("orders_no_delete", "CREATE TRIGGER IF NOT EXISTS trg_orders_no_delete BEFORE DELETE ON orders BEGIN SELECT RAISE(ABORT, 'orders are never deleted'); END"),
    ("order_events_no_update", "CREATE TRIGGER IF NOT EXISTS trg_order_events_no_update BEFORE UPDATE ON order_events BEGIN SELECT RAISE(ABORT, 'order events are append-only'); END"),
    ("order_events_no_delete", "CREATE TRIGGER IF NOT EXISTS trg_order_events_no_delete BEFORE DELETE ON order_events BEGIN SELECT RAISE(ABORT, 'order events are append-only'); END"),
    ("audit_events_no_update", "CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END"),
    ("audit_events_no_delete", "CREATE TRIGGER IF NOT EXISTS trg_audit_events_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT, 'audit events are append-only'); END"),
    ("market_ticks_no_update", "CREATE TRIGGER IF NOT EXISTS trg_market_ticks_no_update BEFORE UPDATE ON market_ticks BEGIN SELECT RAISE(ABORT, 'market ticks are append-only'); END"),
    ("market_ticks_no_delete", "CREATE TRIGGER IF NOT EXISTS trg_market_ticks_no_delete BEFORE DELETE ON market_ticks BEGIN SELECT RAISE(ABORT, 'market ticks are append-only'); END"),
)


@event.listens_for(Base.metadata, "after_create")
def _install_append_only_triggers(_target, connection, **_kw) -> None:
    if connection.dialect.name != "sqlite":
        return
    existing = {row[0] for row in connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if not {"trades", "orders", "order_events", "audit_events", "market_ticks"} <= existing:
        return
    for _name, ddl in APPEND_ONLY_TRIGGERS:
        connection.exec_driver_sql(ddl)
