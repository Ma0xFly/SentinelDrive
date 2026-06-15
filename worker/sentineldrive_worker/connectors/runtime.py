from __future__ import annotations

import concurrent.futures
import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sentineldrive_worker.connectors.config import load_source_configs
from sentineldrive_worker.connectors.contracts import (
    Connector,
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    RawIntelligencePayload,
    SourceConfig,
)
from sentineldrive_worker.connectors.registry import ConnectorRegistry, registry
from sentineldrive_worker.connectors.samples import register_builtin_connectors


class ConnectorTimeoutError(ConnectorError):
    pass


@dataclass
class RuntimeState:
    cursors: dict[str, str | None] = field(default_factory=dict)
    next_allowed_at: dict[str, float] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    last_success_at: dict[str, datetime] = field(default_factory=dict)

    def record_success(self, source: SourceConfig, cursor: str | None) -> None:
        self.cursors[source.name] = cursor
        self.errors.pop(source.name, None)
        self.last_success_at[source.name] = datetime.now(timezone.utc)

    def record_error(self, source: SourceConfig, error: BaseException) -> None:
        self.errors[source.name] = sanitize_error(error)


@dataclass(frozen=True)
class SourceRunRecord:
    source_name: str
    status: str
    items_seen: int = 0
    next_cursor: str | None = None
    attempts: int = 0
    error_message: str | None = None
    raw_items: tuple[dict[str, Any], ...] = ()
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    next_run_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def run_enabled_sources(
    *,
    source_configs: Iterable[SourceConfig] | None = None,
    connector_registry: ConnectorRegistry = registry,
    state: RuntimeState | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    register_builtin_connectors(connector_registry)
    runtime_state = state or RuntimeState()
    configs = list(source_configs or load_source_configs())
    records: list[SourceRunRecord] = []

    for source in configs:
        if not source.enabled:
            records.append(
                SourceRunRecord(
                    source_name=source.name,
                    status="skipped",
                    next_run_at=next_run_time(source),
                    metadata={"reason": "disabled"},
                )
            )
            continue

        connector_key = str(source.metadata.get("connector", source.name))
        if not connector_registry.has(connector_key):
            records.append(
                SourceRunRecord(
                    source_name=source.name,
                    status="skipped",
                    next_run_at=next_run_time(source),
                    metadata={"reason": "connector_not_registered", "connector": connector_key},
                )
            )
            continue

        try:
            connector = connector_registry.create(connector_key, source)
            records.append(run_connector(connector, state=runtime_state, sleeper=sleeper))
        except Exception as exc:
            runtime_state.record_error(source, exc)
            records.append(
                SourceRunRecord(
                    source_name=source.name,
                    status="failed",
                    error_message=sanitize_error(exc),
                    next_run_at=next_run_time(source),
                )
            )

    return {
        "status": "completed",
        "sources_seen": len(records),
        "sources_succeeded": sum(1 for record in records if record.status == "success"),
        "sources_failed": sum(1 for record in records if record.status == "failed"),
        "sources_skipped": sum(1 for record in records if record.status == "skipped"),
        "items_seen": sum(record.items_seen for record in records),
        "records": [record_to_dict(record) for record in records],
    }


def run_connector(
    connector: Connector,
    *,
    state: RuntimeState | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> SourceRunRecord:
    runtime_state = state or RuntimeState()
    source = connector.source
    started_at = datetime.now(timezone.utc)
    attempts_made = 0
    last_error: BaseException | None = None

    wait_for_rate_limit(source, runtime_state, sleeper=sleeper)
    max_attempts = source.retry_policy.attempts + 1
    cursor = runtime_state.cursors.get(source.name, source.cursor)

    for attempt in range(1, max_attempts + 1):
        attempts_made = attempt
        runtime_state.attempts[source.name] = attempt
        try:
            context = ConnectorContext(source=source, cursor=cursor, started_at=started_at)
            result = run_with_timeout(lambda: connector.collect(context), timeout_seconds=source.timeout_seconds)
            runtime_state.record_success(source, result.next_cursor)
            set_next_rate_limit(source, runtime_state)
            finished_at = datetime.now(timezone.utc)
            return SourceRunRecord(
                source_name=source.name,
                status="success",
                items_seen=len(result.items),
                next_cursor=result.next_cursor,
                attempts=attempts_made,
                raw_items=tuple(json_ready(item.to_raw_record()) for item in result.items),
                started_at=started_at,
                finished_at=finished_at,
                next_run_at=next_run_time(source, finished_at),
                metadata=dict(result.metadata),
            )
        except Exception as exc:
            last_error = exc
            runtime_state.record_error(source, exc)
            if attempt >= max_attempts:
                break
            backoff = min(
                source.retry_policy.backoff_seconds * (2 ** (attempt - 1)),
                source.retry_policy.max_backoff_seconds,
            )
            if backoff > 0:
                sleeper(backoff)

    set_next_rate_limit(source, runtime_state)
    finished_at = datetime.now(timezone.utc)
    return SourceRunRecord(
        source_name=source.name,
        status="failed",
        attempts=attempts_made,
        error_message=sanitize_error(last_error) if last_error else "unknown connector failure",
        started_at=started_at,
        finished_at=finished_at,
        next_run_at=next_run_time(source, finished_at),
    )


def run_with_timeout(callable_: Callable[[], ConnectorResult], *, timeout_seconds: float) -> ConnectorResult:
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(callable_)
    try:
        result = future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise ConnectorTimeoutError(f"connector timed out after {timeout_seconds:g}s") from exc
    else:
        executor.shutdown(wait=True)
        return result


def wait_for_rate_limit(source: SourceConfig, state: RuntimeState, *, sleeper: Callable[[float], None]) -> None:
    wait_seconds = state.next_allowed_at.get(source.name, 0) - time.monotonic()
    if wait_seconds > 0:
        sleeper(wait_seconds)


def set_next_rate_limit(source: SourceConfig, state: RuntimeState) -> None:
    interval = 60.0 / source.rate_limit_per_minute
    state.next_allowed_at[source.name] = time.monotonic() + interval


def next_run_time(source: SourceConfig, base_time: datetime | None = None) -> datetime:
    return (base_time or datetime.now(timezone.utc)) + timedelta(seconds=source.sync_interval_seconds)


def sanitize_error(error: BaseException | None) -> str:
    if error is None:
        return "unknown error"
    text = str(error) or error.__class__.__name__
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*\S+",
        "[redacted]=[redacted]",
        text,
    )
    text = re.sub(r"(?i)api[_-]?key|authorization|password|secret|token", "[redacted]", text)
    return text[:500]


def record_to_dict(record: SourceRunRecord) -> dict[str, Any]:
    return {
        "source_name": record.source_name,
        "status": record.status,
        "items_seen": record.items_seen,
        "next_cursor": record.next_cursor,
        "attempts": record.attempts,
        "error_message": record.error_message,
        "raw_items": list(record.raw_items),
        "started_at": record.started_at.isoformat(),
        "finished_at": record.finished_at.isoformat(),
        "next_run_at": record.next_run_at.isoformat() if record.next_run_at else None,
        "metadata": record.metadata,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def assert_json_serializable(value: Any) -> None:
    json.dumps(value)
