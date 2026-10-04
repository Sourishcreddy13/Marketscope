from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

MIN_JWT_SECRET_LENGTH = 32
# Values that ship in documentation/examples and therefore must never be accepted at runtime.
_PLACEHOLDER_SECRET_PREFIXES = ("change-this", "change-me", "marketscope-local", "secret", "password")
# A secret that is valid only when ENVIRONMENT=test. It never applies to any other environment.
_TEST_ONLY_JWT_SECRET = "marketscope-test-only-secret-never-use-outside-tests-0000"


class ConfigurationError(RuntimeError):
    """Raised at startup when the runtime configuration is unsafe."""


def resolve_jwt_secret(environment: str, raw: str | None) -> str:
    """Return the JWT signing secret or fail fast.

    There is deliberately no source-code fallback: a secret known from the repository
    would let anyone forge tokens. Only ENVIRONMENT=test may use the built-in test secret.
    """
    secret = (raw or "").strip()
    if not secret:
        if environment == "test":
            return _TEST_ONLY_JWT_SECRET
        raise ConfigurationError(
            "JWT_SECRET is not set. Generate one with "
            "`python -c \"import secrets; print(secrets.token_urlsafe(48))\"` and export it "
            "or put it in .env (see .env.example)."
        )
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        raise ConfigurationError(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters long.")
    if secret.lower().startswith(_PLACEHOLDER_SECRET_PREFIXES):
        raise ConfigurationError("JWT_SECRET is a documented placeholder value; generate a unique secret.")
    return secret


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in os.getenv(name, default).split(",") if value.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "MarketScope")
    environment: str = os.getenv("ENVIRONMENT", "development")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'data' / 'marketscope.db'}")
    jwt_secret: str = field(
        default_factory=lambda: resolve_jwt_secret(os.getenv("ENVIRONMENT", "development"), os.getenv("JWT_SECRET"))
    )
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = int(os.getenv("JWT_EXPIRY_MINUTES", "120"))
    api_prefix: str = "/api/v1"
    market_tick_interval_seconds: int = int(os.getenv("MARKET_TICK_INTERVAL_SECONDS", "15"))
    initial_cash: str = os.getenv("INITIAL_CASH", "100000.0000")
    auth_rate_limit_attempts: int = int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "5"))
    auth_rate_limit_window_seconds: int = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60"))
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: _csv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    )


settings = Settings()
