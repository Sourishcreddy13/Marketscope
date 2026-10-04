from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

import email_validator
from email_validator import EmailNotValidError, validate_email
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.models.orm import OrderSide, OrderStatus, OrderType, StockStatus, UserRole

if settings.environment != "production":
    # The synthetic demo/test accounts use the reserved `.local` / `.test` domains (Synthetic-Data
    # Rule). email-validator documents editing SPECIAL_USE_DOMAIN_NAMES for exactly this case.
    # Production keeps the library defaults, which reject them.
    for _reserved in ("local", "test"):
        if _reserved in email_validator.SPECIAL_USE_DOMAIN_NAMES:
            email_validator.SPECIAL_USE_DOMAIN_NAMES.remove(_reserved)


def _normalize_email(value: str) -> str:
    """Validate with email-validator (the engine behind pydantic's EmailStr) and normalize once."""
    try:
        result = validate_email(value.strip(), check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return result.normalized.lower()


NormalizedEmail = Annotated[str, Field(min_length=5, max_length=255), AfterValidator(_normalize_email)]


def _reject_blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class RegisterRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RegisterRequest):
    pass


class ProfileUpdateRequest(BaseModel):
    email: NormalizedEmail | None = None
    current_password: str | None = Field(default=None, min_length=8, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    role: UserRole
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RoleUpdateRequest(BaseModel):
    role: UserRole


class StockCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    sector: str = Field(min_length=1, max_length=128)
    exchange: str = Field(min_length=1, max_length=32)

    @field_validator("symbol", "name", "sector", "exchange")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _reject_blank(value) or ""


class StockUpdateRequest(BaseModel):
    symbol: str | None = Field(default=None, min_length=1, max_length=16)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    sector: str | None = Field(default=None, min_length=1, max_length=128)
    exchange: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("symbol", "name", "sector", "exchange")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        return _reject_blank(value)


class StockResponse(StockCreateRequest):
    id: str
    status: StockStatus
    created_at: datetime
    updated_at: datetime


class MarketQuoteResponse(BaseModel):
    stock_id: str
    symbol: str
    price: Decimal
    occurred_at: datetime | None
    previous_price: Decimal | None = None
    change_percent: Decimal | None = None  # versus the previous tick, four decimals, server-computed


class WatchlistCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    stock_ids: list[str] = Field(min_length=1)


class WatchlistUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    stock_ids: list[str] | None = Field(default=None, min_length=1)


class WatchlistResponse(BaseModel):
    id: str
    name: str
    stock_ids: list[str]
    created_at: datetime
    updated_at: datetime


class OrderCreateRequest(BaseModel):
    stock_id: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    stock_id: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    limit_price: Decimal | None
    quote_price: Decimal
    status: OrderStatus
    created_at: datetime
    executed_at: datetime | None
    cancelled_at: datetime | None
    rejected_at: datetime | None
    rejection_reason: str | None


class HoldingResponse(BaseModel):
    stock_id: str
    symbol: str
    quantity: Decimal
    average_buy_price: Decimal
    current_price: Decimal
    current_value: Decimal
    invested_value: Decimal
    absolute_pnl: Decimal
    percent_pnl: Decimal


class PortfolioStatsResponse(BaseModel):
    total_invested: Decimal
    current_value: Decimal
    absolute_pnl: Decimal
    percent_pnl: Decimal
    available_cash: Decimal
    holdings: list[HoldingResponse]


class SectorExposure(BaseModel):
    sector: str
    value: Decimal
    percent: Decimal


class DailyStatItem(BaseModel):
    stock_id: str
    symbol: str
    percent_pnl: Decimal
    absolute_pnl: Decimal


class DailyStatsResponse(BaseModel):
    top_5_gainers: list[DailyStatItem]
    top_5_losers: list[DailyStatItem]


class MostTradedItem(BaseModel):
    stock_id: str
    symbol: str
    executed_order_count: int


class OrderStatsResponse(BaseModel):
    total_orders: int
    by_status: dict[str, int]
    settlement_queue: dict[str, int]
    most_traded_stocks: list[MostTradedItem]


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    order_id: str
    customer_id: str
    stock_id: str
    side: OrderSide
    quantity: Decimal
    execution_price: Decimal
    notional: Decimal
    executed_at: datetime


class AccountCloseRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
