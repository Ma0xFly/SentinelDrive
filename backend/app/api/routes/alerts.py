from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_session
from app.api.safety import safe_metadata, safe_text, safe_url
from app.api.schemas.alerts import (
    AlertDetailResponse,
    AlertGenerationRequest,
    AlertGenerationResponse,
    AlertIntelligenceSummaryResponse,
    AlertPageResponse,
    AlertResponse,
    AlertSort,
    AlertStatusUpdateRequest,
)
from app.api.schemas.intelligence import SourceAttributionResponse
from app.db.types import AlertStatus, AuditAction, RiskLevel
from app.models.intelligence import ThreatIntelligence
from app.models.security import Alert, User
from app.services.alerts import evaluate_and_create_alerts
from app.services.audit import record_audit_event

router = APIRouter(prefix="/alerts", tags=["alerts"])

_RISK_RANK = {
    "info": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class AlertSearchParams:
    risk_level: RiskLevel | None = None
    status: AlertStatus | None = None
    triggering_rule: str | None = None
    intelligence_id: UUID | None = None
    sort: AlertSort = AlertSort.RECENT


@router.get("", response_model=AlertPageResponse)
async def list_alerts(
    risk_level: RiskLevel | None = None,
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    triggering_rule: str | None = Query(default=None, min_length=1, max_length=240),
    intelligence_id: str | None = Query(default=None),
    sort: AlertSort = AlertSort.RECENT,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> AlertPageResponse:
    del current_user
    params = AlertSearchParams(
        risk_level=risk_level,
        status=status_filter,
        triggering_rule=_clean(triggering_rule),
        intelligence_id=_parse_alert_intelligence_id(intelligence_id),
        sort=sort,
    )
    statement = _build_alert_statement(params)
    offset = (page - 1) * limit
    if isinstance(session, Session):
        total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        page_items = list(session.scalars(statement.offset(offset).limit(limit)).all())
    else:
        alerts = list(session.scalars(statement).all())
        filtered = [alert for alert in alerts if _matches_alert(alert, params)]
        sorted_alerts = _sort_alerts(filtered, sort)
        total = len(sorted_alerts)
        page_items = sorted_alerts[offset : offset + limit]
    return AlertPageResponse(
        items=[_alert_response(alert) for alert in page_items],
        page=page,
        limit=limit,
        total=total,
        has_next=offset + limit < total,
    )


@router.get("/{alert_id}", response_model=AlertDetailResponse)
async def get_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> AlertDetailResponse:
    del current_user
    alert = _get_alert_or_404(session, alert_id)
    return _alert_detail_response(alert)


@router.patch("/{alert_id}/status", response_model=AlertDetailResponse)
async def update_alert_status(
    alert_id: UUID,
    payload: AlertStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> AlertDetailResponse:
    alert = _get_alert_or_404(session, alert_id)
    before = _audit_snapshot(alert)
    alert.status = payload.status
    if "notes" in payload.model_fields_set:
        alert.notes = payload.notes
    after = _audit_snapshot(alert)
    action = AuditAction.ALERT_CLOSURE if payload.status == AlertStatus.CLOSED else AuditAction.STATUS_CHANGE
    record_audit_event(
        session,
        action=action,
        entity_type="alert",
        summary="Alert status updated",
        actor_user_id=current_user.id,
        entity_id=alert.id,
        before=before,
        after=after,
        metadata={"triggering_rule": alert.triggering_rule, "threat_intelligence_id": str(alert.threat_intelligence_id)},
    )
    session.commit()
    session.refresh(alert)
    return _alert_detail_response(alert)


@router.post("/evaluate", response_model=AlertGenerationResponse)
async def evaluate_alerts(
    payload: AlertGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> AlertGenerationResponse:
    del current_user
    if payload.intelligence_id is not None and session.get(ThreatIntelligence, payload.intelligence_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "intelligence_not_found", "message": "情报记录不存在。"}},
        )
    created = evaluate_and_create_alerts(session, intelligence_id=payload.intelligence_id, limit=payload.limit)
    session.commit()
    for alert in created:
        session.refresh(alert)
    return AlertGenerationResponse(created=len(created), alert_ids=[alert.id for alert in created])


def _get_alert_or_404(session: Session, alert_id: UUID) -> Alert:
    alert = session.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "alert_not_found", "message": "告警不存在。"}},
        )
    return alert


def _build_alert_statement(params: AlertSearchParams) -> Select:
    statement = select(Alert).options(
        selectinload(Alert.intelligence).selectinload(ThreatIntelligence.source_links),
    )
    conditions = []
    if params.risk_level:
        conditions.append(Alert.risk_level == params.risk_level)
    if params.status:
        conditions.append(Alert.status == params.status)
    if params.triggering_rule:
        conditions.append(Alert.triggering_rule.ilike(_like_pattern(params.triggering_rule)))
    if params.intelligence_id:
        conditions.append(Alert.threat_intelligence_id == params.intelligence_id)
    if conditions:
        statement = statement.where(*conditions)
    return statement.order_by(*_sql_order_by(params.sort))


def _sql_order_by(sort: AlertSort):
    if sort is AlertSort.RISK_LEVEL:
        risk_rank = case(
            (Alert.risk_level == RiskLevel.CRITICAL, 4),
            (Alert.risk_level == RiskLevel.HIGH, 3),
            (Alert.risk_level == RiskLevel.MEDIUM, 2),
            (Alert.risk_level == RiskLevel.LOW, 1),
            else_=0,
        )
        return (risk_rank.desc(), Alert.triggered_at.desc(), Alert.id.asc())
    return (Alert.triggered_at.desc(), Alert.id.asc())


def _matches_alert(alert: Alert, params: AlertSearchParams) -> bool:
    if params.risk_level and _enum_value(alert.risk_level) != params.risk_level.value:
        return False
    if params.status and _enum_value(alert.status) != params.status.value:
        return False
    if params.triggering_rule and params.triggering_rule.lower() not in alert.triggering_rule.lower():
        return False
    if params.intelligence_id and alert.threat_intelligence_id != params.intelligence_id:
        return False
    return True


def _sort_alerts(alerts: list[Alert], sort: AlertSort) -> list[Alert]:
    sorted_alerts = sorted(alerts, key=lambda alert: str(alert.id))
    if sort is AlertSort.RISK_LEVEL:
        sorted_alerts.sort(
            key=lambda alert: (_RISK_RANK.get(_enum_value(alert.risk_level) or "info", 0), _datetime_key(alert.triggered_at)),
            reverse=True,
        )
    else:
        sorted_alerts.sort(key=lambda alert: _datetime_key(alert.triggered_at), reverse=True)
    return sorted_alerts


def _alert_response(alert: Alert) -> AlertResponse:
    return AlertResponse(
        id=alert.id,
        title=alert.title,
        threat_intelligence_id=alert.threat_intelligence_id,
        triggering_rule=alert.triggering_rule,
        risk_level=alert.risk_level,
        triggered_at=alert.triggered_at,
        status=alert.status,
        notes=safe_text(alert.notes),
        metadata=safe_metadata(alert.metadata_ or {}),
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


def _alert_detail_response(alert: Alert) -> AlertDetailResponse:
    base = _alert_response(alert).model_dump()
    return AlertDetailResponse(**base, intelligence=_intelligence_summary(alert.intelligence))


def _intelligence_summary(entry: ThreatIntelligence | None) -> AlertIntelligenceSummaryResponse | None:
    if entry is None:
        return None
    return AlertIntelligenceSummaryResponse(
        id=entry.id,
        title=entry.title,
        summary=entry.summary,
        intelligence_type=entry.intelligence_type,
        cve_id=entry.cve_id,
        severity=entry.severity,
        affected_vendor=entry.affected_vendor,
        affected_product=entry.affected_product,
        vehicle_component=entry.vehicle_component,
        attack_surface=entry.attack_surface,
        risk_score=_float_or_none(entry.risk_score),
        risk_level=entry.risk_level,
        status=entry.status,
        source_names=entry.source_names or [],
        source_urls=[clean_url for source_url in (entry.source_urls or []) if (clean_url := safe_url(source_url))],
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        sources=_source_responses(entry),
    )


def _source_responses(entry: ThreatIntelligence) -> list[SourceAttributionResponse]:
    links = list(entry.source_links or [])
    if links:
        return [
            SourceAttributionResponse(
                id=source.id,
                source_id=source.source_id,
                raw_intelligence_id=source.raw_intelligence_id,
                source_name=source.source_name,
                source_url=safe_url(source.source_url) or "",
                external_id=safe_text(source.external_id),
                first_seen_at=source.first_seen_at,
                last_seen_at=source.last_seen_at,
            )
            for source in links
        ]
    return [
        SourceAttributionResponse(
            id=None,
            source_id=None,
            raw_intelligence_id=entry.raw_intelligence_id,
            source_name=source_name,
            source_url=safe_url((entry.source_urls or [entry.canonical_source_url])[index]) or "",
            external_id=None,
            first_seen_at=entry.first_seen_at,
            last_seen_at=entry.last_seen_at,
        )
        for index, source_name in enumerate(entry.source_names or [])
        if index < len(entry.source_urls or [entry.canonical_source_url])
    ]


def _audit_snapshot(alert: Alert) -> dict[str, Any]:
    return {
        "id": str(alert.id),
        "status": _enum_value(alert.status),
        "notes": safe_text(alert.notes),
        "triggering_rule": alert.triggering_rule,
        "threat_intelligence_id": str(alert.threat_intelligence_id),
    }


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_alert_intelligence_id(value: str | None) -> UUID | None:
    if value is None or value == "":
        return None
    cleaned = value.strip()
    try:
        return UUID(cleaned)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "invalid_intelligence_id",
                    "message": "情报 ID 格式无效。",
                }
            },
        ) from None


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _datetime_key(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return value.timestamp()


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
