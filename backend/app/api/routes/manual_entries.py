import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_session
from app.api.schemas.manual_entries import (
    ManualEntryCategory,
    ManualEntryCreateRequest,
    ManualEntryResponse,
    ManualEntryStatus,
    ManualEntryUpdateRequest,
)
from app.db.types import AuditAction, IntelligenceType, ProcessingStatus, SourceType
from app.models.intelligence import RawIntelligence, ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import User
from app.services.audit import record_audit_event

router = APIRouter(prefix="/manual-entries", tags=["manual-entries"])

_CATEGORY_TO_INTELLIGENCE_TYPE = {
    ManualEntryCategory.VULNERABILITY: IntelligenceType.VULNERABILITY,
    ManualEntryCategory.ADVISORY: IntelligenceType.ADVISORY,
    ManualEntryCategory.INCIDENT: IntelligenceType.INCIDENT,
    ManualEntryCategory.EXPOSURE: IntelligenceType.EXPOSURE,
    ManualEntryCategory.RESEARCH_LEAD: IntelligenceType.ADVISORY,
}


@router.post("", response_model=ManualEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_entry(
    payload: ManualEntryCreateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> ManualEntryResponse:
    source_name = _source_name(payload.source_name, payload.source_url)
    source_url = _source_url(payload.source_url, source_name)
    dedup_key = _dedup_key(payload.category, payload.cve_id, payload.title, source_name, source_url)
    existing = session.scalar(select(ThreatIntelligence).where(ThreatIntelligence.dedup_key == dedup_key))
    if existing is not None and not _is_manual_entry(existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "intelligence_duplicate", "message": "情报记录已存在。"}},
        )
    if existing is not None:
        existing.last_seen_at = datetime.now(timezone.utc)
        record_audit_event(
            session,
            action=AuditAction.MANUAL_ENTRY,
            entity_type="threat_intelligence",
            summary="Duplicate manual entry submitted",
            actor_user_id=current_user.id,
            entity_id=existing.id,
            metadata={"duplicate": True, "dedup_key": dedup_key},
        )
        session.commit()
        session.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return _manual_entry_response(existing)

    now = datetime.now(timezone.utc)
    normalized_payload = _normalized_payload(payload, source_name, source_url)
    content_hash = _hash_dict(normalized_payload)
    raw_item = RawIntelligence(
        source_name=source_name,
        source_type=SourceType.MANUAL,
        source_url=source_url,
        external_id=dedup_key,
        fetched_at=now,
        first_seen_at=now,
        title=payload.title,
        summary=payload.summary,
        snippet=payload.summary[:500],
        raw_content=None,
        raw_hash=content_hash,
        content_hash=content_hash,
        parsing_status=ProcessingStatus.NORMALIZED,
        processing_status=ProcessingStatus.NORMALIZED,
        metadata_={
            "entry_origin": "manual",
            "manual_entry_category": payload.category.value,
            "submitted_by_user_id": str(current_user.id),
        },
        retained_payload_mode="metadata_only",
    )
    session.add(raw_item)
    session.flush()

    entry = ThreatIntelligence(
        raw_intelligence_id=raw_item.id,
        title=payload.title,
        summary=payload.summary,
        intelligence_type=_CATEGORY_TO_INTELLIGENCE_TYPE[payload.category],
        source_names=[source_name],
        source_urls=[source_url],
        canonical_source_url=source_url,
        external_ids=_external_ids(payload),
        cve_id=payload.cve_id,
        cwe_id=payload.cwe_id,
        cvss_score=payload.cvss_score,
        cvss_vector=payload.cvss_vector,
        severity=payload.severity,
        affected_vendor=payload.affected_vendor,
        affected_product=payload.affected_product,
        affected_version=payload.affected_version,
        vehicle_component=payload.vehicle_component,
        attack_surface=payload.attack_surface,
        exploit_status=payload.exploit_status,
        confidence=payload.confidence,
        risk_score=payload.risk_score,
        risk_level=payload.risk_level,
        tags=_manual_tags(payload.category, payload.tags),
        first_seen_at=now,
        last_seen_at=now,
        dedup_key=dedup_key,
        normalized_text_hash=content_hash,
        processing_status=ProcessingStatus.NORMALIZED,
        status=_initial_status(payload.category, payload.status),
        metadata_={
            "entry_origin": "manual",
            "manual_entry_category": payload.category.value,
            "submitted_by_user_id": str(current_user.id),
        },
    )
    session.add(entry)
    session.flush()
    session.add(
        ThreatIntelligenceSource(
            threat_intelligence_id=entry.id,
            raw_intelligence_id=raw_item.id,
            source_name=source_name,
            source_url=source_url,
            external_id=dedup_key,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    record_audit_event(
        session,
        action=AuditAction.MANUAL_ENTRY,
        entity_type="threat_intelligence",
        summary="Manual entry created",
        actor_user_id=current_user.id,
        entity_id=entry.id,
        after=_audit_snapshot(entry),
        metadata={"dedup_key": dedup_key},
    )
    session.commit()
    session.refresh(entry)
    return _manual_entry_response(entry)


@router.get("", response_model=list[ManualEntryResponse])
async def list_manual_entries(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> list[ManualEntryResponse]:
    del current_user
    entries = session.scalars(
        select(ThreatIntelligence)
        .where(ThreatIntelligence.tags.contains(["manual"]))
        .order_by(ThreatIntelligence.last_seen_at.desc(), ThreatIntelligence.created_at.desc())
    ).all()
    return [_manual_entry_response(entry) for entry in entries if _is_manual_entry(entry)]


@router.get("/{entry_id}", response_model=ManualEntryResponse)
async def get_manual_entry(
    entry_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> ManualEntryResponse:
    del current_user
    entry = _get_manual_entry_or_404(session, entry_id)
    return _manual_entry_response(entry)


@router.patch("/{entry_id}", response_model=ManualEntryResponse)
async def update_manual_entry(
    entry_id: UUID,
    payload: ManualEntryUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> ManualEntryResponse:
    entry = _get_manual_entry_or_404(session, entry_id)
    before = _audit_snapshot(entry)
    previous_status = entry.status
    update_data = payload.model_dump(exclude_unset=True)

    for field_name in (
        "title",
        "summary",
        "cve_id",
        "cwe_id",
        "cvss_score",
        "cvss_vector",
        "severity",
        "affected_vendor",
        "affected_product",
        "affected_version",
        "vehicle_component",
        "attack_surface",
        "exploit_status",
        "confidence",
        "risk_score",
        "risk_level",
        "status",
    ):
        if field_name in update_data:
            value = update_data[field_name]
            if isinstance(value, ManualEntryStatus):
                value = value.value
            setattr(entry, field_name, value)

    if "tags" in update_data:
        entry.tags = _manual_tags(_entry_category(entry), update_data["tags"] or [])

    if "source_name" in update_data or "source_url" in update_data:
        source_name_input = update_data.get("source_name") if "source_name" in update_data else _first(entry.source_names)
        source_url_input = update_data.get("source_url") if "source_url" in update_data else _first(entry.source_urls)
        source_name = _source_name(source_name_input, source_url_input)
        source_url = _source_url(source_url_input, source_name)
        entry.source_names = [source_name]
        entry.source_urls = [source_url]
        entry.canonical_source_url = source_url

    entry.last_seen_at = datetime.now(timezone.utc)
    new_dedup_key = _dedup_key(
        _entry_category(entry),
        entry.cve_id,
        entry.title,
        _first(entry.source_names),
        _first(entry.source_urls),
    )
    if new_dedup_key != entry.dedup_key:
        existing = session.scalar(select(ThreatIntelligence).where(ThreatIntelligence.dedup_key == new_dedup_key))
        if existing is not None and existing.id != entry.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": {"code": "manual_entry_duplicate", "message": "人工录入条目已存在。"}},
            )
        entry.dedup_key = new_dedup_key

    entry.normalized_text_hash = _hash_dict(_audit_snapshot(entry))
    if entry.raw_item is not None:
        entry.raw_item.title = entry.title
        entry.raw_item.summary = entry.summary
        entry.raw_item.snippet = entry.summary[:500] if entry.summary else None
        entry.raw_item.source_name = _first(entry.source_names)
        entry.raw_item.source_url = _first(entry.source_urls)
        entry.raw_item.content_hash = entry.normalized_text_hash
    if entry.source_links:
        source_link = entry.source_links[0]
        source_link.source_name = _first(entry.source_names)
        source_link.source_url = _first(entry.source_urls)
        source_link.external_id = entry.dedup_key
        source_link.last_seen_at = entry.last_seen_at

    after = _audit_snapshot(entry)
    audit_action = AuditAction.STATUS_CHANGE if previous_status != entry.status else AuditAction.MANUAL_ENTRY
    audit_summary = "Manual entry status updated" if previous_status != entry.status else "Manual entry updated"
    record_audit_event(
        session,
        action=audit_action,
        entity_type="threat_intelligence",
        summary=audit_summary,
        actor_user_id=current_user.id,
        entity_id=entry.id,
        before=before,
        after=after,
        metadata={"dedup_key": entry.dedup_key},
    )
    session.commit()
    session.refresh(entry)
    return _manual_entry_response(entry)


def _get_manual_entry_or_404(session: Session, entry_id: UUID) -> ThreatIntelligence:
    entry = session.get(ThreatIntelligence, entry_id)
    if entry is None or not _is_manual_entry(entry):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "manual_entry_not_found", "message": "人工录入条目不存在。"}},
        )
    return entry


def _is_manual_entry(entry: ThreatIntelligence) -> bool:
    metadata = entry.metadata_ or {}
    return metadata.get("entry_origin") == "manual" or "manual" in (entry.tags or [])


def _entry_category(entry: ThreatIntelligence) -> ManualEntryCategory:
    category = (entry.metadata_ or {}).get("manual_entry_category")
    if category:
        return ManualEntryCategory(category)
    if "research_lead" in (entry.tags or []):
        return ManualEntryCategory.RESEARCH_LEAD
    return ManualEntryCategory(entry.intelligence_type.value if hasattr(entry.intelligence_type, "value") else entry.intelligence_type)


def _manual_entry_response(entry: ThreatIntelligence) -> ManualEntryResponse:
    return ManualEntryResponse(
        id=entry.id,
        raw_intelligence_id=entry.raw_intelligence_id,
        category=_entry_category(entry),
        intelligence_type=entry.intelligence_type,
        title=entry.title,
        summary=entry.summary,
        source_name=_first(entry.source_names),
        source_url=_first(entry.source_urls),
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
        risk_score=entry.risk_score,
        risk_level=entry.risk_level,
        status=entry.status,
        tags=entry.tags or [],
        dedup_key=entry.dedup_key,
        first_seen_at=entry.first_seen_at,
        last_seen_at=entry.last_seen_at,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _audit_snapshot(entry: ThreatIntelligence) -> dict:
    return {
        "id": str(entry.id) if entry.id else None,
        "category": _entry_category(entry).value,
        "title": entry.title,
        "status": entry.status,
        "dedup_key": entry.dedup_key,
        "cve_id": entry.cve_id,
        "source_name": _first(entry.source_names),
        "source_url": _first(entry.source_urls),
    }


def _normalized_payload(payload: ManualEntryCreateRequest, source_name: str, source_url: str) -> dict:
    return {
        "category": payload.category.value,
        "title": payload.title,
        "summary": payload.summary,
        "source_name": source_name,
        "source_url": source_url,
        "cve_id": payload.cve_id,
        "cwe_id": payload.cwe_id,
        "affected_vendor": payload.affected_vendor,
        "affected_product": payload.affected_product,
        "vehicle_component": payload.vehicle_component.value if payload.vehicle_component else None,
        "attack_surface": payload.attack_surface.value if payload.attack_surface else None,
    }


def _external_ids(payload: ManualEntryCreateRequest) -> dict:
    external_ids = {"manual_entry_category": payload.category.value}
    if payload.cve_id:
        external_ids["cve_id"] = payload.cve_id
    if payload.cwe_id:
        external_ids["cwe_id"] = payload.cwe_id
    return external_ids


def _manual_tags(category: ManualEntryCategory, requested_tags: list[str]) -> list[str]:
    tags = {"manual", category.value, *requested_tags}
    if category is ManualEntryCategory.RESEARCH_LEAD:
        tags.add("research_lead")
    return sorted(tags)


def _initial_status(category: ManualEntryCategory, requested_status: ManualEntryStatus | None) -> str:
    if requested_status is not None:
        return requested_status.value
    if category is ManualEntryCategory.RESEARCH_LEAD:
        return ManualEntryStatus.UNDER_REVIEW.value
    return ManualEntryStatus.ACTIVE.value


def _source_name(source_name: str | None, source_url: str | None) -> str:
    if source_name:
        return source_name
    if source_url:
        host = urlparse(source_url).netloc
        return host or "Manual Entry"
    return "Manual Entry"


def _source_url(source_url: str | None, source_name: str) -> str:
    if source_url:
        return source_url
    slug = re.sub(r"[^a-z0-9]+", "-", source_name.strip().lower()).strip("-")
    return f"manual://{slug or 'entry'}"


def _dedup_key(
    category: ManualEntryCategory,
    cve_id: str | None,
    title: str,
    source_name: str,
    source_url: str,
) -> str:
    if cve_id:
        return f"manual:cve:{cve_id.upper()}"
    signature = _hash_dict(
        {
            "category": category.value,
            "title": " ".join(title.lower().split()),
            "source_name": " ".join(source_name.lower().split()),
            "source_url": source_url.lower(),
        }
    )
    return f"manual:{category.value}:{signature[:32]}"


def _hash_dict(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _first(values: list[str] | None) -> str:
    if not values:
        return "manual://entry"
    return values[0]
