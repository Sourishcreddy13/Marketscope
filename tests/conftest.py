from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-with-at-least-32-bytes-long"
os.environ["MARKET_TICK_INTERVAL_SECONDS"] = "3600"
os.environ["AUTH_RATE_LIMIT_ATTEMPTS"] = "1000"

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.db import Base, SessionLocal, engine
from app.core.rate_limit import auth_rate_limiter
from app.core.security import hash_password
from app.main import app
from app.models.orm import APPEND_ONLY_TRIGGERS, Portfolio, Stock, StockStatus, User, UserRole
from app.services.market_data import MarketDataService

ROOT = Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_schema():
    """Provision the integration schema by applying the real Alembic migrations (NFR-05).

    `Base.metadata.create_all()` is deliberately not used here so migration drift fails the suite.
    """
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield
    Base.metadata.drop_all(bind=engine)


def _clear_all_rows() -> None:
    # Core-level DELETE: this is test teardown, not an application code path. The append-only triggers
    # (which exist precisely to block this) are lifted for the teardown and reinstated straight after.
    with engine.begin() as connection:
        for name, _ddl in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(f"DROP TRIGGER IF EXISTS trg_{name}")
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
        for _name, ddl in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(ddl)


def new_idempotency_key() -> str:
    return f"test-{uuid.uuid4().hex}"


@pytest.fixture(autouse=True)
def reset_database(migrated_schema):
    _clear_all_rows()
    auth_rate_limiter.reset()
    db = SessionLocal()
    admin = User(email="admin@test.local", password_hash=hash_password("Admin@12345"), role=UserRole.ADMIN)
    customer = User(email="customer@test.local", password_hash=hash_password("Customer@12345"), role=UserRole.CUSTOMER)
    other = User(email="other@test.local", password_hash=hash_password("Other@12345"), role=UserRole.CUSTOMER)
    db.add_all([admin, customer, other])
    db.flush()
    db.add_all([
        Portfolio(customer_id=admin.id, cash_balance=Decimal("100000.0000")),
        Portfolio(customer_id=customer.id, cash_balance=Decimal("100000.0000")),
        Portfolio(customer_id=other.id, cash_balance=Decimal("100000.0000")),
    ])
    stocks = [
        Stock(symbol="TEST", name="Test Corp", sector="Technology", exchange="TESTX", status=StockStatus.ACTIVE),
        Stock(symbol="BANK", name="Bank Corp", sector="Financials", exchange="TESTX", status=StockStatus.ACTIVE),
        Stock(symbol="ENERGY", name="Energy Corp", sector="Energy", exchange="TESTX", status=StockStatus.ACTIVE),
    ]
    db.add_all(stocks)
    db.commit()
    market = MarketDataService(db)
    for stock, price in zip(stocks, ["100.0000", "200.0000", "50.0000"], strict=True):
        market.set_price(stock.id, Decimal(price))
    db.commit()
    db.close()
    yield
    _clear_all_rows()


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture()
def customer_token(client: TestClient) -> str:
    return login(client, "customer@test.local", "Customer@12345")


@pytest.fixture()
def other_customer_token(client: TestClient) -> str:
    return login(client, "other@test.local", "Other@12345")


@pytest.fixture()
def admin_token(client: TestClient) -> str:
    return login(client, "admin@test.local", "Admin@12345")


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def stock_by_symbol(db_session, symbol: str) -> Stock:
    stock = db_session.scalar(select(Stock).where(Stock.symbol == symbol))
    assert stock is not None
    return stock


@pytest.fixture()
def app_client_no_raise() -> TestClient:
    """Client that returns the 500 response instead of re-raising server exceptions."""
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
