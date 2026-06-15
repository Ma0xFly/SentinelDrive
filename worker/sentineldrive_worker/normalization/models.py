from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


class NormalizationError(Exception):
    """Raised when a raw record cannot be normalized."""


@dataclass(frozen=True)
class SourceAttribution:
    source_id: object | None
    raw_intelligence_id: object | None
    source_name: str
    source_url: str
    external_id: str | None
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class NormalizedRecord:
    title: str
    summary: str | None
    intelligence_type: str
    dedup_key: str
    source_names: list[str]
    source_urls: list[str]
    canonical_source_url: str | None
    external_ids: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    normalized_text_hash: str
    raw_intelligence_id: object | None = None
    cve_id: str | None = None
    cwe_id: str | None = None
    cvss_score: float | None = None
    cvss_vector: str | None = None
    severity: str = "unknown"
    affected_vendor: str | None = None
    affected_product: str | None = None
    affected_version: str | None = None
    vehicle_component: str | None = None
    attack_surface: str | None = None
    exploit_status: str = "unknown"
    confidence: str = "medium"
    risk_score: float | None = None
    risk_level: str = "info"
    tags: list[str] = field(default_factory=list)
    processing_status: str = "normalized"
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)
    attribution: SourceAttribution | None = None


Normalizer = Any
RawRecord = Mapping[str, Any]
