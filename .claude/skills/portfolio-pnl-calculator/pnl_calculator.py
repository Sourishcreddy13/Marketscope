#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

SCALE = Decimal("0.0001")


def to_decimal(value: object, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a decimal string.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{field} is not a valid decimal: {value}") from exc
    return result.quantize(SCALE, rounding=ROUND_HALF_UP)


def calculate(payload: dict) -> dict[str, str]:
    holdings = payload.get("holdings")
    if not isinstance(holdings, list):
        raise ValueError("holdings must be an array.")

    total_invested = Decimal("0")
    current_value = Decimal("0")

    for index, holding in enumerate(holdings):
        if not isinstance(holding, dict):
            raise ValueError(f"holdings[{index}] must be an object.")

        quantity = to_decimal(holding.get("quantity"), f"holdings[{index}].quantity")
        average_buy_price = to_decimal(
            holding.get("average_buy_price"),
            f"holdings[{index}].average_buy_price",
        )
        current_price = to_decimal(
            holding.get("current_price"),
            f"holdings[{index}].current_price",
        )

        if quantity < 0 or average_buy_price < 0 or current_price < 0:
            raise ValueError(f"holdings[{index}] contains a negative financial value.")

        total_invested += quantity * average_buy_price
        current_value += quantity * current_price

    total_invested = total_invested.quantize(SCALE, rounding=ROUND_HALF_UP)
    current_value = current_value.quantize(SCALE, rounding=ROUND_HALF_UP)
    absolute_pnl = (current_value - total_invested).quantize(
        SCALE, rounding=ROUND_HALF_UP
    )

    if total_invested == 0:
        percent_pnl = Decimal("0.0000")
    else:
        percent_pnl = (
            (absolute_pnl / total_invested) * Decimal("100")
        ).quantize(SCALE, rounding=ROUND_HALF_UP)

    return {
        "total_invested": f"{total_invested:.4f}",
        "current_value": f"{current_value:.4f}",
        "absolute_pnl": f"{absolute_pnl:.4f}",
        "percent_pnl": f"{percent_pnl:.4f}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Calculate canonical MarketScope portfolio P&L.")
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Root JSON value must be an object.")
        result = calculate(payload)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"INPUT_ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
