from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import request_correlation_id
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.exceptions import AccountSuspendedException, DomainValidationException
from app.models.orm import AuditEvent, Portfolio, User, UserRole
from app.repositories.repositories import AuditRepository, OrderRepository, UserRepository


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.audits = AuditRepository(db)

    def register(self, email: str, password: str) -> User:
        normalized = email.strip().lower()
        if self.users.get_by_email(normalized):
            raise DomainValidationException("email already registered")
        user = User(email=normalized, password_hash=hash_password(password), role=UserRole.CUSTOMER)
        try:
            self.users.create(user)
            self.db.add(Portfolio(customer_id=user.id, cash_balance=settings.initial_cash))
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainValidationException("email already registered") from exc
        return user

    def login(self, email: str, password: str) -> tuple[User, str]:
        user = self.users.get_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise DomainValidationException("invalid credentials")
        # Only revealed after the password is verified, so it cannot be used to probe which emails exist.
        if user.role == UserRole.SUSPENDED:
            raise AccountSuspendedException("this account is suspended; contact an administrator")
        return user, create_access_token(user.id, user.role.value)

    def change_role(self, actor: User, target: User, role: UserRole) -> AuditEvent:
        if actor.id == target.id and role != UserRole.ADMIN:
            raise DomainValidationException("an administrator cannot remove their own ADMIN access")
        previous_role = target.role
        target.role = role
        target.last_role_change_at = datetime.now(timezone.utc)
        target.last_role_change_by = actor.id
        event = self.audits.add(
            actor_id=actor.id,
            action="USER_ROLE_CHANGED",
            target_type="User",
            target_id=target.id,
            correlation_id=request_correlation_id.get(),
            details=f"{previous_role.value}->{role.value}",
        )
        self.db.commit()
        return event

    def update_profile(self, user: User, email: str | None, current_password: str | None, new_password: str | None) -> User:
        if email is not None:
            normalized = email.strip().lower()
            existing = self.users.get_by_email(normalized)
            if existing is not None and existing.id != user.id:
                raise DomainValidationException("email already registered")
            if not normalized:
                raise DomainValidationException("email is required")
            user.email = normalized
        if new_password is not None:
            if current_password is None or not verify_password(current_password, user.password_hash):
                raise DomainValidationException("current password is invalid")
            user.password_hash = hash_password(new_password)
        self.db.commit()
        self.db.refresh(user)
        return user

    def close_account(self, user: User, current_password: str) -> User:
        """Self-service account closure: the 'delete' of the user CRUD baseline.

        Accounts are never hard-deleted (orders, trades and audit rows reference them and are
        append-only). Closure moves the account to SUSPENDED, which blocks login and API access;
        an ADMIN can reactivate it through the role-management console (AC-02).
        """
        if user.role == UserRole.ADMIN:
            raise DomainValidationException("an administrator account cannot be closed by self-service")
        if not verify_password(current_password, user.password_hash):
            raise DomainValidationException("current password is invalid")
        if OrderRepository(self.db).count_pending_for_customer(user.id) > 0:
            raise DomainValidationException("cancel pending orders before closing the account")
        previous_role = user.role
        user.role = UserRole.SUSPENDED
        user.last_role_change_at = datetime.now(timezone.utc)
        user.last_role_change_by = user.id
        self.audits.add(
            actor_id=user.id,
            action="USER_ACCOUNT_CLOSED",
            target_type="User",
            target_id=user.id,
            correlation_id=request_correlation_id.get(),
            details=f"{previous_role.value}->{UserRole.SUSPENDED.value}",
        )
        self.db.commit()
        self.db.refresh(user)
        return user
