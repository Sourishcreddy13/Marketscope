from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.models.schemas import StockResponse
from app.repositories.repositories import StockRepository

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=list[StockResponse])
def search_stocks(q: str | None = None, _: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return StockRepository(db).search(q)
