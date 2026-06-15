from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.types import (
    AlertStatus,
    AttackSurface,
    ConfidenceLevel,
    ExploitStatus,
    IntelligenceType,
    RiskLevel,
    Severity,
    VehicleComponent,
)


class IntelligenceSort(str, Enum):
    RECENT = "recent"
    FIRST_SEEN = "first_seen"
    RISK_SCORE = "risk_score"
    SEVERITY = "severity"


class SourceAttributionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID | None
    source_id: UUID | None
    raw_intelligence_id: UUID | None
    source_name: str
    source_url: str
    external_id: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None


class RelatedAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    risk_level: RiskLevel
    status: AlertStatus
    triggered_at: datetime


class IntelligenceResponseBase(BaseModel):
    id: UUID
    title: str
    summary: str | None
    intelligence_type: IntelligenceType
    source_names: list[str]
    source_urls: list[str]
    canonical_source_url: str | None
    cve_id: str | None
    cwe_id: str | None
    cvss_score: float | None
    cvss_vector: str | None
    severity: Severity
    affected_vendor: str | None
    affected_product: str | None
    affected_version: str | None
    vehicle_component: VehicleComponent | None
    attack_surface: AttackSurface | None
    exploit_status: ExploitStatus
    confidence: ConfidenceLevel
    risk_score: float | None
    risk_level: RiskLevel
    status: str
    tags: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any]
    score_metadata: dict[str, Any]
    score_explanation: str | None
    sources: list[SourceAttributionResponse]
    related_alert_count: int


class IntelligenceListItemResponse(IntelligenceResponseBase):
    pass


class IntelligenceDetailResponse(IntelligenceResponseBase):
    raw_intelligence_id: UUID | None
    external_ids: dict[str, Any]
    dedup_key: str
    normalized_text_hash: str | None
    related_alerts: list[RelatedAlertResponse]


class IntelligencePageResponse(BaseModel):
    items: list[IntelligenceListItemResponse]
    page: int
    limit: int
    total: int
    has_next: bool
