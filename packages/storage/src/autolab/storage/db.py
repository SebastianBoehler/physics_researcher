from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from autolab.core.settings import Settings
from autolab.storage.models import Base
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_from_settings(settings: Settings) -> Engine:
    return create_engine(settings.database.url, future=True)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine_from_settings(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(settings: Settings) -> None:
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(bind=engine)


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
