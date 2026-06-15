from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import Select, insert, select, update
from sqlalchemy.orm import Session

from sentineldrive_worker.normalization.models import NormalizedRecord
from sentineldrive_worker.normalization.normalizers import register_builtin_normalizers
from sentineldrive_worker.normalization.registry import NormalizerRegistry, registry
from sentineldrive_worker.persistence.database import create_engine_from_url, create_session_factory
from sentineldrive_worker.persistence.tables import raw_intelligence, threat_intelligence, threat_intelligence_sources


@dataclass
class NormalizationService:
    session_factory: Callable[[], Session]
    normalizer_registry: NormalizerRegistry = registry

    def normalize_pending(self, *, limit: int = 100) -> dict[str, Any]:
        register_builtin_normalizers(self.normalizer_registry)
        with self.session_factory() as session:
            rows = list(session.execute(pending_raw_query(limit)).mappings().all())

        records: list[dict[str, Any]] = []
        for row in rows:
            with self.session_factory() as session:
                try:
                    records.append(self.normalize_raw_row(session, row))
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    records.append(self.mark_failed(session, row, exc))

        return {
            "status": "completed",
            "raw_seen": len(rows),
            "normalized": sum(1 for record in records if record["status"] == "normalized"),
            "failed": sum(1 for record in records if record["status"] == "failed"),
            "records": records,
        }

    def normalize_raw_row(self, session: Session, row: dict[str, Any]) -> dict[str, Any]:
        session.execute(
            update(raw_intelligence)
            .where(raw_intelligence.c.id == row["id"])
            .values(processing_status="processing", updated_at=datetime.now(timezone.utc))
        )
        raw_row = dict(row)
        raw_row["processing_status"] = "processing"
        normalizer = self.normalizer_registry.resolve(raw_row)
        normalized = normalizer.normalize(raw_row)
        intelligence_id, action = upsert_normalized_record(session, normalized)
        upsert_source_attribution(session, intelligence_id, normalized)
        session.execute(
            update(raw_intelligence)
            .where(raw_intelligence.c.id == row["id"])
            .values(
                processing_status="normalized",
                parsing_status="normalized",
                error_message=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return {
            "raw_intelligence_id": str(row["id"]),
            "threat_intelligence_id": str(intelligence_id),
            "status": "normalized",
            "action": action,
            "dedup_key": normalized.dedup_key,
        }

    def mark_failed(self, session: Session, row: dict[str, Any], error: BaseException) -> dict[str, Any]:
        message = sanitize_error(error)
        try:
            session.execute(
                update(raw_intelligence)
                .where(raw_intelligence.c.id == row["id"])
                .values(
                    processing_status="failed",
                    parsing_status="failed",
                    error_message=message,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            session.commit()
        except Exception:
            session.rollback()
        return {
            "raw_intelligence_id": str(row["id"]),
            "status": "failed",
            "error_message": message,
        }


def normalize_pending_raw_intelligence(
    *,
    limit: int = 100,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
    normalizer_registry: NormalizerRegistry = registry,
) -> dict[str, Any]:
    factory = session_factory
    if factory is None:
        engine = create_engine_from_url(database_url)
        factory = create_session_factory(engine)
    return NormalizationService(factory, normalizer_registry=normalizer_registry).normalize_pending(limit=limit)


def pending_raw_query(limit: int) -> Select:
    return (
        select(raw_intelligence)
        .where(raw_intelligence.c.processing_status.in_(("pending", "collected")))
        .order_by(raw_intelligence.c.first_seen_at.asc(), raw_intelligence.c.created_at.asc())
        .limit(limit)
    )


def upsert_normalized_record(session: Session, incoming: NormalizedRecord) -> tuple[object, str]:
    existing = session.execute(select(threat_intelligence).where(threat_intelligence.c.dedup_key == incoming.dedup_key)).mappings().first()
    now = datetime.now(timezone.utc)
    if existing is None:
        intelligence_id = uuid4()
        values = normalized_insert_values(incoming, intelligence_id, now)
        session.execute(insert(threat_intelligence).values(**values))
        return intelligence_id, "created"

    intelligence_id = existing["id"]
    merged = merge_normalized(existing, incoming, now)
    session.execute(update(threat_intelligence).where(threat_intelligence.c.id == intelligence_id).values(**merged))
    return intelligence_id, "updated"


def normalized_insert_values(incoming: NormalizedRecord, intelligence_id: object, now: datetime) -> dict[str, Any]:
    values = normalized_common_values(incoming)
    values.update(
        {
            "id": intelligence_id,
            "raw_intelligence_id": incoming.raw_intelligence_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    return values


def normalized_common_values(incoming: NormalizedRecord) -> dict[str, Any]:
    return {
        "title": incoming.title,
        "summary": incoming.summary,
        "intelligence_type": incoming.intelligence_type,
        "source_names": unique_values(incoming.source_names),
        "source_urls": unique_values(incoming.source_urls),
        "canonical_source_url": incoming.canonical_source_url,
        "external_ids": dict(incoming.external_ids),
        "cve_id": incoming.cve_id,
        "cwe_id": incoming.cwe_id,
        "cvss_score": incoming.cvss_score,
        "cvss_vector": incoming.cvss_vector,
        "severity": incoming.severity,
        "affected_vendor": incoming.affected_vendor,
        "affected_product": incoming.affected_product,
        "affected_version": incoming.affected_version,
        "vehicle_component": incoming.vehicle_component,
        "attack_surface": incoming.attack_surface,
        "exploit_status": incoming.exploit_status,
        "confidence": incoming.confidence,
        "risk_score": incoming.risk_score,
        "risk_level": incoming.risk_level,
        "tags": unique_values(incoming.tags),
        "first_seen_at": incoming.first_seen_at,
        "last_seen_at": incoming.last_seen_at,
        "dedup_key": incoming.dedup_key,
        "normalized_text_hash": incoming.normalized_text_hash,
        "processing_status": incoming.processing_status,
        "status": incoming.status,
        "metadata": dict(incoming.metadata),
    }


def merge_normalized(existing: dict[str, Any], incoming: NormalizedRecord, now: datetime) -> dict[str, Any]:
    values: dict[str, Any] = {
        "source_names": unique_values([*(existing.get("source_names") or []), *incoming.source_names]),
        "source_urls": unique_values([*(existing.get("source_urls") or []), *incoming.source_urls]),
        "external_ids": merge_external_ids(existing.get("external_ids") or {}, incoming.external_ids),
        "tags": unique_values([*(existing.get("tags") or []), *incoming.tags]),
        "first_seen_at": min_datetime(existing.get("first_seen_at"), incoming.first_seen_at),
        "last_seen_at": max_datetime(existing.get("last_seen_at"), incoming.last_seen_at),
        "metadata": merge_metadata(existing.get("metadata") or {}, incoming.metadata),
        "updated_at": now,
    }
    conservative_fields = (
        "summary",
        "canonical_source_url",
        "cve_id",
        "cwe_id",
        "cvss_score",
        "cvss_vector",
        "affected_vendor",
        "affected_product",
        "affected_version",
        "vehicle_component",
        "attack_surface",
        "risk_score",
        "normalized_text_hash",
    )
    incoming_values = normalized_common_values(incoming)
    for field in conservative_fields:
        if is_empty(existing.get(field)) and not is_empty(incoming_values.get(field)):
            values[field] = incoming_values[field]
    if stronger_severity(incoming.severity, existing.get("severity")):
        values["severity"] = incoming.severity
    if stronger_exploit_status(incoming.exploit_status, existing.get("exploit_status")):
        values["exploit_status"] = incoming.exploit_status
    if stronger_confidence(incoming.confidence, existing.get("confidence")):
        values["confidence"] = incoming.confidence
    if existing.get("title") in {None, "", existing.get("cve_id")} and incoming.title:
        values["title"] = incoming.title
    return values


def upsert_source_attribution(session: Session, intelligence_id: object, incoming: NormalizedRecord) -> None:
    if incoming.attribution is None:
        return
    attribution = incoming.attribution
    existing = session.execute(
        select(threat_intelligence_sources).where(
            threat_intelligence_sources.c.threat_intelligence_id == intelligence_id,
            threat_intelligence_sources.c.source_url == attribution.source_url,
        )
    ).mappings().first()
    now = datetime.now(timezone.utc)
    values = {
        "source_id": attribution.source_id,
        "raw_intelligence_id": attribution.raw_intelligence_id,
        "source_name": attribution.source_name,
        "source_url": attribution.source_url,
        "external_id": attribution.external_id,
        "last_seen_at": attribution.last_seen_at,
        "updated_at": now,
    }
    if existing:
        values["first_seen_at"] = min_datetime(existing.get("first_seen_at"), attribution.first_seen_at)
        session.execute(update(threat_intelligence_sources).where(threat_intelligence_sources.c.id == existing["id"]).values(**values))
        return
    values.update(
        {
            "id": uuid4(),
            "threat_intelligence_id": intelligence_id,
            "first_seen_at": attribution.first_seen_at,
            "created_at": now,
        }
    )
    session.execute(insert(threat_intelligence_sources).values(**values))


def unique_values(values: Iterable[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value is None or value == "":
            continue
        if value not in result:
            result.append(value)
    return result


def merge_external_ids(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if key not in merged or is_empty(merged[key]):
            merged[key] = value
        elif merged[key] != value:
            current = merged[key] if isinstance(merged[key], list) else [merged[key]]
            merged[key] = unique_values([*current, value])
    return merged


def merge_metadata(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    normalizers = unique_values([*(merged.get("normalizers") or []), incoming.get("normalizer")])
    if normalizers:
        merged["normalizers"] = normalizers
    sightings = list(merged.get("sightings") or [])
    sightings.append({key: value for key, value in incoming.items() if key in {"normalizer", "raw_source_type", "vendor", "feed_name", "date_added"}})
    merged["sightings"] = sightings[-20:]
    for key, value in incoming.items():
        if key not in merged and not is_empty(value):
            merged[key] = value
    return merged


def min_datetime(first: datetime | None, second: datetime | None) -> datetime:
    values = [value for value in (first, second) if isinstance(value, datetime)]
    return min(values) if values else datetime.now(timezone.utc)


def max_datetime(first: datetime | None, second: datetime | None) -> datetime:
    values = [value for value in (first, second) if isinstance(value, datetime)]
    return max(values) if values else datetime.now(timezone.utc)


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def stronger_severity(incoming: str, existing: str | None) -> bool:
    order = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
    return order.get(incoming or "unknown", 0) > order.get(existing or "unknown", 0)


def stronger_exploit_status(incoming: str, existing: str | None) -> bool:
    order = {"unknown": 0, "none_known": 1, "proof_of_concept": 2, "exploited": 3}
    return order.get(incoming or "unknown", 0) > order.get(existing or "unknown", 0)


def stronger_confidence(incoming: str, existing: str | None) -> bool:
    order = {"low": 1, "medium": 2, "high": 3}
    return order.get(incoming or "medium", 2) > order.get(existing or "medium", 2)


def sanitize_error(error: BaseException) -> str:
    text = str(error) or error.__class__.__name__
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*[^&\s]+",
        "[redacted]=[redacted]",
        text,
    )
    text = re.sub(r"(?i)api[_-]?key|authorization|password|secret|token", "[redacted]", text)
    return text[:500]
