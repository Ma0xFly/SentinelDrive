from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, and_, insert, or_, select, update
from sqlalchemy.orm import Session

from sentineldrive_worker.connectors.config import load_source_configs
from sentineldrive_worker.connectors.contracts import SourceConfig, SourceType, enum_value
from sentineldrive_worker.connectors.registry import ConnectorRegistry, registry
from sentineldrive_worker.connectors.runtime import RuntimeState, run_enabled_sources
from sentineldrive_worker.persistence.database import create_engine_from_url, create_session_factory
from sentineldrive_worker.persistence.tables import job_logs, raw_intelligence, sources, sync_states

SYNC_JOB_NAME = "sentineldrive.sync_sources"
MAX_RAW_CONTENT_BYTES = 256_000


class CollectionPersistenceService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def persist_runs(self, source_configs: Iterable[SourceConfig], run_result: dict[str, Any]) -> dict[str, Any]:
        configs_by_name = {source.name: source for source in source_configs}
        persisted_records: list[dict[str, Any]] = []

        for record in run_result.get("records", []):
            source_name = record["source_name"]
            source = configs_by_name[source_name]
            with self._session_factory() as session:
                try:
                    persisted_records.append(self.persist_source_run(session, source, record))
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    persisted_records.append(
                        {
                            "source_name": source.name,
                            "source_id": None,
                            "job_log_id": None,
                            "status": "persistence_failed",
                            "items_seen": int(record.get("items_seen", 0)),
                            "items_created": 0,
                            "items_updated": 0,
                            "error_message": str(exc)[:500],
                        }
                    )

        return {
            **run_result,
            "persisted": {
                "sources": len(persisted_records),
                "raw_created": sum(item["items_created"] for item in persisted_records),
                "raw_updated": sum(item["items_updated"] for item in persisted_records),
                "failed": sum(1 for item in persisted_records if item["status"] == "persistence_failed"),
                "records": persisted_records,
            },
        }

    def persist_source_run(self, session: Session, source: SourceConfig, record: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        source_id = ensure_source(session, source, record, now)
        ensure_sync_state(session, source_id, now)

        items_created = 0
        items_updated = 0
        if record["status"] == "success":
            for raw_item in record.get("raw_items", []):
                result = upsert_raw_record(session, source_id, source, raw_item, now)
                if result == "created":
                    items_created += 1
                else:
                    items_updated += 1

        update_source_status(session, source_id, record, now)
        update_sync_state(session, source_id, record, now)
        job_log_id = insert_job_log(session, source_id, record, items_created, items_updated, now)

        return {
            "source_name": source.name,
            "source_id": str(source_id),
            "job_log_id": str(job_log_id),
            "status": record["status"],
            "items_seen": int(record.get("items_seen", 0)),
            "items_created": items_created,
            "items_updated": items_updated,
        }


def run_and_persist_enabled_sources(
    *,
    source_configs: Iterable[SourceConfig] | None = None,
    connector_registry: ConnectorRegistry = registry,
    state: RuntimeState | None = None,
    sleeper=None,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    configs = list(source_configs or load_source_configs())
    runtime_kwargs: dict[str, Any] = {
        "source_configs": configs,
        "connector_registry": connector_registry,
        "state": state,
    }
    if sleeper is not None:
        runtime_kwargs["sleeper"] = sleeper

    run_result = run_enabled_sources(**runtime_kwargs)
    factory = session_factory
    if factory is None:
        engine = create_engine_from_url(database_url)
        factory = create_session_factory(engine)

    return CollectionPersistenceService(factory).persist_runs(configs, run_result)


def persistence_enabled() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def ensure_source(session: Session, source: SourceConfig, record: dict[str, Any], now: datetime) -> UUID:
    existing = session.execute(select(sources).where(sources.c.name == source.name)).mappings().first()
    source_status = "disabled" if record["status"] == "skipped" and record.get("metadata", {}).get("reason") == "disabled" else "enabled"
    if record["status"] == "failed":
        source_status = "error"

    if existing:
        source_id = existing["id"]
        session.execute(
            update(sources)
            .where(sources.c.id == source_id)
            .values(
                source_type=enum_value(source.source_type),
                base_url=source.base_url,
                status=source_status,
                config=source_metadata(source),
                updated_at=now,
            )
        )
        return source_id

    source_id = uuid4()
    session.execute(
        insert(sources).values(
            id=source_id,
            name=source.name,
            source_type=enum_value(source.source_type),
            base_url=source.base_url,
            status=source_status,
            config=source_metadata(source),
            created_at=now,
            updated_at=now,
        )
    )
    return source_id


def ensure_sync_state(session: Session, source_id: UUID, now: datetime) -> None:
    existing = session.execute(select(sync_states.c.id).where(sync_states.c.source_id == source_id)).scalar_one_or_none()
    if existing:
        return
    session.execute(
        insert(sync_states).values(
            id=uuid4(),
            source_id=source_id,
            cursor=None,
            status="queued",
            consecutive_failures=0,
            metadata={},
            created_at=now,
            updated_at=now,
        )
    )


def upsert_raw_record(session: Session, source_id: UUID, source: SourceConfig, raw_item: dict[str, Any], now: datetime) -> str:
    retained_item = apply_retention_policy(raw_item, source.source_type)
    existing = find_existing_raw_record(session, source_id, retained_item)
    values = raw_record_values(source_id, retained_item, now)

    if existing:
        session.execute(update(raw_intelligence).where(raw_intelligence.c.id == existing["id"]).values(**values))
        return "updated"

    session.execute(insert(raw_intelligence).values(id=uuid4(), created_at=now, **values))
    return "created"


def find_existing_raw_record(session: Session, source_id: UUID, raw_item: dict[str, Any]) -> dict[str, Any] | None:
    conditions = [raw_intelligence.c.raw_hash == raw_item["raw_hash"]]
    external_id = raw_item.get("external_id")
    if external_id:
        conditions.append(and_(raw_intelligence.c.source_id == source_id, raw_intelligence.c.external_id == external_id))
    query: Select = select(raw_intelligence.c.id).where(or_(*conditions))
    return session.execute(query).mappings().first()


def raw_record_values(source_id: UUID, raw_item: dict[str, Any], now: datetime) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_name": raw_item["source_name"],
        "source_type": raw_item["source_type"],
        "source_url": raw_item["source_url"],
        "external_id": raw_item.get("external_id"),
        "fetched_at": parse_datetime(raw_item["fetched_at"]),
        "first_seen_at": parse_datetime(raw_item["first_seen_at"]),
        "title": raw_item.get("title"),
        "summary": raw_item.get("summary"),
        "snippet": raw_item.get("snippet"),
        "raw_content": raw_item.get("raw_content"),
        "raw_hash": raw_item["raw_hash"],
        "content_hash": raw_item.get("content_hash"),
        "parsing_status": raw_item.get("parsing_status", "pending"),
        "processing_status": raw_item.get("processing_status", "collected"),
        "error_message": raw_item.get("error_message"),
        "metadata": raw_item.get("metadata") or {},
        "retained_payload_mode": raw_item.get("retained_payload_mode", "metadata_only"),
        "updated_at": now,
    }


def update_source_status(session: Session, source_id: UUID, record: dict[str, Any], now: datetime) -> None:
    values: dict[str, Any] = {"updated_at": now}
    if record["status"] == "success":
        values.update(status="enabled", last_success_at=parse_datetime(record["finished_at"]), last_error_message=None)
    elif record["status"] == "failed":
        values.update(
            status="error",
            last_error_at=parse_datetime(record["finished_at"]),
            last_error_message=record.get("error_message"),
        )
    elif record.get("metadata", {}).get("reason") == "disabled":
        values.update(status="disabled")
    session.execute(update(sources).where(sources.c.id == source_id).values(**values))


def update_sync_state(session: Session, source_id: UUID, record: dict[str, Any], now: datetime) -> None:
    existing = session.execute(select(sync_states).where(sync_states.c.source_id == source_id)).mappings().one()
    status = "success"
    consecutive_failures = int(existing["consecutive_failures"] or 0)
    cursor = existing["cursor"]

    if record["status"] == "success":
        consecutive_failures = 0
        if record.get("next_cursor") is not None:
            cursor = record["next_cursor"]
    elif record["status"] == "failed":
        status = "failed"
        consecutive_failures += 1

    session.execute(
        update(sync_states)
        .where(sync_states.c.source_id == source_id)
        .values(
            cursor=cursor,
            status=status,
            last_run_at=parse_datetime(record["finished_at"]),
            next_run_at=parse_optional_datetime(record.get("next_run_at")),
            consecutive_failures=consecutive_failures,
            metadata=sync_metadata(record),
            updated_at=now,
        )
    )


def insert_job_log(
    session: Session,
    source_id: UUID,
    record: dict[str, Any],
    items_created: int,
    items_updated: int,
    now: datetime,
) -> UUID:
    job_log_id = uuid4()
    status = "failed" if record["status"] == "failed" else "success"
    session.execute(
        insert(job_logs).values(
            id=job_log_id,
            job_name=SYNC_JOB_NAME,
            source_id=source_id,
            status=status,
            started_at=parse_datetime(record["started_at"]),
            finished_at=parse_datetime(record["finished_at"]),
            items_seen=int(record.get("items_seen", 0)),
            items_created=items_created,
            items_updated=items_updated,
            error_message=record.get("error_message"),
            metadata=job_metadata(record),
            created_at=now,
            updated_at=now,
        )
    )
    return job_log_id


def apply_retention_policy(raw_item: dict[str, Any], source_type: SourceType | str) -> dict[str, Any]:
    retained = dict(raw_item)
    normalized_type = enum_value(source_type)
    if normalized_type in {SourceType.HTML.value, SourceType.PDF.value}:
        retained["raw_content"] = None
        retained["retained_payload_mode"] = "metadata_only"
        metadata = dict(retained.get("metadata") or {})
        metadata["retention_enforced"] = "metadata_only"
        retained["metadata"] = metadata
        return retained

    raw_content = retained.get("raw_content")
    if raw_content is not None and len(str(raw_content).encode("utf-8")) > MAX_RAW_CONTENT_BYTES:
        retained["raw_content"] = None
        retained["retained_payload_mode"] = "metadata_only"
        metadata = dict(retained.get("metadata") or {})
        metadata["retention_enforced"] = "raw_content_too_large"
        retained["metadata"] = metadata
    return retained


def source_metadata(source: SourceConfig) -> dict[str, Any]:
    return {
        "sync_interval_seconds": source.sync_interval_seconds,
        "timeout_seconds": source.timeout_seconds,
        "rate_limit_per_minute": source.rate_limit_per_minute,
        "retry_attempts": source.retry_policy.attempts,
        "retry_backoff_seconds": source.retry_policy.backoff_seconds,
        "retry_max_backoff_seconds": source.retry_policy.max_backoff_seconds,
        "metadata": dict(source.metadata),
    }


def job_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(record.get("metadata") or {})
    metadata.update(
        {
            "run_status": record["status"],
            "attempts": int(record.get("attempts", 0)),
            "next_cursor": record.get("next_cursor"),
        }
    )
    if record["status"] == "skipped":
        metadata["skipped"] = True
    if int(record.get("attempts", 0)) > 1:
        metadata["retried"] = True
    return metadata


def sync_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "last_run_status": record["status"],
        "attempts": int(record.get("attempts", 0)),
        "items_seen": int(record.get("items_seen", 0)),
        "error_message": record.get("error_message"),
        "metadata": dict(record.get("metadata") or {}),
    }


def parse_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return parse_datetime(value)


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise TypeError(f"expected datetime or ISO timestamp, got {type(value).__name__}")
