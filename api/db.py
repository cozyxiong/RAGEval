from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.config import settings


class Base(DeclarativeBase):
    pass


def _sqlite_url(path: str) -> str:
    resolved = Path(path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{resolved.as_posix()}"


def make_engine(db_path: str | None = None):
    url = _sqlite_url(db_path or settings.eval_db_path)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _rec) -> None:  # type: ignore[no-untyped-def]
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def reset_engine(db_path: str) -> None:
    """Test helper: rebind the global sessionmaker to a new sqlite file."""
    global engine, SessionLocal
    engine.dispose()
    engine = make_engine(db_path)
    SessionLocal.configure(bind=engine)


def init_db() -> None:
    from api import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
