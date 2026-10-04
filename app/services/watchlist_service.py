from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import acquire_write_lock
from app.domain.exceptions import WatchlistUpdateException
from app.domain.watchlist_policy import validate_non_empty_symbols, validate_watchlist_count, validate_watchlist_creation
from app.models.orm import Stock, StockStatus, Watchlist, WatchlistSymbol
from app.repositories.repositories import StockRepository, WatchlistRepository


class WatchlistService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.watchlists = WatchlistRepository(db)
        self.stocks = StockRepository(db)

    def _validate_stocks(self, stock_ids: list[str]) -> list[Stock]:
        validate_non_empty_symbols(stock_ids)
        if len(set(stock_ids)) != len(stock_ids):
            raise WatchlistUpdateException("duplicate symbols are not allowed")
        stocks = [self.stocks.get(stock_id) for stock_id in stock_ids]
        if any(stock is None or stock.status != StockStatus.ACTIVE for stock in stocks):
            raise WatchlistUpdateException("all stocks must be active")
        return [stock for stock in stocks if stock is not None]

    def list_for_customer(self, customer_id: str) -> list[Watchlist]:
        return self.watchlists.list_for_customer(customer_id)

    def create(self, customer_id: str, name: str, stock_ids: list[str]) -> Watchlist:
        validate_watchlist_creation(name, stock_ids)
        try:
            # Count check and insert happen under one write lock, so the ten-watchlist cap cannot be raced.
            acquire_write_lock(self.db)
            validate_watchlist_count(self.watchlists.count_for_customer(customer_id))
            stocks = self._validate_stocks(stock_ids)
            watchlist = Watchlist(customer_id=customer_id, name=name.strip())
            watchlist.symbols = [WatchlistSymbol(stock_id=stock.id) for stock in stocks]
            self.db.add(watchlist)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WatchlistUpdateException("a watchlist with this name already exists") from exc
        except BaseException:
            self.db.rollback()
            raise
        self.db.refresh(watchlist)
        return watchlist

    def update(self, customer_id: str, watchlist_id: str, name: str | None, stock_ids: list[str] | None) -> Watchlist:
        watchlist = self.watchlists.get_owned(watchlist_id, customer_id)
        if watchlist is None:
            raise WatchlistUpdateException("watchlist not found")
        try:
            if name is not None:
                if not name.strip():
                    raise WatchlistUpdateException("watchlist name is required")
                watchlist.name = name.strip()
            if stock_ids is not None:
                wanted = [stock.id for stock in self._validate_stocks(stock_ids)]
                # Apply the difference only: re-inserting a retained symbol would hit uq_watchlist_stock,
                # because the unit of work flushes INSERTs before DELETEs.
                existing = {symbol.stock_id: symbol for symbol in watchlist.symbols}
                for stock_id, symbol in existing.items():
                    if stock_id not in wanted:
                        watchlist.symbols.remove(symbol)
                for stock_id in wanted:
                    if stock_id not in existing:
                        watchlist.symbols.append(WatchlistSymbol(stock_id=stock_id))
            if not watchlist.symbols:
                raise WatchlistUpdateException("watchlist must contain at least one symbol")
            self.db.commit()
            self.db.refresh(watchlist)
            return watchlist
        except Exception as exc:
            self.db.rollback()
            if isinstance(exc, WatchlistUpdateException):
                raise
            raise WatchlistUpdateException("watchlist update rolled back") from exc

    def delete(self, customer_id: str, watchlist_id: str) -> None:
        watchlist = self.watchlists.get_owned(watchlist_id, customer_id)
        if watchlist is None:
            raise WatchlistUpdateException("watchlist not found")
        self.db.delete(watchlist)
        self.db.commit()
