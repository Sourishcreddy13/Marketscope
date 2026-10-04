from __future__ import annotations

from decimal import Decimal

from app.domain.enums import OrderSide, OrderStatus, OrderType
from app.domain.exceptions import InsufficientFundsException, InvalidOrderStateException

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {
        OrderStatus.EXECUTED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
    },
    OrderStatus.EXECUTED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
}


def validate_order_shape(
    side: OrderSide,
    order_type: OrderType,
    quantity: Decimal,
    limit_price: Decimal | None,
) -> None:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if order_type == OrderType.LIMIT and (limit_price is None or limit_price <= 0):
        raise ValueError("limit orders require a positive limit_price")
    if order_type == OrderType.MARKET and limit_price is not None:
        raise ValueError("market orders must not include limit_price")
    if side not in {OrderSide.BUY, OrderSide.SELL}:
        raise ValueError("invalid order side")


def validate_buy_funds(quote_price: Decimal, quantity: Decimal, available_cash: Decimal) -> None:
    if quote_price * quantity > available_cash:
        raise InsufficientFundsException("BUY order exceeds available cash")


def validate_transition(current: OrderStatus, target: OrderStatus) -> None:
    if target not in VALID_TRANSITIONS[current]:
        raise InvalidOrderStateException(f"Invalid transition {current.value} -> {target.value}")
