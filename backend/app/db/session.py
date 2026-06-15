from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.settings import Settings, get_settings


def create_database_engine(settings: Settings | None = None):
    app_settings = settings or get_settings()
    return create_engine(
        app_settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        future=True,
    )


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
