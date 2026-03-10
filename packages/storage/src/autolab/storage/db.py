from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock

from autolab.core.settings import Settings
from autolab.storage.models import Base
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_INIT_DB_LOCK = Lock()
_INITIALIZED_DATABASE_URLS: set[str] = set()


def create_engine_from_settings(settings: Settings) -> Engine:
    connect_args: dict[str, object] = {}
    if settings.database.url.startswith("sqlite"):
        connect_args = {"check_same_thread": False, "timeout": 30}
    return create_engine(settings.database.url, future=True, connect_args=connect_args)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(settings: Settings) -> None:
    database_url = settings.database.url
    if database_url in _INITIALIZED_DATABASE_URLS:
        return
    with _INIT_DB_LOCK:
        if database_url in _INITIALIZED_DATABASE_URLS:
            return
        engine = create_engine_from_settings(settings)
        Base.metadata.create_all(bind=engine)
        _INITIALIZED_DATABASE_URLS.add(database_url)


@contextmanager
def session_scope(settings: Settings) -> Iterator[Session]:
    session_factory = create_session_factory(settings)
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
