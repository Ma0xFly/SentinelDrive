from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urldefrag, urlsplit, urlunsplit

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.safety import safe_metadata, safe_text, safe_url
from app.api.schemas.intelligence import IntelligenceIngestRequest
from app.db.types import ConfidenceLevel, ExploitStatus, IntelligenceType, ProcessingStatus, RiskLevel, Severity, SourceType
from app.models.intelligence import RawIntelligence, ThreatIntelligence, ThreatIntelligenceSource


@dataclass(frozen=True)
class IngestOutcome:
    entry: ThreatIntelligence
    raw_item: RawIntelligence | None
    duplicate: bool
    result: str


def ingest_external_intelligence(session: Session, payload: IntelligenceIngestRequest, *, actor_user_id: Any) -> IngestOutcome:
    source_name = _source_name(payload)
    source_url = _canonical_url(payload.source_url) or payload.source_url
    collected_at = payload.collected_at or datetime.now(timezone.utc)
    published_at = payload.published_at or collected_at
    normalized_payload = _normalized_payload(payload, source_name, source_url)
    content_hash = payload.content_hash or _stable_hash(normalized_payload)
    normalized_text_hash = _stable_hash(_text_signature(payload, source_name, source_url))
    dedup_key = _dedup_key(payload, source_name, source_url, content_hash, normalized_text_hash)

    existing = _find_existing(session, payload, dedup_key, source_url)
    if existing is not None:
        _merge_existing(existing, payload, source_name, source_url, collected_at, content_hash, normalized_text_hash)
        _upsert_source_link(session, existing, None, source_name, source_url, payload.external_id or payload.dedup_key)
        return IngestOutcome(entry=existing, raw_item=None, duplicate=True, result="updated")

    raw_item = RawIntelligence(
        source_name=source_name,
        source_type=SourceType.API,
        source_url=source_url,
        external_id=payload.external_id or payload.dedup_key or payload.cve_id,
        fetched_at=collected_at,
        first_seen_at=published_at,
        title=payload.title,
        summary=payload.summary,
        snippet=(payload.description or payload.summary)[:500],
        raw_content=_safe_raw_payload(payload.raw_payload),
        raw_hash=_stable_hash({"source_name": source_name, "source_url": source_url, "content_hash": content_hash}),
        content_hash=content_hash,
        parsing_status=ProcessingStatus.NORMALIZED,
        processing_status=ProcessingStatus.NORMALIZED,
        metadata_=_metadata(payload, actor_user_id=actor_user_id),
        retained_payload_mode="metadata_only",
    )
    session.add(raw_item)
    session.flush()

    entry = ThreatIntelligence(
        raw_intelligence_id=raw_item.id,
        title=payload.title,
        summary=payload.summary,
        intelligence_type=_intelligence_type(payload),
        source_names=[source_name],
        source_urls=[source_url],
        canonical_source_url=source_url,
        external_ids=_external_ids(payload),
        cve_id=payload.cve_id,
        cwe_id=None,
        cvss_score=_cvss_score(payload),
        cvss_vector=None,
        severity=payload.severity,
        affected_vendor=payload.affected_vendor,
        affected_product=_first(payload.affected_products),
        affected_version=None,
        vehicle_component=None,
        attack_surface=None,
        exploit_status=ExploitStatus.UNKNOWN,
        confidence=ConfidenceLevel.MEDIUM,
        risk_score=payload.external_score,
        risk_level=_risk_level(payload.severity),
        tags=_tags(payload),
        first_seen_at=published_at,
        last_seen_at=collected_at,
        dedup_key=dedup_key,
        normalized_text_hash=normalized_text_hash,
        processing_status=ProcessingStatus.NORMALIZED,
        status="active",
        metadata_=_metadata(payload, actor_user_id=actor_user_id),
    )
    session.add(entry)
    session.flush()
    _upsert_source_link(session, entry, raw_item, source_name, source_url, payload.external_id or payload.dedup_key)
    return IngestOutcome(entry=entry, raw_item=raw_item, duplicate=False, result="created")


def ingest_response_snapshot(entry: ThreatIntelligence, *, duplicate: bool) -> dict[str, Any]:
    return {
        "id": str(entry.id) if entry.id else None,
        "duplicate": duplicate,
        "dedup_key": entry.dedup_key,
        "title": entry.title,
        "cve_id": entry.cve_id,
        "source_name": _first(entry.source_names),
        "source_url": safe_url(_first(entry.source_urls)),
    }


def _find_existing(session: Session, payload: IntelligenceIngestRequest, dedup_key: str, source_url: str) -> ThreatIntelligence | None:
    if payload.cve_id:
        existing = session.scalar(select(ThreatIntelligence).where(ThreatIntelligence.cve_id == payload.cve_id))
        if existing is not None:
            return existing
    conditions = [ThreatIntelligence.dedup_key == dedup_key]
    if payload.dedup_key:
        conditions.append(ThreatIntelligence.dedup_key == payload.dedup_key)
    if payload.external_id:
        conditions.append(
            ThreatIntelligence.source_links.any(
                and_(
                    ThreatIntelligenceSource.external_id == payload.external_id,
                    ThreatIntelligenceSource.source_url == source_url,
                )
            )
        )
    return session.scalar(select(ThreatIntelligence).where(or_(*conditions)))


def _merge_existing(
    entry: ThreatIntelligence,
    payload: IntelligenceIngestRequest,
    source_name: str,
    source_url: str,
    collected_at: datetime,
    content_hash: str,
    normalized_text_hash: str,
) -> None:
    entry.source_names = _unique([*(entry.source_names or []), source_name])
    entry.source_urls = _unique([*(entry.source_urls or []), source_url])
    entry.external_ids = _merge_dict(entry.external_ids or {}, _external_ids(payload))
    entry.tags = _unique([*(entry.tags or []), *_tags(payload)])
    entry.last_seen_at = max(_datetime_or_min(entry.last_seen_at), collected_at)
    entry.metadata_ = _merge_dict(entry.metadata_ or {}, _metadata(payload, actor_user_id=None))
    if not entry.summary and payload.summary:
        entry.summary = payload.summary
    if not entry.canonical_source_url:
        entry.canonical_source_url = source_url
    if not entry.affected_vendor and payload.affected_vendor:
        entry.affected_vendor = payload.affected_vendor
    if not entry.affected_product and payload.affected_products:
        entry.affected_product = _first(payload.affected_products)
    if not entry.normalized_text_hash:
        entry.normalized_text_hash = normalized_text_hash
    if _severity_rank(payload.severity) > _severity_rank(entry.severity):
        entry.severity = payload.severity
    if entry.risk_score is None and payload.external_score is not None:
        entry.risk_score = payload.external_score
    if entry.risk_level == RiskLevel.INFO and payload.severity is not Severity.UNKNOWN:
        entry.risk_level = _risk_level(payload.severity)
    entry.metadata_["last_ingest_content_hash"] = content_hash


def _upsert_source_link(
    session: Session,
    entry: ThreatIntelligence,
    raw_item: RawIntelligence | None,
    source_name: str,
    source_url: str,
    external_id: str | None,
) -> None:
    existing = next((link for link in (entry.source_links or []) if link.source_url == source_url), None)
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.source_name = source_name
        existing.external_id = external_id or existing.external_id
        existing.raw_intelligence_id = raw_item.id if raw_item is not None else existing.raw_intelligence_id
        existing.last_seen_at = now
        return
    link = ThreatIntelligenceSource(
        threat_intelligence_id=entry.id,
        raw_intelligence_id=raw_item.id if raw_item is not None else None,
        source_name=source_name,
        source_url=source_url,
        external_id=external_id,
        first_seen_at=now,
        last_seen_at=now,
    )
    session.add(link)


def _metadata(payload: IntelligenceIngestRequest, *, actor_user_id: Any) -> dict[str, Any]:
    metadata = {
        "entry_origin": "external_ingest",
        "platform": payload.platform,
        "cnvd_id": payload.cnvd_id,
        "vendor_advisory_id": payload.vendor_advisory_id,
        "affected_products": payload.affected_products,
        "components": payload.components,
        "attack_surfaces": payload.attack_surfaces,
        "published_at": payload.published_at.isoformat() if payload.published_at else None,
        "collected_at": payload.collected_at.isoformat() if payload.collected_at else None,
        "submitted_by_user_id": str(actor_user_id) if actor_user_id else None,
    }
    safe = safe_metadata({key: value for key, value in metadata.items() if value not in (None, [], {})})
    return safe if isinstance(safe, dict) else {}


def _safe_raw_payload(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value:
        return None
    safe = safe_metadata(value)
    return safe if isinstance(safe, dict) else None


def _external_ids(payload: IntelligenceIngestRequest) -> dict[str, Any]:
    values = {
        "external_id": payload.external_id,
        "cve_id": payload.cve_id,
        "cnvd_id": payload.cnvd_id,
        "vendor_advisory_id": payload.vendor_advisory_id,
        "dedup_key": payload.dedup_key,
        "content_hash": payload.content_hash,
    }
    safe = safe_metadata({key: value for key, value in values.items() if value})
    return safe if isinstance(safe, dict) else {}


def _dedup_key(payload: IntelligenceIngestRequest, source_name: str, source_url: str, content_hash: str, normalized_text_hash: str) -> str:
    if payload.cve_id:
        return f"cve:{payload.cve_id}"
    if payload.dedup_key:
        return f"external:{_stable_hash({'dedup_key': payload.dedup_key})[:48]}"
    if payload.external_id:
        return f"external:{_stable_hash({'source_name': source_name, 'external_id': payload.external_id})[:48]}"
    if payload.content_hash:
        return f"content:{payload.content_hash}"
    if source_url:
        return f"url:{_stable_hash({'url': source_url})[:48]}"
    return f"text:{normalized_text_hash or content_hash}"


def _normalized_payload(payload: IntelligenceIngestRequest, source_name: str, source_url: str) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "source_url": source_url,
        "platform": payload.platform,
        "title": payload.title,
        "summary": payload.summary,
        "description": payload.description,
        "external_id": payload.external_id,
        "cve_id": payload.cve_id,
        "cnvd_id": payload.cnvd_id,
        "vendor_advisory_id": payload.vendor_advisory_id,
        "affected_vendor": payload.affected_vendor,
        "affected_products": payload.affected_products,
        "components": payload.components,
        "attack_surfaces": payload.attack_surfaces,
        "severity": payload.severity.value,
        "published_at": payload.published_at,
    }


def _text_signature(payload: IntelligenceIngestRequest, source_name: str, source_url: str) -> dict[str, Any]:
    return {
        "title": _normalize_text(payload.title),
        "summary": _normalize_text(payload.summary),
        "source_name": _normalize_text(source_name),
        "source_url": source_url,
    }


def _source_name(payload: IntelligenceIngestRequest) -> str:
    return payload.source_name or payload.platform or "External Ingest"


def _canonical_url(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    url, _fragment = urldefrag(text)
    parsed = urlsplit(url)
    if parsed.scheme in {"http", "https"}:
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        cleaned = urlunsplit((scheme, netloc, path, parsed.query, ""))
        return safe_url(cleaned)
    return safe_text(text)


def _stable_hash(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _intelligence_type(payload: IntelligenceIngestRequest) -> IntelligenceType:
    if payload.cve_id:
        return IntelligenceType.VULNERABILITY
    if payload.attack_surfaces:
        return IntelligenceType.EXPOSURE
    return IntelligenceType.ADVISORY


def _cvss_score(payload: IntelligenceIngestRequest) -> float | None:
    if payload.external_score is None or payload.external_score > 10:
        return None
    return payload.external_score


def _risk_level(severity: Severity) -> RiskLevel:
    mapping = {
        Severity.CRITICAL: RiskLevel.CRITICAL,
        Severity.HIGH: RiskLevel.HIGH,
        Severity.MEDIUM: RiskLevel.MEDIUM,
        Severity.LOW: RiskLevel.LOW,
        Severity.UNKNOWN: RiskLevel.INFO,
    }
    return mapping[severity]


def _severity_rank(value: Severity | str | None) -> int:
    text = value.value if isinstance(value, Severity) else str(value or "unknown")
    return {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(text, 0)


def _tags(payload: IntelligenceIngestRequest) -> list[str]:
    tags = {"external_ingest", *(payload.tags or [])}
    if payload.platform:
        tags.add(payload.platform.strip().lower())
    if payload.components:
        tags.update(payload.components)
    if payload.attack_surfaces:
        tags.update(payload.attack_surfaces)
    return sorted(tag for tag in tags if tag)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def _merge_dict(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or merged[key] in (None, "", [], {}):
            merged[key] = value
    return merged


def _datetime_or_min(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    return value


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]
