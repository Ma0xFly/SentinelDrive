from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class StatsTotalsResponse(BaseModel):
    total_intelligence: int
    new_last_24_hours: int
    new_last_7_days: int


class StatsTrendPointResponse(BaseModel):
    date: date
    count: int


class StatsAlertsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    trend: list[StatsTrendPointResponse]


class StatsSourceTopResponse(BaseModel):
    id: UUID
    name: str
    intelligence_count: int


class StatsSourcesResponse(BaseModel):
    enabled: int
    top: list[StatsSourceTopResponse]


class StatsOverviewResponse(BaseModel):
    totals: StatsTotalsResponse
    by_intelligence_type: dict[str, int]
    by_severity: dict[str, int]
    by_risk_level: dict[str, int]
    by_processing_status: dict[str, int]
    trend: list[StatsTrendPointResponse]
    alerts: StatsAlertsResponse
    sources: StatsSourcesResponse
