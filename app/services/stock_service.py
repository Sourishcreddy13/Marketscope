from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import request_correlation_id
from app.domain.exceptions import DomainValidationException, InvalidInputException
from app.models.orm import Stock, StockStatus
from app.models.schemas import StockCreateRequest, StockUpdateRequest
from app.repositories.repositories import AuditRepository, StockRepository


def _clean(field: str, value: str | None) -> str:
    """Trim and reject values that are empty after normalization."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise InvalidInputException(f"{field} must not be blank")
    return cleaned


class StockService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stocks = StockRepository(db)
        self.audits = AuditRepository(db)

    def create(self, actor_id: str, payload: StockCreateRequest) -> Stock:
        symbol = _clean("symbol", payload.symbol).upper()
        name = _clean("name", payload.name)
        sector = _clean("sector", payload.sector)
        exchange = _clean("exchange", payload.exchange)
        if self.stocks.get_by_symbol(symbol):
            raise DomainValidationException("symbol already exists")
        stock = Stock(symbol=symbol, name=name, sector=sector, exchange=exchange)
        self.db.add(stock)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainValidationException("symbol already exists") from exc
        self.audits.add(actor_id, "STOCK_CREATED", "Stock", stock.id, request_correlation_id.get())
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def update(self, actor_id: str, stock_id: str, payload: StockUpdateRequest) -> Stock:
        stock = self.stocks.get(stock_id)
        if stock is None:
            raise DomainValidationException("stock not found")
        if stock.status == StockStatus.DELETED:
            raise DomainValidationException("deleted stock cannot be updated")
        changes = {
            field: _clean(field, getattr(payload, field))
            for field in ("name", "sector", "exchange")
            if getattr(payload, field) is not None
        }
        if payload.symbol is not None:
            symbol = _clean("symbol", payload.symbol).upper()
            clash = self.stocks.get_by_symbol(symbol)
            if clash is not None and clash.id != stock.id:
                raise DomainValidationException("symbol already exists")
            changes["symbol"] = symbol
        for field, value in changes.items():
            setattr(stock, field, value)
        self.audits.add(actor_id, "STOCK_UPDATED", "Stock", stock.id, request_correlation_id.get())
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainValidationException("symbol already exists") from exc
        self.db.refresh(stock)
        return stock

    def soft_delete(self, actor_id: str, stock_id: str) -> Stock:
        stock = self.stocks.get(stock_id)
        if stock is None:
            raise DomainValidationException("stock not found")
        if stock.status == StockStatus.DELETED:
            return stock
        stock.status = StockStatus.DELETED
        self.audits.add(actor_id, "STOCK_SOFT_DELETED", "Stock", stock.id, request_correlation_id.get())
        self.db.commit()
        self.db.refresh(stock)
        return stock
