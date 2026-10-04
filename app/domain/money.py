from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

SCALE = Decimal("0.0001")
SCALE_FACTOR = Decimal("10000")
ZERO = Decimal("0.0000")
HUNDRED = Decimal("100")


def D(value: str | Decimal | int) -> Decimal:
    if isinstance(value, float):  # precision-ok: guard that rejects floats
        raise TypeError("binary floating-point values are forbidden for financial arithmetic")
    return Decimal(str(value)).quantize(SCALE, rounding=ROUND_HALF_UP)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(SCALE, rounding=ROUND_HALF_UP)


def notional(price: Decimal, quantity: Decimal) -> Decimal:
    return quantize_money(price * quantity)


def weighted_average(
    old_quantity: Decimal,
    old_average_price: Decimal,
    new_quantity: Decimal,
    new_price: Decimal,
) -> Decimal:
    total_quantity = old_quantity + new_quantity
    if total_quantity == 0:
        return ZERO
    total_cost = old_quantity * old_average_price + new_quantity * new_price
    return quantize_money(total_cost / total_quantity)


def absolute_pnl(quantity: Decimal, average_buy_price: Decimal, current_price: Decimal) -> Decimal:
    return quantize_money(quantity * (current_price - average_buy_price))


def percent_pnl(absolute: Decimal, invested: Decimal) -> Decimal:
    if invested == 0:
        return ZERO
    return quantize_money((absolute / invested) * HUNDRED)
