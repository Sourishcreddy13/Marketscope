from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.orm import User, UserRole

bearer_scheme = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    role: UserRole


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentUser:
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = str(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user = db.get(User, user_id)
    if user is None or user.role == UserRole.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable")
    return CurrentUser(id=user.id, email=user.email, role=user.role)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ADMIN role required")
    return user
