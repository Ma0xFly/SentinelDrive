from __future__ import annotations

import os
from collections.abc import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_engine_from_url(database_url: str | None = None) -> Engine:
    resolved_url = database_url or os.environ["DATABASE_URL"]
    return create_engine(resolved_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine) -> Callable[[], Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

