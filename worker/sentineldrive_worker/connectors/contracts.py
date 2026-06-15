from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ConnectorError(Exception):
    """Raised when a connector cannot complete a collection attempt."""


class RuntimeEnum(str, Enum):
    pass


class SourceType(RuntimeEnum):
    API = "api"
    RSS = "rss"
    HTML = "html"
    PDF = "pdf"
    MANUAL = "manual"
    VENDOR = "vendor"


class ProcessingStatus(RuntimeEnum):
    PENDING = "pending"
    COLLECTED = "collected"
    PROCESSING = "processing"
    NORMALIZED = "normalized"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    backoff_seconds: float = 1.0
    max_backoff_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.attempts < 0:
            raise ValueError("retry attempts must be zero or greater")
        if self.backoff_seconds < 0:
            raise ValueError("retry backoff must be zero or greater")
        if self.max_backoff_seconds < self.backoff_seconds:
            raise ValueError("max retry backoff must be greater than or equal to backoff")


@dataclass(frozen=True)
class SourceConfig:
    name: str
    source_type: SourceType
    enabled: bool = True
    base_url: str | None = None
    sync_interval_seconds: int = 3600
    timeout_seconds: float = 20.0
    rate_limit_per_minute: int = 20
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    cursor: str | None = None
    credentials: Mapping[str, str] = field(default_factory=dict)
    headers: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("source name is required")
        if self.sync_interval_seconds <= 0:
            raise ValueError("sync interval must be greater than zero")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout must be greater than zero")
        if self.rate_limit_per_minute <= 0:
            raise ValueError("rate limit must be greater than zero")


@dataclass(frozen=True)
class ConnectorContext:
    source: SourceConfig
    cursor: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class RawIntelligencePayload:
    source_name: str
    source_type: SourceType | str
    source_url: str
    fetched_at: datetime
    first_seen_at: datetime
    raw_hash: str
    external_id: str | None = None
    title: str | None = None
    summary: str | None = None
    snippet: str | None = None
    raw_content: Mapping[str, Any] | None = None
    content_hash: str | None = None
    parsing_status: ProcessingStatus | str = ProcessingStatus.PENDING
    processing_status: ProcessingStatus | str = ProcessingStatus.COLLECTED
    error_message: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    retained_payload_mode: str = "metadata_only"

    @classmethod
    def from_source(
        cls,
        source: SourceConfig,
        *,
        source_url: str | None = None,
        external_id: str | None = None,
        title: str | None = None,
        summary: str | None = None,
        snippet: str | None = None,
        raw_content: Mapping[str, Any] | None = None,
        fetched_at: datetime | None = None,
        first_seen_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
        retained_payload_mode: str | None = None,
        parsing_status: ProcessingStatus | str = ProcessingStatus.PENDING,
    ) -> "RawIntelligencePayload":
        now = datetime.now(timezone.utc)
        fetched = fetched_at or now
        first_seen = first_seen_at or fetched
        resolved_url = source_url or source.base_url or f"sentineldrive://source/{source.name}"
        payload_metadata = dict(metadata or {})
        content_hash = stable_hash(
            {
                "source_url": resolved_url,
                "external_id": external_id,
                "title": title,
                "summary": summary,
                "snippet": snippet,
                "raw_content": raw_content,
            }
        )
        raw_hash = stable_hash(
            {
                "source_name": source.name,
                "source_type": source.source_type.value,
                "source_url": resolved_url,
                "external_id": external_id,
                "content_hash": content_hash,
            }
        )
        return cls(
            source_name=source.name,
            source_type=source.source_type,
            source_url=resolved_url,
            fetched_at=fetched,
            first_seen_at=first_seen,
            external_id=external_id,
            title=title,
            summary=summary,
            snippet=snippet,
            raw_content=raw_content,
            raw_hash=raw_hash,
            content_hash=content_hash,
            parsing_status=parsing_status,
            metadata=payload_metadata,
            retained_payload_mode=retained_payload_mode or default_retention_mode(source.source_type),
        )

    def to_raw_record(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_type": enum_value(self.source_type),
            "source_url": self.source_url,
            "external_id": self.external_id,
            "fetched_at": self.fetched_at,
            "first_seen_at": self.first_seen_at,
            "title": self.title,
            "summary": self.summary,
            "snippet": self.snippet,
            "raw_content": dict(self.raw_content) if self.raw_content is not None else None,
            "raw_hash": self.raw_hash,
            "content_hash": self.content_hash,
            "parsing_status": enum_value(self.parsing_status),
            "processing_status": enum_value(self.processing_status),
            "error_message": self.error_message,
            "metadata": dict(self.metadata),
            "retained_payload_mode": self.retained_payload_mode,
        }


@dataclass(frozen=True)
class ConnectorResult:
    items: Sequence[RawIntelligencePayload] = field(default_factory=tuple)
    next_cursor: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class Connector(Protocol):
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        """Collect source data and return Raw Intelligence-shaped payloads."""


def stable_hash(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(value, default=_json_default, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def default_retention_mode(source_type: SourceType | str) -> str:
    if enum_value(source_type) in {SourceType.API.value, SourceType.RSS.value}:
        return "raw_payload"
    return "metadata_only"


def enum_value(value: RuntimeEnum | str) -> str:
    return value.value if isinstance(value, RuntimeEnum) else value


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, RuntimeEnum):
        return value.value
    return str(value)
