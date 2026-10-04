from decimal import Decimal

import pytest

from app.domain.exceptions import InsufficientFundsException, InvalidOrderStateException, WatchlistUpdateException
from app.domain.money import D, absolute_pnl, notional, percent_pnl, weighted_average
from app.domain.order_policy import validate_buy_funds, validate_transition
from app.domain.portfolio_policy import holding_pnl, update_after_buy, update_after_sell
from app.domain.watchlist_policy import validate_watchlist_count, validate_watchlist_creation
from app.models.orm import OrderStatus


def test_nfr01_decimal_constructor_preserves_scale():
    assert D("10.12555") == Decimal("10.1256")


def test_nfr01_notional_is_fixed_point():
    assert notional(D("10.3333"), D("3.0000")) == Decimal("30.9999")


def test_nfr01_weighted_average():
    assert weighted_average(D("10"), D("100"), D("10"), D("120")) == Decimal("110.0000")


def test_nfr01_pnl_positive():
    assert absolute_pnl(D("10"), D("100"), D("110")) == Decimal("100.0000")


def test_nfr01_pnl_percentage():
    assert percent_pnl(D("100"), D("1000")) == Decimal("10.0000")


def test_nfr01_zero_investment_percentage():
    assert percent_pnl(D("100"), Decimal("0")) == Decimal("0.0000")


def test_nfr01_holding_pnl():
    absolute, percent = holding_pnl(D("5"), D("100"), D("90"))
    assert absolute == Decimal("-50.0000")
    assert percent == Decimal("-10.0000")


def test_ac08_insufficient_funds_exception():
    with pytest.raises(InsufficientFundsException):
        validate_buy_funds(D("101"), D("10"), D("1000"))


def test_ac08_equal_available_cash_passes():
    validate_buy_funds(D("100"), D("10"), D("1000"))


def test_ac07_valid_pending_to_executed():
    validate_transition(OrderStatus.PENDING, OrderStatus.EXECUTED)


@pytest.mark.parametrize("target", [OrderStatus.CANCELLED, OrderStatus.REJECTED])
def test_ac07_valid_pending_terminal_transitions(target):
    validate_transition(OrderStatus.PENDING, target)


def test_ac07_executed_cannot_be_cancelled():
    with pytest.raises(InvalidOrderStateException):
        validate_transition(OrderStatus.EXECUTED, OrderStatus.CANCELLED)


def test_ac07_cancelled_cannot_execute():
    with pytest.raises(InvalidOrderStateException):
        validate_transition(OrderStatus.CANCELLED, OrderStatus.EXECUTED)


def test_ac07_rejected_cannot_execute():
    with pytest.raises(InvalidOrderStateException):
        validate_transition(OrderStatus.REJECTED, OrderStatus.EXECUTED)


def test_ac04_empty_watchlist_rejected():
    with pytest.raises(WatchlistUpdateException):
        validate_watchlist_creation("Empty", [])


def test_ac04_watchlist_name_required():
    with pytest.raises(WatchlistUpdateException):
        validate_watchlist_creation(" ", ["stock"])


def test_ac04_duplicate_symbols_rejected():
    with pytest.raises(WatchlistUpdateException):
        validate_watchlist_creation("Tech", ["a", "a"])


def test_ac04_tenth_watchlist_is_allowed():
    validate_watchlist_count(9)


def test_ac04_eleventh_watchlist_rejected():
    with pytest.raises(WatchlistUpdateException):
        validate_watchlist_count(10)


def test_portfolio_buy_updates_average():
    quantity, average = update_after_buy(D("10"), D("100"), D("5"), D("130"))
    assert quantity == Decimal("15.0000")
    assert average == Decimal("110.0000")


def test_portfolio_sell_updates_quantity():
    assert update_after_sell(D("10"), D("3")) == Decimal("7.0000")


def test_portfolio_sell_over_position_rejected():
    with pytest.raises(ValueError):
        update_after_sell(D("2"), D("3"))


def test_nfr01_float_values_are_rejected_at_money_boundary():
    with pytest.raises(TypeError, match="floating-point"):
        D(10.25)
