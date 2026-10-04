from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencies import CurrentUser, get_current_user
from app.core.rate_limit import limit_auth_attempts
from app.domain.exceptions import AccountSuspendedException, DomainValidationException
from app.models.orm import User
from app.models.schemas import AccountCloseRequest, LoginRequest, ProfileUpdateRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["auth"])


def to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, role=user.role, created_at=user.created_at)


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(limit_auth_attempts)]
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        service = UserService(db)
        user = service.register(str(payload.email), payload.password)
        _, token = service.login(str(payload.email), payload.password)
        return TokenResponse(access_token=token, user=to_user_response(user))
    except DomainValidationException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_auth_attempts)])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        user, token = UserService(db).login(str(payload.email), payload.password)
        return TokenResponse(access_token=token, user=to_user_response(user))
    except AccountSuspendedException as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DomainValidationException as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = db.get(User, current.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return to_user_response(user)


@router.patch("/me", response_model=UserResponse)
def update_me(
    payload: ProfileUpdateRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        return to_user_response(UserService(db).update_profile(user, str(payload.email) if payload.email else None, payload.current_password, payload.new_password))
    except DomainValidationException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/me", response_model=UserResponse)
def close_me(
    payload: AccountCloseRequest,
    current: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        return to_user_response(UserService(db).close_account(user, payload.current_password))
    except DomainValidationException as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
