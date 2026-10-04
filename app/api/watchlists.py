from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.domain.exceptions import WatchlistUpdateException
from app.models.schemas import WatchlistCreateRequest, WatchlistResponse, WatchlistUpdateRequest
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


def to_response(watchlist) -> WatchlistResponse:
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        stock_ids=[symbol.stock_id for symbol in watchlist.symbols],
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


@router.get("", response_model=list[WatchlistResponse])
def list_watchlists(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return [to_response(w) for w in WatchlistService(db).list_for_customer(current.id)]


@router.post("", response_model=WatchlistResponse, status_code=201)
def create_watchlist(payload: WatchlistCreateRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return to_response(WatchlistService(db).create(current.id, payload.name, payload.stock_ids))
    except WatchlistUpdateException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(watchlist_id: str, payload: WatchlistUpdateRequest, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        return to_response(WatchlistService(db).update(current.id, watchlist_id, payload.name, payload.stock_ids))
    except WatchlistUpdateException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(watchlist_id: str, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        WatchlistService(db).delete(current.id, watchlist_id)
    except WatchlistUpdateException as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
