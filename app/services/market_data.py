from __future__ import annotations

import random
from datetime import datetime
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.domain.money import D
from app.models.orm import MarketTick, Stock, StockStatus

MAX_TICK_BASIS_POINTS = 200  # +/-2% per tick
WALK_FLOOR = Decimal("0.70")
WALK_CEILING = Decimal("1.30")


class MarketDataService:
    """Synthetic market-data source backed by append-only SQLite tick records."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_latest_tick(self, stock_id: str) -> MarketTick | None:
        return self.db.scalar(
            select(MarketTick)
            .where(MarketTick.stock_id == stock_id)
            .order_by(desc(MarketTick.occurred_at))
            .limit(1)
        )

    def get_price(self, stock_id: str, fallback: Decimal = Decimal("100.0000")) -> Decimal:
        latest = self.get_latest_tick(stock_id)
        return D(latest.price if latest else fallback)

    def set_price(self, stock_id: str, price: Decimal) -> Decimal:
        value = D(price)
        self.db.add(MarketTick(stock_id=stock_id, price=value))
        self.db.flush()
        return value

    def get_reference_price(self, stock_id: str) -> Decimal | None:
        """The first price ever recorded for the stock (the anchor of the bounded random walk)."""
        first = self.db.scalar(
            select(MarketTick).where(MarketTick.stock_id == stock_id).order_by(MarketTick.occurred_at).limit(1)
        )
        return D(first.price) if first else None

    def get_previous_tick(self, stock_id: str) -> MarketTick | None:
        return self.db.scalar(
            select(MarketTick).where(MarketTick.stock_id == stock_id).order_by(desc(MarketTick.occurred_at)).offset(1).limit(1)
        )

    def tick_all(self) -> dict[str, Decimal]:
        stocks = list(self.db.scalars(select(Stock).where(Stock.status == StockStatus.ACTIVE)))
        updated: dict[str, Decimal] = {}
        for stock in stocks:
            current = self.get_price(stock.id)
            delta_basis_points = random.SystemRandom().randint(-MAX_TICK_BASIS_POINTS, MAX_TICK_BASIS_POINTS)
            multiplier = Decimal("1") + (Decimal(delta_basis_points) / Decimal("10000"))
            next_price = max(D("0.0100"), D(current * multiplier))
            # Bounded walk: the synthetic price never strays more than +/-30% from its first price, so a
            # long-running server cannot drift to absurd values.
            reference = self.get_reference_price(stock.id)
            if reference is not None:
                next_price = min(max(next_price, D(reference * WALK_FLOOR)), D(reference * WALK_CEILING))
            updated[stock.id] = self.set_price(stock.id, next_price)
        self.db.commit()
        return updated

    def quotes(self) -> list[tuple[Stock, Decimal, datetime | None, Decimal | None]]:
        """(stock, latest price, tick time, previous price) for every ACTIVE stock, ordered by symbol."""
        stocks = list(self.db.scalars(select(Stock).where(Stock.status == StockStatus.ACTIVE).order_by(Stock.symbol)))
        result: list[tuple[Stock, Decimal, datetime | None, Decimal | None]] = []
        for stock in stocks:
            tick = self.get_latest_tick(stock.id)
            previous = self.get_previous_tick(stock.id)
            result.append(
                (
                    stock,
                    D(tick.price) if tick else D(Decimal("100.0000")),
                    tick.occurred_at if tick else None,
                    D(previous.price) if previous else None,
                )
            )
        return result

    def snapshot(self, stock_ids: list[str]) -> dict[str, Decimal]:
        return {stock_id: self.get_price(stock_id) for stock_id in stock_ids}
