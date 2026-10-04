from __future__ import annotations

from decimal import Decimal

from sqlalchemy import inspect, select

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models.orm import Order, OrderSide, OrderType, Portfolio, Stock, StockStatus, User, UserRole
from app.services.market_data import MarketDataService
from app.services.order_service import OrderService
from app.services.watchlist_service import WatchlistService

SEED_STOCKS = [
    ("AAPL", "Apple Inc.", "Technology", "NASDAQ", "225.0000"),
    ("AMZN", "Amazon.com Inc.", "Consumer", "NASDAQ", "205.0000"),
    ("JPM", "JPMorgan Chase & Co.", "Financials", "NYSE", "230.0000"),
    ("MSFT", "Microsoft Corporation", "Technology", "NASDAQ", "430.0000"),
    ("NVDA", "NVIDIA Corporation", "Technology", "NASDAQ", "125.0000"),
    ("TSLA", "Tesla Inc.", "Automotive", "NASDAQ", "440.0000"),
    ("V", "Visa Inc.", "Financials", "NYSE", "330.0000"),
    ("XOM", "Exxon Mobil Corporation", "Energy", "NYSE", "115.0000"),
]


def seed() -> None:
    # The schema is owned by Alembic; seeding never creates tables behind the migrations' back.
    if not inspect(engine).has_table("trades"):
        raise SystemExit("Database schema is missing or outdated. Run `uv run alembic upgrade head` first.")
    db = SessionLocal()
    try:
        users = [
            ("admin@marketscope.local", "Admin@12345", UserRole.ADMIN),
            ("customer@marketscope.local", "Customer@12345", UserRole.CUSTOMER),
            ("analyst@marketscope.local", "Analyst@12345", UserRole.CUSTOMER),
        ]
        for email, password, role in users:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, password_hash=hash_password(password), role=role)
                db.add(user)
                db.flush()
                db.add(Portfolio(customer_id=user.id, cash_balance=Decimal(settings.initial_cash)))

        db.flush()
        market_data = MarketDataService(db)
        for symbol, name, sector, exchange, price in SEED_STOCKS:
            stock = db.scalar(select(Stock).where(Stock.symbol == symbol))
            if stock is None:
                stock = Stock(
                    symbol=symbol,
                    name=name,
                    sector=sector,
                    exchange=exchange,
                    status=StockStatus.ACTIVE,
                )
                db.add(stock)
                db.flush()
            if market_data.get_latest_tick(stock.id) is None:
                market_data.set_price(stock.id, Decimal(price))

        customer = db.scalar(select(User).where(User.email == "customer@marketscope.local"))
        admin = db.scalar(select(User).where(User.email == "admin@marketscope.local"))
        assert customer is not None and admin is not None

        watchlist_service = WatchlistService(db)
        customer_watchlists = watchlist_service.list_for_customer(customer.id)
        if not customer_watchlists:
            aapl = db.scalar(select(Stock).where(Stock.symbol == "AAPL"))
            msft = db.scalar(select(Stock).where(Stock.symbol == "MSFT"))
            assert aapl is not None and msft is not None
            watchlist_service.create(customer.id, "Core Technology", [aapl.id, msft.id])

        if db.scalar(select(Order).where(Order.customer_id == customer.id).limit(1)) is None:
            aapl = db.scalar(select(Stock).where(Stock.symbol == "AAPL"))
            msft = db.scalar(select(Stock).where(Stock.symbol == "MSFT"))
            nvda = db.scalar(select(Stock).where(Stock.symbol == "NVDA"))
            assert aapl is not None and msft is not None and nvda is not None
            order_service = OrderService(db)
            first = order_service.create(
                customer.id, aapl.id, OrderSide.BUY, OrderType.MARKET, Decimal("10.0000"), None, idempotency_key="seed-customer-aapl-buy"
            )
            order_service.execute(admin.id, first.id)
            second = order_service.create(
                customer.id, msft.id, OrderSide.BUY, OrderType.MARKET, Decimal("4.0000"), None, idempotency_key="seed-customer-msft-buy"
            )
            order_service.execute(admin.id, second.id)
            order_service.create(
                customer.id, nvda.id, OrderSide.BUY, OrderType.LIMIT, Decimal("20.0000"), Decimal("110.0000"),
                idempotency_key="seed-customer-nvda-limit",
            )

        db.commit()
    finally:
        db.close()
