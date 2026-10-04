from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger
from sqlalchemy.types import TypeDecorator

from app.domain.money import SCALE_FACTOR, D


class FixedDecimal(TypeDecorator[Decimal]):
    """SQLite-safe fixed-point Decimal stored as an integer scaled by 10,000.

    The domain always sees Python Decimal. SQLite never stores binary floating point.
    """

    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        decimal_value = D(value)
        return int(decimal_value * SCALE_FACTOR)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return D(Decimal(value) / SCALE_FACTOR)
