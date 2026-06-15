import re
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.types import (
    AttackSurface,
    ConfidenceLevel,
    ExploitStatus,
    IntelligenceType,
    RiskLevel,
    Severity,
    VehicleComponent,
)

CVE_PATTERN = re.compile(r"^CVE-\d{4}-\d{4,}$", re.IGNORECASE)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"\b(password|token|secret|api[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def _strip_optional_text(value: object) -> object:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _reject_obvious_secret_value(value: str | None) -> str | None:
    if value and SENSITIVE_ASSIGNMENT_PATTERN.search(value):
        raise ValueError("manual entry text must not include unredacted credentials")
    return value


def _validate_source_url_value(value: str | None) -> str | None:
    if value is None:
        return None
    if " " in value or "://" not in value:
        raise ValueError("source_url must be an absolute URL")
    return value


def _normalize_cve_id_value(value: str | None) -> str | None:
    if value is None:
        return None
    cve_id = value.strip().upper()
    if not CVE_PATTERN.fullmatch(cve_id):
        raise ValueError("cve_id must match CVE-YYYY-NNNN format")
    return cve_id


def _normalize_cwe_id_value(value: str | None) -> str | None:
    return value.upper() if value else value


def _normalize_tag_values(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    normalized: set[str] = set()
    for tag in value:
        clean = tag.strip().lower()
        if not clean:
            continue
        if len(clean) > 80:
            raise ValueError("tags must be 80 characters or shorter")
        if SENSITIVE_ASSIGNMENT_PATTERN.search(clean):
            raise ValueError("tags must not include unredacted credentials")
        normalized.add(clean)
    return sorted(normalized)


class ManualEntryCategory(str, Enum):
    VULNERABILITY = "vulnerability"
    ADVISORY = "advisory"
    INCIDENT = "incident"
    EXPOSURE = "exposure"
    RESEARCH_LEAD = "research_lead"


class ManualEntryStatus(str, Enum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ManualEntryCreateRequest(BaseModel):
    category: ManualEntryCategory
    title: str = Field(min_length=3, max_length=500)
    summary: str = Field(min_length=1)
    source_name: str | None = Field(default=None, max_length=160)
    source_url: str | None = Field(default=None, max_length=1000)
    cve_id: str | None = Field(default=None, max_length=32)
    cwe_id: str | None = Field(default=None, max_length=32)
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    cvss_vector: str | None = Field(default=None, max_length=160)
    severity: Severity = Severity.UNKNOWN
    affected_vendor: str | None = Field(default=None, max_length=160)
    affected_product: str | None = Field(default=None, max_length=200)
    affected_version: str | None = Field(default=None, max_length=200)
    vehicle_component: VehicleComponent | None = None
    attack_surface: AttackSurface | None = None
    exploit_status: ExploitStatus = ExploitStatus.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    risk_score: float | None = Field(default=None, ge=0, le=100)
    risk_level: RiskLevel = RiskLevel.INFO
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: ManualEntryStatus | None = None

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: object) -> object:
        aliases = {
            "vulnerabilities": "vulnerability",
            "advisories": "advisory",
            "incidents": "incident",
            "exposures": "exposure",
            "research leads": "research_lead",
            "research-leads": "research_lead",
            "research_leads": "research_lead",
        }
        if isinstance(value, str):
            normalized = value.strip().lower()
            return aliases.get(normalized, normalized)
        return value

    @field_validator(
        "title",
        "summary",
        "source_name",
        "source_url",
        "cwe_id",
        "cvss_vector",
        "affected_vendor",
        "affected_product",
        "affected_version",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("title", "summary", "source_name", "source_url")
    @classmethod
    def reject_obvious_secrets(cls, value: str | None) -> str | None:
        return _reject_obvious_secret_value(value)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        return _validate_source_url_value(value)

    @field_validator("cve_id")
    @classmethod
    def normalize_cve_id(cls, value: str | None) -> str | None:
        return _normalize_cve_id_value(value)

    @field_validator("cwe_id")
    @classmethod
    def normalize_cwe_id(cls, value: str | None) -> str | None:
        return _normalize_cwe_id_value(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return _normalize_tag_values(value) or []

    @model_validator(mode="after")
    def source_attribution_required(self) -> "ManualEntryCreateRequest":
        if not self.source_name and not self.source_url:
            raise ValueError("source_name or source_url is required")
        return self


class ManualEntryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=500)
    summary: str | None = Field(default=None, min_length=1)
    source_name: str | None = Field(default=None, max_length=160)
    source_url: str | None = Field(default=None, max_length=1000)
    cve_id: str | None = Field(default=None, max_length=32)
    cwe_id: str | None = Field(default=None, max_length=32)
    cvss_score: float | None = Field(default=None, ge=0, le=10)
    cvss_vector: str | None = Field(default=None, max_length=160)
    severity: Severity | None = None
    affected_vendor: str | None = Field(default=None, max_length=160)
    affected_product: str | None = Field(default=None, max_length=200)
    affected_version: str | None = Field(default=None, max_length=200)
    vehicle_component: VehicleComponent | None = None
    attack_surface: AttackSurface | None = None
    exploit_status: ExploitStatus | None = None
    confidence: ConfidenceLevel | None = None
    risk_score: float | None = Field(default=None, ge=0, le=100)
    risk_level: RiskLevel | None = None
    tags: list[str] | None = Field(default=None, max_length=20)
    status: ManualEntryStatus | None = None

    @field_validator(
        "title",
        "summary",
        "source_name",
        "source_url",
        "cwe_id",
        "cvss_vector",
        "affected_vendor",
        "affected_product",
        "affected_version",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return _strip_optional_text(value)

    @field_validator("title", "summary", "source_name", "source_url")
    @classmethod
    def reject_obvious_secrets(cls, value: str | None) -> str | None:
        return _reject_obvious_secret_value(value)

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str | None) -> str | None:
        return _validate_source_url_value(value)

    @field_validator("cve_id")
    @classmethod
    def normalize_cve_id(cls, value: str | None) -> str | None:
        return _normalize_cve_id_value(value)

    @field_validator("cwe_id")
    @classmethod
    def normalize_cwe_id(cls, value: str | None) -> str | None:
        return _normalize_cwe_id_value(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        return _normalize_tag_values(value)

    @model_validator(mode="after")
    def at_least_one_field_required(self) -> "ManualEntryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self


class ManualEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_intelligence_id: UUID | None
    category: ManualEntryCategory
    intelligence_type: IntelligenceType
    title: str
    summary: str | None
    source_name: str
    source_url: str
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
    dedup_key: str
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime
