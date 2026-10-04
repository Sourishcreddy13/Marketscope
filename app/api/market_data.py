from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.domain.enums import StockStatus
from app.domain.money import percent_pnl
from app.models.schemas import MarketQuoteResponse
from app.repositories.repositories import StockRepository
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/market-data", tags=["market-data"])


def _change(price: Decimal, previous: Decimal | None) -> Decimal | None:
    return percent_pnl(price - previous, previous) if previous else None


@router.get("", response_model=list[MarketQuoteResponse])
def quotes(_: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        MarketQuoteResponse(
            stock_id=stock.id,
            symbol=stock.symbol,
            price=price,
            occurred_at=occurred_at,
            previous_price=previous,
            change_percent=_change(price, previous),
        )
        for stock, price, occurred_at, previous in MarketDataService(db).quotes()
    ]


@router.get("/{stock_id}", response_model=MarketQuoteResponse)
def quote(stock_id: str, _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    stock = StockRepository(db).get(stock_id)
    if stock is None or stock.status != StockStatus.ACTIVE:
        raise HTTPException(status_code=404, detail="Stock not found")
    service = MarketDataService(db)
    tick = service.get_latest_tick(stock.id)
    previous_tick = service.get_previous_tick(stock.id)
    price = service.get_price(stock.id)
    previous = Decimal(previous_tick.price) if previous_tick else None
    return MarketQuoteResponse(
        stock_id=stock.id,
        symbol=stock.symbol,
        price=price,
        occurred_at=tick.occurred_at if tick else None,
        previous_price=previous,
        change_percent=_change(price, previous),
    )
