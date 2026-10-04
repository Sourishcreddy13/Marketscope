from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.models.schemas import DailyStatsResponse, PortfolioStatsResponse, SectorExposure
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioStatsResponse)
def portfolio(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return PortfolioService(db).statistics(current.id)


@router.get("/sector-exposure", response_model=list[SectorExposure])
def sector_exposure(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return PortfolioService(db).sector_exposure(current.id)


@router.get("/daily-stats", response_model=DailyStatsResponse)
def daily_stats(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return PortfolioService(db).daily_statistics(current.id)
