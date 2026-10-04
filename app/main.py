from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.market_data import router as market_data_router
from app.api.orders import router as orders_router
from app.api.portfolio import router as portfolio_router
from app.api.stocks import router as stocks_router
from app.api.watchlists import router as watchlists_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, request_correlation_id, sanitize_correlation_id
from app.core.ticker_lock import TickerLeaderLock
from app.services.market_data import MarketDataService

configure_logging()
logger = logging.getLogger("marketscope")


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop = asyncio.Event()
    # Single-writer guard: with several workers only the lock holder runs the synthetic ticker.
    leader_lock = TickerLeaderLock()
    is_ticker_leader = leader_lock.acquire()

    async def ticker() -> None:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=settings.market_tick_interval_seconds)
            except asyncio.TimeoutError:
                db = SessionLocal()
                try:
                    MarketDataService(db).tick_all()
                except Exception:
                    logger.exception("market_tick_failed")
                finally:
                    db.close()

    task = asyncio.create_task(ticker()) if is_ticker_leader else None
    try:
        yield
    finally:
        stop.set()
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        leader_lock.release()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    # The interactive docs load their UI from a CDN, so the strict API policy applies everywhere else.
    if not request.url.path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", _API_CSP)
    return response


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    correlation_id = sanitize_correlation_id(request.headers.get("X-Request-ID"))
    # Exception handlers run after this middleware has unwound, so the ID is also kept on the request.
    request.state.correlation_id = correlation_id
    token = request_correlation_id.set(correlation_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        logger.info(
            "request_completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            },
        )
        return response
    finally:
        request_correlation_id.reset(token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", None) or request_correlation_id.get()
    token = request_correlation_id.set(correlation_id)
    try:
        logger.exception(
            "unhandled_exception",
            extra={"method": request.method, "path": request.url.path, "status_code": 500},
        )
    finally:
        request_correlation_id.reset(token)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": correlation_id},
        headers={"X-Request-ID": correlation_id},
    )


@app.get("/health", tags=["system"])
def health():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": settings.app_name, "database": "sqlite"}
    finally:
        db.close()


app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(admin_router, prefix=settings.api_prefix)
app.include_router(stocks_router, prefix=settings.api_prefix)
app.include_router(watchlists_router, prefix=settings.api_prefix)
app.include_router(orders_router, prefix=settings.api_prefix)
app.include_router(portfolio_router, prefix=settings.api_prefix)
app.include_router(market_data_router, prefix=settings.api_prefix)
