import json
import re
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.api.safety import looks_sensitive_value
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

CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)


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


class IntelligenceIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str = Field(min_length=1, max_length=160)
    source_url: str = Field(min_length=1, max_length=1000)
    platform: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=3, max_length=500)
    summary: str = Field(min_length=1, max_length=4000)
    description: str | None = Field(default=None, max_length=12000)
    external_id: str | None = Field(default=None, max_length=240)
    cve_id: str | None = Field(default=None, max_length=32)
    cnvd_id: str | None = Field(default=None, max_length=80)
    vendor_advisory_id: str | None = Field(default=None, max_length=120)
    affected_vendor: str | None = Field(default=None, max_length=160)
    affected_products: list[str] = Field(default_factory=list, max_length=50)
    components: list[str] = Field(default_factory=list, max_length=50)
    attack_surfaces: list[str] = Field(default_factory=list, max_length=50)
    severity: Severity = Severity.UNKNOWN
    external_score: float | None = Field(default=None, ge=0, le=100)
    published_at: datetime | None = None
    collected_at: datetime | None = None
    dedup_key: str | None = Field(default=None, max_length=320)
    content_hash: str | None = Field(default=None, max_length=128)
    raw_payload: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)

    @field_validator(
        "source_name",
        "source_url",
        "platform",
        "title",
        "summary",
        "description",
        "external_id",
        "cnvd_id",
        "vendor_advisory_id",
        "affected_vendor",
        "dedup_key",
        "content_hash",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator(
        "title",
        "summary",
        "description",
        "source_name",
        "platform",
        "external_id",
        "cnvd_id",
        "vendor_advisory_id",
        "affected_vendor",
        "dedup_key",
        "content_hash",
    )
    @classmethod
    def reject_obvious_secret_text(cls, value: str | None) -> str | None:
        if value and looks_sensitive_value(value):
            raise ValueError("ingest text must not include unredacted credentials")
        return value

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        if " " in value or "://" not in value:
            raise ValueError("source_url must be an absolute URL")
        return value

    @field_validator("cve_id")
    @classmethod
    def normalize_cve_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cve_id = value.strip().upper()
        if not CVE_PATTERN.fullmatch(cve_id):
            raise ValueError("cve_id must match CVE-YYYY-NNNN format")
        return cve_id

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            aliases = {
                "严重": "critical",
                "高危": "high",
                "中危": "medium",
                "低危": "low",
                "信息": "unknown",
                "info": "unknown",
            }
            return aliases.get(normalized, normalized)
        return value

    @field_validator("affected_products", "components", "attack_surfaces", "tags")
    @classmethod
    def normalize_text_list(cls, value: list[str]) -> list[str]:
        normalized: set[str] = set()
        for item in value:
            clean = item.strip().lower()
            if not clean:
                continue
            if len(clean) > 120:
                raise ValueError("list values must be 120 characters or shorter")
            if looks_sensitive_value(clean):
                raise ValueError("list values must not include unredacted credentials")
            normalized.add(clean)
        return sorted(normalized)

    @field_validator("raw_payload")
    @classmethod
    def limit_raw_payload_size(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return None
        if len(json.dumps(value, sort_keys=True, default=str)) > 32768:
            raise ValueError("raw_payload must be 32 KB or smaller")
        return value

    @model_validator(mode="after")
    def source_identity_required(self) -> "IntelligenceIngestRequest":
        if not self.source_name and not self.platform:
            raise ValueError("source_name or platform is required")
        return self


class IntelligenceIngestResponse(BaseModel):
    id: UUID
    raw_intelligence_id: UUID | None
    status: str
    duplicate: bool
    dedup_key: str
    title: str
    cve_id: str | None
    source_name: str
    source_url: str
    message: str
