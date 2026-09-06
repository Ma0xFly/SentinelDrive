from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_session
from app.api.schemas.stats import (
    StatsAlertsResponse,
    StatsOverviewResponse,
    StatsSourceTopResponse,
    StatsSourcesResponse,
    StatsTotalsResponse,
    StatsTrendPointResponse,
)
from app.db.types import (
    AlertStatus,
    IntelligenceType,
    ProcessingStatus,
    RiskLevel,
    Severity,
    SourceStatus,
)
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import Alert, User
from app.models.source import Source

router = APIRouter(prefix="/stats", tags=["stats"])

TREND_DAYS = 30
RECENT_WINDOW_24_HOURS = timedelta(hours=24)
RECENT_WINDOW_7_DAYS = timedelta(days=7)
SOURCE_TOP_LIMIT = 10

_INTELLIGENCE_TYPE_KEYS = [item.value for item in IntelligenceType]
_SEVERITY_KEYS = [item.value for item in Severity]
_RISK_LEVEL_KEYS = [item.value for item in RiskLevel]
_PROCESSING_STATUS_KEYS = [item.value for item in ProcessingStatus]
_ALERT_STATUS_KEYS = [item.value for item in AlertStatus]


@router.get("/overview", response_model=StatsOverviewResponse)
async def get_stats_overview(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> StatsOverviewResponse:
    del current_user
    now = datetime.now(timezone.utc)
    days = _trend_days(now)
    window_start = datetime.combine(days[0], time.min, tzinfo=timezone.utc)
    if isinstance(session, Session):
        return _sql_overview(session, now, days, window_start)
    return _fallback_overview(session, now, days, window_start)


def _sql_overview(
    session: Session,
    now: datetime,
    days: list[date],
    window_start: datetime,
) -> StatsOverviewResponse:
    return StatsOverviewResponse(
        totals=StatsTotalsResponse(
            total_intelligence=_sql_intelligence_count(session),
            new_last_24_hours=_sql_intelligence_count(
                session,
                ThreatIntelligence.first_seen_at >= now - RECENT_WINDOW_24_HOURS,
            ),
            new_last_7_days=_sql_intelligence_count(
                session,
                ThreatIntelligence.first_seen_at >= now - RECENT_WINDOW_7_DAYS,
            ),
        ),
        by_intelligence_type=_sql_distribution(session, ThreatIntelligence.intelligence_type, _INTELLIGENCE_TYPE_KEYS),
        by_severity=_sql_distribution(session, ThreatIntelligence.severity, _SEVERITY_KEYS),
        by_risk_level=_sql_distribution(session, ThreatIntelligence.risk_level, _RISK_LEVEL_KEYS),
        by_processing_status=_sql_distribution(
            session,
            ThreatIntelligence.processing_status,
            _PROCESSING_STATUS_KEYS,
        ),
        trend=_sql_daily_trend(session, ThreatIntelligence.first_seen_at, days, window_start),
        alerts=_sql_alerts(session, days, window_start),
        sources=_sql_sources(session),
    )


def _fallback_overview(
    session: Any,
    now: datetime,
    days: list[date],
    window_start: datetime,
) -> StatsOverviewResponse:
    entries = list(session.scalars(select(ThreatIntelligence)).all())
    alerts = list(session.scalars(select(Alert)).all())
    sources = list(session.scalars(select(Source)).all())
    source_links = list(session.scalars(select(ThreatIntelligenceSource)).all())
    return StatsOverviewResponse(
        totals=StatsTotalsResponse(
            total_intelligence=len(entries),
            new_last_24_hours=sum(
                1 for entry in entries if entry.first_seen_at >= now - RECENT_WINDOW_24_HOURS
            ),
            new_last_7_days=sum(
                1 for entry in entries if entry.first_seen_at >= now - RECENT_WINDOW_7_DAYS
            ),
        ),
        by_intelligence_type=_fallback_distribution(entries, "intelligence_type", _INTELLIGENCE_TYPE_KEYS),
        by_severity=_fallback_distribution(entries, "severity", _SEVERITY_KEYS),
        by_risk_level=_fallback_distribution(entries, "risk_level", _RISK_LEVEL_KEYS),
        by_processing_status=_fallback_distribution(entries, "processing_status", _PROCESSING_STATUS_KEYS),
        trend=_fallback_daily_trend(entries, "first_seen_at", days, window_start),
        alerts=StatsAlertsResponse(
            total=len(alerts),
            by_status=_fallback_distribution(alerts, "status", _ALERT_STATUS_KEYS),
            trend=_fallback_daily_trend(alerts, "triggered_at", days, window_start),
        ),
        sources=_fallback_sources(sources, source_links),
    )


def _sql_alerts(session: Session, days: list[date], window_start: datetime) -> StatsAlertsResponse:
    total = session.scalar(select(func.count()).select_from(Alert)) or 0
    return StatsAlertsResponse(
        total=total,
        by_status=_sql_distribution(session, Alert.status, _ALERT_STATUS_KEYS),
        trend=_sql_daily_trend(session, Alert.triggered_at, days, window_start),
    )


def _sql_intelligence_count(session: Session, *conditions) -> int:
    statement = select(func.count()).select_from(ThreatIntelligence)
    if conditions:
        statement = statement.where(*conditions)
    return session.scalar(statement) or 0


def _sql_distribution(session: Session, column, keys: Sequence[str]) -> dict[str, int]:
    counts = {key: 0 for key in keys}
    for value, count in session.execute(select(column, func.count()).group_by(column)).all():
        key = _enum_value(value)
        if key in counts:
            counts[key] = int(count)
    return counts


def _sql_daily_trend(
    session: Session,
    column,
    days: list[date],
    window_start: datetime,
) -> list[StatsTrendPointResponse]:
    counts = {day: 0 for day in days}
    utc_day = func.date(func.timezone("UTC", column))
    for row_day, count in session.execute(
        select(utc_day, func.count()).where(column >= window_start).group_by(utc_day)
    ).all():
        key = _utc_date(row_day) if isinstance(row_day, datetime) else row_day
        if key in counts:
            counts[key] = int(count)
    return [StatsTrendPointResponse(date=day, count=counts[day]) for day in days]


def _sql_sources(session: Session) -> StatsSourcesResponse:
    enabled = (
        session.scalar(
            select(func.count()).select_from(Source).where(Source.status == SourceStatus.ENABLED)
        )
        or 0
    )
    intelligence_count = func.count(func.distinct(ThreatIntelligenceSource.threat_intelligence_id))
    rows = session.execute(
        select(Source.id, Source.name, intelligence_count)
        .join(ThreatIntelligenceSource, ThreatIntelligenceSource.source_id == Source.id)
        .group_by(Source.id, Source.name)
        .order_by(intelligence_count.desc(), Source.name.asc())
        .limit(SOURCE_TOP_LIMIT)
    ).all()
    top = [
        StatsSourceTopResponse(id=row_id, name=name, intelligence_count=int(count))
        for row_id, name, count in rows
    ]
    return StatsSourcesResponse(enabled=enabled, top=top)


def _fallback_distribution(items: list[Any], attribute: str, keys: Sequence[str]) -> dict[str, int]:
    counts = {key: 0 for key in keys}
    for item in items:
        key = _enum_value(getattr(item, attribute))
        if key in counts:
            counts[key] += 1
    return counts


def _fallback_daily_trend(
    items: list[Any],
    attribute: str,
    days: list[date],
    window_start: datetime,
) -> list[StatsTrendPointResponse]:
    counts = {day: 0 for day in days}
    for item in items:
        value = getattr(item, attribute)
        if value is None or value < window_start:
            continue
        day = _utc_date(value)
        if day in counts:
            counts[day] += 1
    return [StatsTrendPointResponse(date=day, count=counts[day]) for day in days]


def _fallback_sources(sources: list[Any], source_links: list[Any]) -> StatsSourcesResponse:
    enabled = sum(
        1 for source in sources if _enum_value(source.status) == SourceStatus.ENABLED.value
    )
    intelligence_ids_by_source: dict[UUID, set[UUID]] = {}
    for link in source_links:
        if link.source_id is None:
            continue
        intelligence_ids_by_source.setdefault(link.source_id, set()).add(link.threat_intelligence_id)
    names = {source.id: source.name for source in sources}
    ranked = sorted(
        (
            (source_id, len(intelligence_ids))
            for source_id, intelligence_ids in intelligence_ids_by_source.items()
            if source_id in names
        ),
        key=lambda item: (-item[1], names[item[0]]),
    )
    top = [
        StatsSourceTopResponse(
            id=source_id,
            name=names[source_id],
            intelligence_count=count,
        )
        for source_id, count in ranked[:SOURCE_TOP_LIMIT]
    ]
    return StatsSourcesResponse(enabled=enabled, top=top)


def _trend_days(now: datetime) -> list[date]:
    today = now.date()
    return [today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1)]


def _utc_date(value: datetime) -> date:
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(timezone.utc).date()


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
