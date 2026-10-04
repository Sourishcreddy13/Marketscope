"""Domain vocabulary shared by policies, services and persistence (no framework imports)."""
from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"
    SUSPENDED = "SUSPENDED"


class StockStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
