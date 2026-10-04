from __future__ import annotations

from decimal import Decimal

from app.domain.money import ZERO, percent_pnl, quantize_money, weighted_average


def holding_invested_value(quantity: Decimal, average_buy_price: Decimal) -> Decimal:
    return quantize_money(quantity * average_buy_price)


def holding_current_value(quantity: Decimal, current_price: Decimal) -> Decimal:
    return quantize_money(quantity * current_price)


def holding_pnl(quantity: Decimal, average_buy_price: Decimal, current_price: Decimal) -> tuple[Decimal, Decimal]:
    invested = holding_invested_value(quantity, average_buy_price)
    current = holding_current_value(quantity, current_price)
    absolute = quantize_money(current - invested)
    percentage = percent_pnl(absolute, invested)
    return absolute, percentage


def update_after_buy(
    old_quantity: Decimal,
    old_average_buy_price: Decimal,
    buy_quantity: Decimal,
    execution_price: Decimal,
) -> tuple[Decimal, Decimal]:
    return old_quantity + buy_quantity, weighted_average(
        old_quantity,
        old_average_buy_price,
        buy_quantity,
        execution_price,
    )


def update_after_sell(
    old_quantity: Decimal,
    sell_quantity: Decimal,
) -> Decimal:
    remaining = old_quantity - sell_quantity
    if remaining < ZERO:
        raise ValueError("sell quantity exceeds holding")
    return quantize_money(remaining)
