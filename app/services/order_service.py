from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import acquire_write_lock
from app.core.logging import request_correlation_id
from app.domain.exceptions import (
    DomainValidationException,
    IdempotencyConflictException,
    InsufficientFundsException,
)
from app.domain.money import D, notional
from app.domain.order_policy import validate_buy_funds, validate_order_shape, validate_transition
from app.domain.portfolio_policy import update_after_buy, update_after_sell
from app.models.orm import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Portfolio,
    PortfolioHolding,
    StockStatus,
    Trade,
)
from app.repositories.repositories import (
    AuditRepository,
    OrderRepository,
    PortfolioRepository,
    StockRepository,
    TradeRepository,
)
from app.services.market_data import MarketDataService

ZERO = Decimal("0.0000")


@dataclass(frozen=True)
class Placement:
    """Result of placing an order; `replayed` is True when an idempotency key matched an earlier request."""

    order: Order
    replayed: bool


def request_fingerprint(stock_id: str, side: OrderSide, order_type: OrderType, quantity: Decimal, limit_price: Decimal | None) -> str:
    canonical = "|".join(
        [stock_id, side.value, order_type.value, f"{D(quantity):.4f}", f"{D(limit_price):.4f}" if limit_price is not None else "-"]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class OrderService:
    """Owns the unit of work for every order operation.

    Each public mutating method runs inside `_unit_of_work`: all validation happens before any
    state is mutated, the whole change commits once, and any failure path rolls the session back
    so no half-applied reservation, cash, holding or status change can leak to a caller that
    reuses the session.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = OrderRepository(db)
        self.stocks = StockRepository(db)
        self.portfolios = PortfolioRepository(db)
        self.audits = AuditRepository(db)
        self.trades = TradeRepository(db)
        self.market_data = MarketDataService(db)

    @contextmanager
    def _unit_of_work(self) -> Iterator[None]:
        try:
            acquire_write_lock(self.db)
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def _quote(self, stock_id: str) -> Decimal:
        return self.market_data.get_price(stock_id)

    # ------------------------------------------------------------------ placement

    def create(
        self,
        customer_id: str,
        stock_id: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        limit_price: Decimal | None,
        *,
        idempotency_key: str,
    ) -> Order:
        return self.place(customer_id, stock_id, side, order_type, quantity, limit_price, idempotency_key=idempotency_key).order

    def place(
        self,
        customer_id: str,
        stock_id: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        limit_price: Decimal | None,
        *,
        idempotency_key: str,
    ) -> Placement:
        if not idempotency_key or not idempotency_key.strip():
            raise DomainValidationException("an idempotency key is required to place an order")
        quantity = D(quantity)
        limit_price = D(limit_price) if limit_price is not None else None
        fingerprint = request_fingerprint(stock_id, side, order_type, quantity, limit_price)

        replay = self._find_replay(customer_id, idempotency_key, fingerprint)
        if replay is not None:
            return Placement(replay, True)

        try:
            with self._unit_of_work():
                order = self._place_new(customer_id, stock_id, side, order_type, quantity, limit_price, idempotency_key, fingerprint)
        except IntegrityError:
            # A concurrent request with the same key won the race: serve its result.
            replay = self._find_replay(customer_id, idempotency_key, fingerprint)
            if replay is None:
                raise
            return Placement(replay, True)
        self.db.refresh(order)
        return Placement(order, False)

    def _find_replay(self, customer_id: str, key: str, fingerprint: str) -> Order | None:
        existing = self.orders.get_by_idempotency_key(customer_id, key)
        if existing is None:
            return None
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflictException("idempotency key was already used with a different order request")
        return existing

    def _place_new(
        self,
        customer_id: str,
        stock_id: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        limit_price: Decimal | None,
        idempotency_key: str,
        fingerprint: str,
    ) -> Order:
        stock = self.stocks.get(stock_id)
        if stock is None or stock.status != StockStatus.ACTIVE:
            raise DomainValidationException("stock is not tradable")
        validate_order_shape(side, order_type, quantity, limit_price)

        portfolio = self.portfolios.get_or_create(customer_id, D(settings.initial_cash))
        available_cash = D(portfolio.cash_balance) - D(portfolio.reserved_cash)
        quote_price = D(limit_price) if order_type == OrderType.LIMIT and limit_price is not None else self._quote(stock_id)

        # Validate first, mutate afterwards.
        reservation = ZERO
        if side == OrderSide.BUY:
            validate_buy_funds(quote_price, quantity, available_cash)
            reservation = notional(quote_price, quantity)
        else:
            holding = self.portfolios.get_holding(portfolio.id, stock_id)
            held_quantity = D(holding.quantity) if holding else ZERO
            sellable = held_quantity - self.portfolios.pending_sell_quantity(customer_id, stock_id)
            if quantity > sellable:
                raise DomainValidationException("SELL order exceeds available holding")

        order = Order(
            customer_id=customer_id,
            stock_id=stock_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            quote_price=quote_price,
            status=OrderStatus.PENDING,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        self.orders.create(order)
        if reservation:
            portfolio.reserved_cash = D(portfolio.reserved_cash) + reservation
        self.orders.create_event(order.id, None, OrderStatus.PENDING.value, customer_id, "order accepted")
        return order

    def list_for_customer(self, customer_id: str) -> list[Order]:
        return self.orders.list_for_customer(customer_id)

    # ------------------------------------------------------------------ cancellation / rejection

    def _release_buy_reservation(self, order: Order) -> None:
        if order.side == OrderSide.BUY:
            portfolio = self.portfolios.get_or_create(order.customer_id, D(settings.initial_cash))
            portfolio.reserved_cash = max(ZERO, D(portfolio.reserved_cash) - notional(order.quote_price, order.quantity))

    def cancel(self, customer_id: str, order_id: str) -> Order:
        with self._unit_of_work():
            order = self.orders.get(order_id)
            if order is None or order.customer_id != customer_id:
                raise DomainValidationException("order not found")
            validate_transition(order.status, OrderStatus.CANCELLED)
            self._release_buy_reservation(order)
            previous = order.status.value
            order.status = OrderStatus.CANCELLED
            order.cancelled_at = datetime.now(timezone.utc)
            self.orders.create_event(order.id, previous, OrderStatus.CANCELLED.value, customer_id, "customer cancellation")
        self.db.refresh(order)
        return order

    def reject(self, actor_id: str, order_id: str, reason: str) -> Order:
        with self._unit_of_work():
            order = self.orders.get(order_id)
            if order is None:
                raise DomainValidationException("order not found")
            validate_transition(order.status, OrderStatus.REJECTED)
            self._release_buy_reservation(order)
            previous = order.status.value
            order.status = OrderStatus.REJECTED
            order.rejected_at = datetime.now(timezone.utc)
            order.rejection_reason = reason.strip() or "Rejected by administrator"
            self.orders.create_event(order.id, previous, OrderStatus.REJECTED.value, actor_id, order.rejection_reason)
            self.audits.add(actor_id, "ORDER_REJECTED", "Order", order.id, request_correlation_id.get(), order.rejection_reason)
        self.db.refresh(order)
        return order

    # ------------------------------------------------------------------ execution

    def _limit_is_executable(self, order: Order, market_price: Decimal) -> bool:
        if order.order_type == OrderType.MARKET or order.limit_price is None:
            return True
        limit = D(order.limit_price)
        return market_price <= limit if order.side == OrderSide.BUY else market_price >= limit

    def execute(self, actor_id: str, order_id: str) -> Order:
        """Execute a PENDING order exactly once.

        Re-executing raises InvalidOrderStateException (state machine) and the unique `trades.order_id`
        constraint is a second line of defence, so a replayed request can never double-apply.
        """
        with self._unit_of_work():
            order = self.orders.get(order_id)
            if order is None:
                raise DomainValidationException("order not found")
            validate_transition(order.status, OrderStatus.EXECUTED)

            market_price = self._quote(order.stock_id)
            if not self._limit_is_executable(order, market_price):
                raise DomainValidationException("limit price condition is not met")

            execution_price = D(order.quote_price) if order.order_type == OrderType.MARKET else D(market_price)
            actual_notional = notional(execution_price, order.quantity)
            portfolio = self.portfolios.get_or_create(order.customer_id, D(settings.initial_cash))
            holding = self.portfolios.get_holding(portfolio.id, order.stock_id)

            # Phase 1 - validate and compute the complete outcome without touching any entity.
            if order.side == OrderSide.BUY:
                new_cash = D(portfolio.cash_balance) - actual_notional
                if new_cash < ZERO:
                    raise InsufficientFundsException("execution would exceed available cash")
                new_reserved = max(ZERO, D(portfolio.reserved_cash) - notional(order.quote_price, order.quantity))
                if holding is None:
                    new_quantity, new_average = D(order.quantity), execution_price
                else:
                    new_quantity, new_average = update_after_buy(
                        D(holding.quantity), D(holding.average_buy_price), D(order.quantity), execution_price
                    )
            else:
                if holding is None:
                    raise DomainValidationException("cannot sell a stock not held")
                other_pending = self.portfolios.pending_sell_quantity(order.customer_id, order.stock_id) - D(order.quantity)
                if D(order.quantity) > D(holding.quantity) - other_pending:
                    raise DomainValidationException("execution exceeds available holding")
                new_quantity = update_after_sell(D(holding.quantity), D(order.quantity))
                new_average = D(holding.average_buy_price)
                new_cash = D(portfolio.cash_balance) + actual_notional
                new_reserved = D(portfolio.reserved_cash)

            # Phase 2 - apply.
            self._apply_execution(order, portfolio, holding, new_cash, new_reserved, new_quantity, new_average)
            executed_at = datetime.now(timezone.utc)
            previous = order.status.value
            order.status = OrderStatus.EXECUTED
            order.executed_at = executed_at
            self.trades.add(
                Trade(
                    order_id=order.id,
                    customer_id=order.customer_id,
                    stock_id=order.stock_id,
                    side=order.side,
                    quantity=D(order.quantity),
                    execution_price=execution_price,
                    notional=actual_notional,
                    executed_at=executed_at,
                    actor_id=actor_id,
                    request_correlation_id=request_correlation_id.get(),
                )
            )
            self.orders.create_event(order.id, previous, OrderStatus.EXECUTED.value, actor_id, "stub execution")
            self.audits.add(
                actor_id, "ORDER_EXECUTED", "Order", order.id, request_correlation_id.get(), f"price={execution_price:.4f}"
            )
        self.db.refresh(order)
        return order

    def _apply_execution(
        self,
        order: Order,
        portfolio: Portfolio,
        holding: PortfolioHolding | None,
        new_cash: Decimal,
        new_reserved: Decimal,
        new_quantity: Decimal,
        new_average: Decimal,
    ) -> None:
        portfolio.cash_balance = new_cash
        portfolio.reserved_cash = new_reserved
        if holding is None:
            self.db.add(
                PortfolioHolding(
                    portfolio_id=portfolio.id, stock_id=order.stock_id, quantity=new_quantity, average_buy_price=new_average
                )
            )
        else:
            holding.quantity = new_quantity
            holding.average_buy_price = new_average
