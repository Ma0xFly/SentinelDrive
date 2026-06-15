from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.api.safety import looks_sensitive_value
from app.api.schemas.intelligence import SourceAttributionResponse
from app.db.types import AlertStatus, AttackSurface, IntelligenceType, RiskLevel, Severity, VehicleComponent


class AlertSort(str, Enum):
    RECENT = "recent"
    RISK_LEVEL = "risk_level"


class AlertIntelligenceSummaryResponse(BaseModel):
    id: UUID
    title: str
    summary: str | None
    intelligence_type: IntelligenceType
    cve_id: str | None
    severity: Severity
    affected_vendor: str | None
    affected_product: str | None
    vehicle_component: VehicleComponent | None
    attack_surface: AttackSurface | None
    risk_score: float | None
    risk_level: RiskLevel
    status: str
    source_names: list[str]
    source_urls: list[str]
    first_seen_at: datetime
    last_seen_at: datetime
    sources: list[SourceAttributionResponse]


class AlertResponse(BaseModel):
    id: UUID
    title: str
    threat_intelligence_id: UUID
    triggering_rule: str
    risk_level: RiskLevel
    triggered_at: datetime
    status: AlertStatus
    notes: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class AlertDetailResponse(AlertResponse):
    intelligence: AlertIntelligenceSummaryResponse | None


class AlertPageResponse(BaseModel):
    items: list[AlertResponse]
    page: int
    limit: int
    total: int
    has_next: bool


class AlertStatusUpdateRequest(BaseModel):
    status: AlertStatus
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes", mode="before")
    @classmethod
    def strip_notes(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if looks_sensitive_value(stripped):
                raise ValueError("notes must not include unredacted credentials")
            return stripped or None
        return value


class AlertGenerationRequest(BaseModel):
    intelligence_id: UUID | None = None
    limit: int = Field(default=100, ge=1, le=500)


class AlertGenerationResponse(BaseModel):
    created: int
    alert_ids: list[UUID]
