from __future__ import annotations

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


class Base(DeclarativeBase):
    pass


connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}

if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

if settings.database_url in {"sqlite://", "sqlite:///:memory:"}:
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(settings.database_url, connect_args=connect_args, **engine_kwargs)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def acquire_write_lock(db: Session) -> None:
    """Open the write transaction before any state is read.

    SQLite allows a single writer. Issuing a no-op write as the first statement of a unit of work
    takes that lock up front, so the "read state -> validate -> mutate" sequence that follows cannot
    interleave with a competing writer (no lost updates, no double execution). Cached ORM state is
    expired so the validation sees the committed rows, not a stale identity-map copy.
    """
    db.execute(text("UPDATE portfolios SET reserved_cash = reserved_cash WHERE 1 = 0"))
    db.expire_all()
