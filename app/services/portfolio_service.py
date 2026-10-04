from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.money import ZERO, D
from app.domain.portfolio_policy import holding_current_value, holding_invested_value, holding_pnl
from app.models.orm import Portfolio, Stock
from app.models.schemas import DailyStatItem, DailyStatsResponse, HoldingResponse, PortfolioStatsResponse, SectorExposure
from app.repositories.repositories import PortfolioRepository
from app.services.market_data import MarketDataService

logger = logging.getLogger("marketscope")


class PortfolioService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.market_data = MarketDataService(db)
        self.portfolios = PortfolioRepository(db)

    def get_portfolio(self, customer_id: str) -> Portfolio:
        portfolio = self.portfolios.get(customer_id)
        if portfolio is None:
            # Portfolios are created at registration/seeding. A read must never write: report the
            # inconsistency and answer with a transient, unsaved opening balance.
            logger.warning("portfolio_missing", extra={"customer_id": customer_id})
            return Portfolio(customer_id=customer_id, cash_balance=D(settings.initial_cash), reserved_cash=ZERO)
        return portfolio

    def statistics(self, customer_id: str) -> PortfolioStatsResponse:
        portfolio = self.get_portfolio(customer_id)
        total_invested = ZERO
        current_value = ZERO
        holdings: list[HoldingResponse] = []
        for holding in portfolio.holdings:
            stock = self.db.get(Stock, holding.stock_id)
            if stock is None or D(holding.quantity) <= 0:
                continue
            current_price = self.market_data.get_price(holding.stock_id)
            invested = holding_invested_value(D(holding.quantity), D(holding.average_buy_price))
            current = holding_current_value(D(holding.quantity), current_price)
            absolute, percentage = holding_pnl(D(holding.quantity), D(holding.average_buy_price), current_price)
            total_invested += invested
            current_value += current
            holdings.append(
                HoldingResponse(
                    stock_id=holding.stock_id,
                    symbol=stock.symbol,
                    quantity=D(holding.quantity),
                    average_buy_price=D(holding.average_buy_price),
                    current_price=current_price,
                    current_value=current,
                    invested_value=invested,
                    absolute_pnl=absolute,
                    percent_pnl=percentage,
                )
            )
        absolute_pnl = D(current_value - total_invested)
        percent = D((absolute_pnl / total_invested) * Decimal("100")) if total_invested else ZERO
        holdings.sort(key=lambda item: item.symbol)
        return PortfolioStatsResponse(
            total_invested=D(total_invested),
            current_value=D(current_value),
            absolute_pnl=D(absolute_pnl),
            percent_pnl=D(percent),
            available_cash=D(portfolio.cash_balance) - D(portfolio.reserved_cash),
            holdings=holdings,
        )

    def daily_statistics(self, customer_id: str) -> DailyStatsResponse:
        stats = self.statistics(customer_id)
        gainers = sorted((h for h in stats.holdings if h.percent_pnl > 0), key=lambda h: (-h.percent_pnl, h.symbol))[:5]
        losers = sorted((h for h in stats.holdings if h.percent_pnl < 0), key=lambda h: (h.percent_pnl, h.symbol))[:5]
        return DailyStatsResponse(
            top_5_gainers=[DailyStatItem(stock_id=h.stock_id, symbol=h.symbol, percent_pnl=h.percent_pnl, absolute_pnl=h.absolute_pnl) for h in gainers],
            top_5_losers=[DailyStatItem(stock_id=h.stock_id, symbol=h.symbol, percent_pnl=h.percent_pnl, absolute_pnl=h.absolute_pnl) for h in losers],
        )

    def sector_exposure(self, customer_id: str) -> list[SectorExposure]:
        stats = self.statistics(customer_id)
        totals: dict[str, Decimal] = {}
        for holding in stats.holdings:
            stock = self.db.get(Stock, holding.stock_id)
            if stock is not None:
                totals[stock.sector] = D(totals.get(stock.sector, ZERO) + holding.current_value)
        total = stats.current_value
        return [
            SectorExposure(sector=sector, value=D(value), percent=D((value / total) * Decimal("100")) if total else ZERO)
            for sector, value in sorted(totals.items())
        ]
