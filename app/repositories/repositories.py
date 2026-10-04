from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orm import (
    AuditEvent,
    Order,
    OrderEvent,
    OrderSide,
    OrderStatus,
    Portfolio,
    PortfolioHolding,
    Stock,
    StockStatus,
    Trade,
    User,
    Watchlist,
)


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def list(self, limit: int = 100) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.created_at.desc()).limit(limit)))


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, stock_id: str) -> Stock | None:
        return self.db.get(Stock, stock_id)

    def get_by_symbol(self, symbol: str) -> Stock | None:
        return self.db.scalar(select(Stock).where(Stock.symbol == symbol.upper()))

    def search(self, query: str | None = None, include_deleted: bool = False) -> list[Stock]:
        stmt = select(Stock)
        if not include_deleted:
            stmt = stmt.where(Stock.status == StockStatus.ACTIVE)
        if query:
            token = f"%{query.upper()}%"
            stmt = stmt.where(
                (Stock.symbol.ilike(token))
                | (Stock.name.ilike(token))
                | (Stock.sector.ilike(token))
                | (Stock.exchange.ilike(token))
            )
        return list(self.db.scalars(stmt.order_by(Stock.symbol)))

    def list_all(self) -> list[Stock]:
        return list(self.db.scalars(select(Stock).order_by(Stock.symbol)))


class WatchlistRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def count_for_customer(self, customer_id: str) -> int:
        return int(self.db.scalar(select(func.count(Watchlist.id)).where(Watchlist.customer_id == customer_id)) or 0)

    def list_for_customer(self, customer_id: str) -> list[Watchlist]:
        return list(self.db.scalars(select(Watchlist).where(Watchlist.customer_id == customer_id).order_by(Watchlist.name)))

    def get_owned(self, watchlist_id: str, customer_id: str) -> Watchlist | None:
        return self.db.scalar(select(Watchlist).where(Watchlist.id == watchlist_id, Watchlist.customer_id == customer_id))


class PortfolioRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create(self, customer_id: str, initial_cash: Decimal) -> Portfolio:
        portfolio = self.db.scalar(select(Portfolio).where(Portfolio.customer_id == customer_id))
        if portfolio is None:
            portfolio = Portfolio(customer_id=customer_id, cash_balance=initial_cash)
            self.db.add(portfolio)
            self.db.flush()
        return portfolio

    def get(self, customer_id: str) -> Portfolio | None:
        return self.db.scalar(select(Portfolio).where(Portfolio.customer_id == customer_id))

    def get_holding(self, portfolio_id: str, stock_id: str) -> PortfolioHolding | None:
        return self.db.scalar(select(PortfolioHolding).where(PortfolioHolding.portfolio_id == portfolio_id, PortfolioHolding.stock_id == stock_id))

    def pending_sell_quantity(self, customer_id: str, stock_id: str) -> Decimal:
        rows = self.db.scalars(
            select(Order.quantity).where(
                Order.customer_id == customer_id,
                Order.stock_id == stock_id,
                Order.side == OrderSide.SELL,
                Order.status == OrderStatus.PENDING,
            )
        )
        total = Decimal("0.0000")
        for quantity in rows:
            total += quantity
        return total


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, order_id: str) -> Order | None:
        return self.db.get(Order, order_id)

    def get_by_idempotency_key(self, customer_id: str, key: str) -> Order | None:
        return self.db.scalar(select(Order).where(Order.customer_id == customer_id, Order.idempotency_key == key))

    def list_for_customer(self, customer_id: str) -> list[Order]:
        return list(self.db.scalars(select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())))

    def count_pending_for_customer(self, customer_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(Order.id)).where(Order.customer_id == customer_id, Order.status == OrderStatus.PENDING)
            )
            or 0
        )

    def list_all(self, limit: int = 200) -> list[Order]:
        return list(self.db.scalars(select(Order).order_by(Order.created_at.desc()).limit(limit)))

    def create(self, order: Order) -> Order:
        self.db.add(order)
        self.db.flush()
        return order

    def create_event(self, order_id: str, from_status: str | None, to_status: str, actor_id: str, reason: str | None = None) -> OrderEvent:
        event = OrderEvent(order_id=order_id, from_status=from_status, to_status=to_status, actor_id=actor_id, reason=reason)
        self.db.add(event)
        self.db.flush()
        return event

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(select(Order.status, func.count(Order.id)).group_by(Order.status)).all()
        return {status.value: int(count) for status, count in rows}

    def most_traded(self, limit: int = 10) -> list[tuple[str, str, int]]:
        """Most-traded symbols across the platform as (stock_id, symbol, executed_order_count)."""
        rows = self.db.execute(
            select(Stock.id, Stock.symbol, func.count(Order.id))
            .join(Stock, Stock.id == Order.stock_id)
            .where(Order.status == OrderStatus.EXECUTED)
            .group_by(Stock.id, Stock.symbol)
            .order_by(func.count(Order.id).desc(), Stock.symbol)
            .limit(limit)
        ).all()
        return [(stock_id, symbol, int(count)) for stock_id, symbol, count in rows]


class TradeRepository:
    """Append-only: exposes insert and read operations only."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, trade: Trade) -> Trade:
        self.db.add(trade)
        self.db.flush()
        return trade

    def list_recent(self, limit: int = 200) -> list[Trade]:
        return list(self.db.scalars(select(Trade).order_by(Trade.executed_at.desc()).limit(limit)))

    def get_for_order(self, order_id: str) -> Trade | None:
        return self.db.scalar(select(Trade).where(Trade.order_id == order_id))

    def list_for_customer(self, customer_id: str, limit: int = 200) -> list[Trade]:
        return list(
            self.db.scalars(
                select(Trade).where(Trade.customer_id == customer_id).order_by(Trade.executed_at.desc()).limit(limit)
            )
        )


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, actor_id: str, action: str, target_type: str, target_id: str, correlation_id: str, details: str | None = None) -> AuditEvent:
        event = AuditEvent(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id, request_correlation_id=correlation_id, details=details)
        self.db.add(event)
        self.db.flush()
        return event

    def list_recent(self, limit: int = 100) -> list[AuditEvent]:
        return list(self.db.scalars(select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit)))
