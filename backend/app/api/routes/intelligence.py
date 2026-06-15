from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_request_session
from app.api.safety import safe_dict, safe_metadata, safe_text, safe_url
from app.api.schemas.intelligence import (
    IntelligenceDetailResponse,
    IntelligenceIngestRequest,
    IntelligenceIngestResponse,
    IntelligenceListItemResponse,
    IntelligencePageResponse,
    IntelligenceSort,
    RelatedAlertResponse,
    SourceAttributionResponse,
)
from app.db.types import AttackSurface, AuditAction, IntelligenceType, RiskLevel, Severity, VehicleComponent
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import User
from app.services.audit import record_audit_event
from app.services.intelligence_ingest import ingest_external_intelligence, ingest_response_snapshot

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

_SEVERITY_RANK = {
    "unknown": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class IntelligenceSearchParams:
    q: str | None = None
    cve: str | None = None
    vendor: str | None = None
    product: str | None = None
    vehicle_component: VehicleComponent | None = None
    attack_surface: AttackSurface | None = None
    risk_level: RiskLevel | None = None
    tag: str | None = None
    source: str | None = None
    status: str | None = None
    intelligence_type: IntelligenceType | None = None
    sort: IntelligenceSort = IntelligenceSort.RECENT


@router.post("/ingest", response_model=IntelligenceIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_intelligence(
    payload: IntelligenceIngestRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> IntelligenceIngestResponse:
    outcome = ingest_external_intelligence(session, payload, actor_user_id=current_user.id)
    snapshot = ingest_response_snapshot(outcome.entry, duplicate=outcome.duplicate)
    record_audit_event(
        session,
        action=AuditAction.MANUAL_ENTRY,
        entity_type="threat_intelligence",
        summary="External intelligence ingested" if not outcome.duplicate else "Duplicate external intelligence ingested",
        actor_user_id=current_user.id,
        entity_id=outcome.entry.id,
        after=snapshot,
        metadata={
            "entry_origin": "external_ingest",
            "duplicate": outcome.duplicate,
            "dedup_key": outcome.entry.dedup_key,
            "source_name": safe_text(payload.source_name),
            "platform": safe_text(payload.platform),
        },
    )
    session.commit()
    session.refresh(outcome.entry)
    if outcome.duplicate:
        response.status_code = status.HTTP_200_OK
    return IntelligenceIngestResponse(
        id=outcome.entry.id,
        raw_intelligence_id=outcome.entry.raw_intelligence_id,
        status=outcome.result,
        duplicate=outcome.duplicate,
        dedup_key=outcome.entry.dedup_key,
        title=outcome.entry.title,
        cve_id=outcome.entry.cve_id,
        source_name=_first_value(outcome.entry.source_names) or "",
        source_url=safe_url(_first_value(outcome.entry.source_urls)) or "",
        message="外部情报已接收。" if not outcome.duplicate else "外部情报已存在，已更新来源信息。",
    )


@router.get("", response_model=IntelligencePageResponse)
async def list_intelligence(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    cve: str | None = Query(default=None, min_length=1, max_length=32),
    vendor: str | None = Query(default=None, min_length=1, max_length=160),
    product: str | None = Query(default=None, min_length=1, max_length=200),
    vehicle_component: VehicleComponent | None = None,
    attack_surface: AttackSurface | None = None,
    risk_level: RiskLevel | None = None,
    tag: str | None = Query(default=None, min_length=1, max_length=80),
    source: str | None = Query(default=None, min_length=1, max_length=240),
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=40),
    intelligence_type: IntelligenceType | None = None,
    sort: IntelligenceSort = IntelligenceSort.RECENT,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> IntelligencePageResponse:
    del current_user
    params = IntelligenceSearchParams(
        q=_clean(q),
        cve=_normalize_cve(cve),
        vendor=_clean(vendor),
        product=_clean(product),
        vehicle_component=vehicle_component,
        attack_surface=attack_surface,
        risk_level=risk_level,
        tag=_clean(tag),
        source=_clean(source),
        status=_clean(status_filter),
        intelligence_type=intelligence_type,
        sort=sort,
    )
    statement = _build_search_statement(params)
    offset = (page - 1) * limit
    if isinstance(session, Session):
        total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        page_items = list(session.scalars(statement.offset(offset).limit(limit)).all())
    else:
        entries = list(session.scalars(statement).all())
        filtered = [entry for entry in entries if _matches_params(entry, params)]
        sorted_entries = _sort_entries(filtered, sort)
        total = len(sorted_entries)
        page_items = sorted_entries[offset : offset + limit]
    return IntelligencePageResponse(
        items=[_list_item_response(entry) for entry in page_items],
        page=page,
        limit=limit,
        total=total,
        has_next=offset + limit < total,
    )


@router.get("/{intelligence_id}", response_model=IntelligenceDetailResponse)
async def get_intelligence(
    intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> IntelligenceDetailResponse:
    del current_user
    entry = session.get(ThreatIntelligence, intelligence_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "intelligence_not_found", "message": "情报记录不存在。"}},
        )
    return _detail_response(entry)


def _build_search_statement(params: IntelligenceSearchParams) -> Select:
    statement = select(ThreatIntelligence).options(
        selectinload(ThreatIntelligence.source_links),
        selectinload(ThreatIntelligence.alerts),
    )
    conditions = []
    if params.q:
        conditions.append(_text_search_condition(params.q))
    if params.cve:
        conditions.append(func.lower(ThreatIntelligence.cve_id) == params.cve.lower())
    if params.vendor:
        conditions.append(ThreatIntelligence.affected_vendor.ilike(_like_pattern(params.vendor)))
    if params.product:
        conditions.append(ThreatIntelligence.affected_product.ilike(_like_pattern(params.product)))
    if params.vehicle_component:
        conditions.append(ThreatIntelligence.vehicle_component == params.vehicle_component)
    if params.attack_surface:
        conditions.append(ThreatIntelligence.attack_surface == params.attack_surface)
    if params.risk_level:
        conditions.append(ThreatIntelligence.risk_level == params.risk_level)
    if params.tag:
        conditions.append(func.array_to_string(ThreatIntelligence.tags, " ").ilike(_like_pattern(params.tag)))
    if params.source:
        source_pattern = _like_pattern(params.source)
        conditions.append(
            or_(
                func.array_to_string(ThreatIntelligence.source_names, " ").ilike(source_pattern),
                func.array_to_string(ThreatIntelligence.source_urls, " ").ilike(source_pattern),
                ThreatIntelligence.canonical_source_url.ilike(source_pattern),
                ThreatIntelligence.source_links.any(
                    or_(
                        ThreatIntelligenceSource.source_name.ilike(source_pattern),
                        ThreatIntelligenceSource.source_url.ilike(source_pattern),
                        ThreatIntelligenceSource.external_id.ilike(source_pattern),
                    )
                ),
            )
        )
    if params.status:
        conditions.append(ThreatIntelligence.status == params.status)
    if params.intelligence_type:
        conditions.append(ThreatIntelligence.intelligence_type == params.intelligence_type)
    if conditions:
        statement = statement.where(*conditions)
    return statement.order_by(*_sql_order_by(params.sort))


def _text_search_condition(query: str):
    pattern = _like_pattern(query)
    return or_(
        ThreatIntelligence.search_vector.op("@@")(func.plainto_tsquery("simple", query)),
        ThreatIntelligence.title.ilike(pattern),
        ThreatIntelligence.summary.ilike(pattern),
        ThreatIntelligence.cve_id.ilike(pattern),
        ThreatIntelligence.cwe_id.ilike(pattern),
        ThreatIntelligence.affected_vendor.ilike(pattern),
        ThreatIntelligence.affected_product.ilike(pattern),
        func.array_to_string(ThreatIntelligence.tags, " ").ilike(pattern),
    )


def _sql_order_by(sort: IntelligenceSort):
    if sort is IntelligenceSort.FIRST_SEEN:
        return (ThreatIntelligence.first_seen_at.desc(), ThreatIntelligence.id.asc())
    if sort is IntelligenceSort.RISK_SCORE:
        return (ThreatIntelligence.risk_score.desc().nullslast(), ThreatIntelligence.last_seen_at.desc(), ThreatIntelligence.id.asc())
    if sort is IntelligenceSort.SEVERITY:
        severity_rank = case(
            (ThreatIntelligence.severity == Severity.CRITICAL, 4),
            (ThreatIntelligence.severity == Severity.HIGH, 3),
            (ThreatIntelligence.severity == Severity.MEDIUM, 2),
            (ThreatIntelligence.severity == Severity.LOW, 1),
            else_=0,
        )
        return (
            severity_rank.desc(),
            ThreatIntelligence.risk_score.desc().nullslast(),
            ThreatIntelligence.last_seen_at.desc(),
            ThreatIntelligence.id.asc(),
        )
    return (ThreatIntelligence.last_seen_at.desc(), ThreatIntelligence.id.asc())


def _matches_params(entry: ThreatIntelligence, params: IntelligenceSearchParams) -> bool:
    if params.q and not _entry_matches_text(entry, params.q):
        return False
    if params.cve and _lower(entry.cve_id) != params.cve.lower():
        return False
    if params.vendor and params.vendor.lower() not in _lower(entry.affected_vendor):
        return False
    if params.product and params.product.lower() not in _lower(entry.affected_product):
        return False
    if params.vehicle_component and _enum_value(entry.vehicle_component) != params.vehicle_component.value:
        return False
    if params.attack_surface and _enum_value(entry.attack_surface) != params.attack_surface.value:
        return False
    if params.risk_level and _enum_value(entry.risk_level) != params.risk_level.value:
        return False
    if params.tag and params.tag.lower() not in {_lower(tag) for tag in (entry.tags or [])}:
        return False
    if params.source and not _entry_matches_source(entry, params.source):
        return False
    if params.status and entry.status != params.status:
        return False
    if params.intelligence_type and _enum_value(entry.intelligence_type) != params.intelligence_type.value:
        return False
    return True


def _entry_matches_text(entry: ThreatIntelligence, query: str) -> bool:
    needle = query.lower()
    values: list[Any] = [
        entry.title,
        entry.summary,
        entry.cve_id,
        entry.cwe_id,
        entry.affected_vendor,
        entry.affected_product,
        entry.affected_version,
        _enum_value(entry.vehicle_component),
        _enum_value(entry.attack_surface),
        _enum_value(entry.severity),
        _enum_value(entry.risk_level),
        entry.status,
        *(entry.tags or []),
        *(entry.source_names or []),
        *(entry.source_urls or []),
    ]
    return any(needle in _lower(value) for value in values)


def _entry_matches_source(entry: ThreatIntelligence, source: str) -> bool:
    needle = source.lower()
    values: list[Any] = [
        *(entry.source_names or []),
        *(entry.source_urls or []),
        entry.canonical_source_url,
    ]
    for source_link in entry.source_links or []:
        values.extend((source_link.source_name, source_link.source_url, source_link.external_id))
    return any(needle in _lower(value) for value in values)


def _sort_entries(entries: list[ThreatIntelligence], sort: IntelligenceSort) -> list[ThreatIntelligence]:
    sorted_entries = sorted(entries, key=lambda entry: str(entry.id))
    if sort is IntelligenceSort.FIRST_SEEN:
        sorted_entries.sort(key=lambda entry: _datetime_key(entry.first_seen_at), reverse=True)
    elif sort is IntelligenceSort.RISK_SCORE:
        sorted_entries.sort(
            key=lambda entry: (_number_key(entry.risk_score), _datetime_key(entry.last_seen_at)),
            reverse=True,
        )
    elif sort is IntelligenceSort.SEVERITY:
        sorted_entries.sort(
            key=lambda entry: (
                _SEVERITY_RANK.get(_enum_value(entry.severity), 0),
                _number_key(entry.risk_score),
                _datetime_key(entry.last_seen_at),
            ),
            reverse=True,
        )
    else:
        sorted_entries.sort(key=lambda entry: _datetime_key(entry.last_seen_at), reverse=True)
    return sorted_entries


def _list_item_response(entry: ThreatIntelligence) -> IntelligenceListItemResponse:
    metadata = safe_metadata(entry.metadata_ or {})
    return IntelligenceListItemResponse(
        id=entry.id,
        title=entry.title,
        summary=entry.summary,
        intelligence_type=entry.intelligence_type,
        source_names=entry.source_names or [],
        source_urls=[clean_url for source_url in (entry.source_urls or []) if (clean_url := safe_url(source_url))],
        canonical_source_url=safe_url(entry.canonical_source_url),
        cve_id=entry.cve_id,
        cwe_id=entry.cwe_id,
        cvss_score=entry.cvss_score,
        cvss_vector=entry.cvss_vector,
        severity=entry.severity,
        affected_vendor=entry.affected_vendor,
        affected_product=entry.affected_product,
        affected_version=entry.affected_version,
        vehicle_component=entry.vehicle_component,
        attack_surface=entry.attack_surface,
        exploit_status=entry.exploit_status,
        confidence=entry.confidence,
        risk_score=_float_or_none(entry.risk_score),
        risk_level=entry.risk_level,
        status=entry.status,
        tags=entry.tags or [],
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        metadata=metadata,
        score_metadata=_score_metadata(entry.metadata_ or {}),
        score_explanation=_score_explanation(entry.metadata_ or {}),
        sources=_source_responses(entry),
        related_alert_count=len(entry.alerts or []),
    )


def _detail_response(entry: ThreatIntelligence) -> IntelligenceDetailResponse:
    base = _list_item_response(entry).model_dump()
    return IntelligenceDetailResponse(
        **base,
        raw_intelligence_id=entry.raw_intelligence_id,
        external_ids=safe_dict(entry.external_ids or {}),
        dedup_key=entry.dedup_key,
        normalized_text_hash=entry.normalized_text_hash,
        related_alerts=[
            RelatedAlertResponse(
                id=alert.id,
                title=alert.title,
                risk_level=alert.risk_level,
                status=alert.status,
                triggered_at=alert.triggered_at,
            )
            for alert in sorted(entry.alerts or [], key=lambda item: item.triggered_at, reverse=True)
        ],
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
    responses: list[SourceAttributionResponse] = []
    source_names = entry.source_names or []
    source_urls = entry.source_urls or []
    for index, source_name in enumerate(source_names):
        source_url = source_urls[index] if index < len(source_urls) else entry.canonical_source_url
        if source_url:
            responses.append(
                SourceAttributionResponse(
                    id=None,
                    source_id=None,
                    raw_intelligence_id=entry.raw_intelligence_id,
                    source_name=source_name,
                    source_url=safe_url(source_url) or "",
                    external_id=None,
                    first_seen_at=entry.first_seen_at,
                    last_seen_at=entry.last_seen_at,
                )
            )
    return responses


def _score_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    for key in ("score_metadata", "scoring", "risk_scoring", "score"):
        value = metadata.get(key)
        if isinstance(value, dict):
            safe_value = safe_metadata(value)
            return safe_value if isinstance(safe_value, dict) else {}
    return {}


def _score_explanation(metadata: dict[str, Any]) -> str | None:
    for key in ("score_explanation", "scoring_explanation", "risk_explanation", "explanation"):
        value = metadata.get(key)
        if isinstance(value, str) and safe_text(value) is not None:
            return value
        if isinstance(value, list):
            explanation = "; ".join(str(item) for item in value if item is not None)
            if explanation and safe_text(explanation) is not None:
                return explanation[:1000]
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_cve(value: str | None) -> str | None:
    cleaned = _clean(value)
    return cleaned.upper() if cleaned else None


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _lower(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value).lower()
    return str(value).lower()


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


def _number_key(value: Any) -> float:
    if value is None:
        return -1.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _first_value(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]
