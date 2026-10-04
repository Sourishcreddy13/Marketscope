from __future__ import annotations

from app.domain.exceptions import WatchlistUpdateException

MAX_WATCHLISTS = 10


def validate_watchlist_creation(name: str, stock_ids: list[str]) -> None:
    if not name.strip():
        raise WatchlistUpdateException("watchlist name is required")
    if not stock_ids:
        raise WatchlistUpdateException("watchlist must contain at least one symbol")
    if len(set(stock_ids)) != len(stock_ids):
        raise WatchlistUpdateException("duplicate stock in watchlist")


def validate_watchlist_count(current_count: int) -> None:
    if current_count >= MAX_WATCHLISTS:
        raise WatchlistUpdateException("customer may hold at most ten watchlists")


def validate_non_empty_symbols(stock_ids: list[str]) -> None:
    if not stock_ids:
        raise WatchlistUpdateException("watchlist must contain at least one symbol")
