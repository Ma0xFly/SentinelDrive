from collections.abc import Callable
from dataclasses import dataclass
from math import ceil

import psycopg
import redis

from app.core.settings import Settings


@dataclass(frozen=True)
class DependencyProbeResult:
    name: str
    ready: bool
    detail: str


Probe = Callable[[Settings], DependencyProbeResult]


def _psycopg_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return database_url


def check_postgres(settings: Settings) -> DependencyProbeResult:
    try:
        database_url = _psycopg_url(settings.database_url.get_secret_value())
        timeout = max(1, ceil(settings.readiness_timeout_seconds))
        with psycopg.connect(database_url, connect_timeout=timeout) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception:
        return DependencyProbeResult(name="postgres", ready=False, detail="unreachable")
    return DependencyProbeResult(name="postgres", ready=True, detail="ok")


def check_redis(settings: Settings) -> DependencyProbeResult:
    try:
        client = redis.Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=settings.readiness_timeout_seconds,
            socket_timeout=settings.readiness_timeout_seconds,
        )
        client.ping()
    except Exception:
        return DependencyProbeResult(name="redis", ready=False, detail="unreachable")
    return DependencyProbeResult(name="redis", ready=True, detail="ok")
