from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, require_admin
from app.domain.exceptions import (
    DomainValidationException,
    InsufficientFundsException,
    InvalidInputException,
    InvalidOrderStateException,
)
from app.models.orm import User
from app.models.schemas import (
    MostTradedItem,
    OrderResponse,
    OrderStatsResponse,
    RoleUpdateRequest,
    StockCreateRequest,
    StockResponse,
    StockUpdateRequest,
    TradeResponse,
    UserResponse,
)
from app.repositories.repositories import AuditRepository, OrderRepository, StockRepository, TradeRepository, UserRepository
from app.services.market_data import MarketDataService
from app.services.order_service import OrderService
from app.services.stock_service import StockService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["admin"])


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role, created_at=user.created_at)


@router.get("/users", response_model=list[UserResponse])
def list_users(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    return [user_response(user) for user in UserRepository(db).list()]


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_role(user_id: str, payload: RoleUpdateRequest, admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    actor = db.get(User, admin.id)
    target = db.get(User, user_id)
    if actor is None or target is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        UserService(db).change_role(actor, target, payload.role)
    except DomainValidationException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return user_response(target)


@router.get("/stocks", response_model=list[StockResponse])
def list_stocks(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    return StockRepository(db).list_all()


@router.post("/stocks", response_model=StockResponse, status_code=201)
def create_stock(payload: StockCreateRequest, admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return StockService(db).create(admin.id, payload)
    except InvalidInputException as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DomainValidationException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/stocks/{stock_id}", response_model=StockResponse)
def update_stock(stock_id: str, payload: StockUpdateRequest, admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return StockService(db).update(admin.id, stock_id, payload)
    except InvalidInputException as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DomainValidationException as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc)) from exc


@router.delete("/stocks/{stock_id}", response_model=StockResponse)
def delete_stock(stock_id: str, admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return StockService(db).soft_delete(admin.id, stock_id)
    except DomainValidationException as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc




@router.get("/orders", response_model=list[OrderResponse])
def list_orders(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    return OrderRepository(db).list_all()

@router.post("/orders/{order_id}/execute", response_model=OrderResponse)
def execute_order(order_id: str, admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return OrderService(db).execute(admin.id, order_id)
    except (DomainValidationException, InvalidOrderStateException, InsufficientFundsException) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/orders/{order_id}/reject", response_model=OrderResponse)
def reject_order(order_id: str, reason: str = "Rejected by administrator", admin: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        return OrderService(db).reject(admin.id, order_id, reason)
    except (DomainValidationException, InvalidOrderStateException) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/market-data/tick")
def tick_market_data(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    prices = MarketDataService(db).tick_all()
    return {"updated_symbols": len(prices), "prices": {stock_id: f"{price:.4f}" for stock_id, price in prices.items()}}


@router.get("/orders/stats", response_model=OrderStatsResponse)
def order_stats(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    repository = OrderRepository(db)
    counts = repository.count_by_status()
    pending = counts.get("PENDING", 0)
    most_traded = repository.most_traded()
    return OrderStatsResponse(
        total_orders=sum(counts.values()),
        by_status=counts,
        settlement_queue={"pending_orders": pending},
        most_traded_stocks=[
            MostTradedItem(stock_id=stock_id, symbol=symbol, executed_order_count=count)
            for stock_id, symbol, count in most_traded
        ],
    )


@router.get("/stocks/most-traded", response_model=list[MostTradedItem])
def most_traded_stocks(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Specified endpoint (app_spec): symbols ranked by executed-order count, platform-wide."""
    return [
        MostTradedItem(stock_id=stock_id, symbol=symbol, executed_order_count=count)
        for stock_id, symbol, count in OrderRepository(db).most_traded()
    ]


@router.get("/trades", response_model=list[TradeResponse])
def recent_trades(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    return TradeRepository(db).list_recent()


@router.get("/audits")
def recent_audits(_: CurrentUser = Depends(require_admin), db: Session = Depends(get_db)):
    rows = AuditRepository(db).list_recent(100)
    return [
        {
            "id": row.id,
            "actor_id": row.actor_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "occurred_at": row.occurred_at,
            "request_correlation_id": row.request_correlation_id,
            "details": row.details,
        }
        for row in rows
    ]
