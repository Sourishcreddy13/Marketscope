from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.domain.exceptions import (
    DomainValidationException,
    IdempotencyConflictException,
    InsufficientFundsException,
)
from app.models.schemas import OrderCreateRequest, OrderResponse
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])

_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9_.:-]{8,64}$")


@router.get("", response_model=list[OrderResponse])
def list_orders(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return OrderService(db).list_for_customer(current.id)


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(
    payload: OrderCreateRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Place an order. The `Idempotency-Key` header (8-64 chars) is mandatory.

    Replaying the same key with the same body returns the original order (200, `Idempotent-Replay: true`)
    without creating a second order; the same key with a different body is rejected with 422.
    """
    if idempotency_key is None or not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key header is required (8-64 characters: letters, digits, '_', '.', ':', '-')",
        )
    try:
        placement = OrderService(db).place(
            current.id,
            payload.stock_id,
            payload.side,
            payload.order_type,
            payload.quantity,
            payload.limit_price,
            idempotency_key=idempotency_key,
        )
    except IdempotencyConflictException as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InsufficientFundsException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DomainValidationException as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if placement.replayed:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return placement.order


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return OrderService(db).cancel(current.id, order_id)
    except DomainValidationException as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 409, detail=str(exc)) from exc
