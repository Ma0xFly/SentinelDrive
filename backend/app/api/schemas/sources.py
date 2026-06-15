from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.safety import looks_sensitive_value
from app.db.types import JobStatus, SourceStatus, SourceType


class SourceSort(str, Enum):
    NAME = "name"
    RECENT = "recent"
    FAILURES = "failures"


class JobLogSort(str, Enum):
    RECENT = "recent"
    STARTED = "started"


class SyncStateResponse(BaseModel):
    id: UUID
    status: JobStatus
    cursor: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    consecutive_failures: int
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SourceJobSummaryResponse(BaseModel):
    total: int
    success: int
    failed: int
    skipped: int
    retried: int
    items_seen: int
    items_created: int
    items_updated: int
    latest_job_id: UUID | None
    latest_job_status: JobStatus | None
    latest_run_status: str | None
    latest_started_at: datetime | None
    latest_finished_at: datetime | None
    latest_attempts: int | None
    latest_retried: bool
    latest_skipped: bool
    latest_metadata: dict[str, Any]


class SourceStatusResponse(BaseModel):
    id: UUID
    name: str
    source_type: SourceType
    status: SourceStatus
    enabled: bool
    base_url: str | None
    config: dict[str, Any]
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None
    failure_count: int
    sync_state: SyncStateResponse | None
    recent_jobs: SourceJobSummaryResponse
    created_at: datetime
    updated_at: datetime


class SourceStatusPageResponse(BaseModel):
    items: list[SourceStatusResponse]
    page: int
    limit: int
    total: int
    has_next: bool


class JobLogResponse(BaseModel):
    id: UUID
    job_name: str
    source_id: UUID | None
    source_name: str | None
    source_type: SourceType | None
    status: JobStatus
    run_status: str | None
    started_at: datetime | None
    finished_at: datetime | None
    items_seen: int
    items_created: int
    items_updated: int
    error_message: str | None
    attempts: int | None
    retried: bool
    skipped: bool
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class JobLogPageResponse(BaseModel):
    items: list[JobLogResponse]
    page: int
    limit: int
    total: int
    has_next: bool


class PipelineTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalization_limit: int | None = Field(default=None, ge=1, le=500)
    scoring_limit: int | None = Field(default=None, ge=1, le=500)
    alert_limit: int | None = Field(default=None, ge=1, le=500)


class PipelineTriggerResponse(BaseModel):
    job_id: UUID
    celery_task_id: str
    task_name: str
    status: str
    message: str


class PipelineJobResponse(BaseModel):
    id: UUID
    job_name: str
    source_id: UUID | None
    source_name: str | None
    source_type: SourceType | None
    status: JobStatus
    run_status: str | None
    celery_task_id: str | None
    celery_status: str | None
    started_at: datetime | None
    finished_at: datetime | None
    items_seen: int
    items_created: int
    items_updated: int
    error_message: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class PipelineFailureResponse(BaseModel):
    category: str
    id: UUID
    source_id: UUID | None
    source_name: str | None
    source_url: str | None
    status: str
    stage: str | None
    error_message: str | None
    occurred_at: datetime | None
    metadata: dict[str, Any]


class PipelineStatusResponse(BaseModel):
    pending_raw_rows: int
    failed_raw_rows: int
    scoring_pending_intelligence_rows: int
    open_alerts: int
    latest_pipeline_job: PipelineJobResponse | None
    latest_source_job: PipelineJobResponse | None
    recent_failures: list[PipelineFailureResponse]


class SourceStatusUpdateRequest(BaseModel):
    status: SourceStatus
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if looks_sensitive_value(stripped):
                raise ValueError("reason must not include unredacted credentials")
            return stripped or None
        return value
