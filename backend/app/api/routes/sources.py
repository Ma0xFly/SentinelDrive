from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_optional_current_user, get_pipeline_task_client, get_request_session
from app.api.safety import safe_metadata, safe_text, safe_url
from app.api.schemas.sources import (
    JobLogPageResponse,
    JobLogResponse,
    JobLogSort,
    PipelineFailureResponse,
    PipelineJobResponse,
    PipelineStatusResponse,
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    SourceJobSummaryResponse,
    SourcePublicPageResponse,
    SourcePublicResponse,
    SourceSort,
    SourceStatusPageResponse,
    SourceStatusResponse,
    SourceStatusUpdateRequest,
    SyncStateResponse,
)
from app.db.types import AlertStatus, AuditAction, JobStatus, ProcessingStatus, RiskLevel, SourceStatus, SourceType
from app.models.intelligence import RawIntelligence, ThreatIntelligence
from app.models.job import JobLog
from app.models.security import Alert, User
from app.models.source import Source, SyncState
from app.services.audit import record_audit_event
from app.services.pipeline import PROCESS_PIPELINE_TASK, EnqueuedPipelineTask, PipelineTaskClient

router = APIRouter(prefix="/sources", tags=["sources"])

DEFAULT_PIPELINE_LIMIT = 100
RECENT_FAILURE_LIMIT = 5


@dataclass(frozen=True)
class SourceSearchParams:
    status: SourceStatus | None = None
    source_type: SourceType | None = None
    q: str | None = None
    sort: SourceSort = SourceSort.NAME


@dataclass(frozen=True)
class JobSearchParams:
    source_id: UUID | None = None
    status: JobStatus | None = None
    job_name: str | None = None
    run_status: str | None = None
    retried: bool | None = None
    skipped: bool | None = None
    sort: JobLogSort = JobLogSort.RECENT


@router.get("", response_model=SourceStatusPageResponse | SourcePublicPageResponse)
async def list_sources(
    status_filter: SourceStatus | None = Query(default=None, alias="status"),
    source_type: SourceType | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    sort: SourceSort = SourceSort.NAME,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User | None = Depends(get_optional_current_user),
    session: Session = Depends(get_request_session),
) -> SourceStatusPageResponse | SourcePublicPageResponse:
    authenticated = current_user is not None
    if not authenticated:
        sort = SourceSort.NAME
    params = SourceSearchParams(status=status_filter, source_type=source_type, q=_clean(q), sort=sort)
    statement = _source_statement(params)
    offset = (page - 1) * limit
    if isinstance(session, Session):
        total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        sources = list(session.scalars(statement.offset(offset).limit(limit)).all())
        if not authenticated:
            return SourcePublicPageResponse(
                items=[_source_public_response(source) for source in sources],
                page=page,
                limit=limit,
                total=total,
                has_next=offset + limit < total,
            )
        jobs_by_source = _jobs_by_source(session, [source.id for source in sources])
    else:
        all_sources = list(session.scalars(statement).all())
        filtered = [source for source in all_sources if _matches_source(source, params)]
        if not authenticated:
            sorted_sources = sorted(filtered, key=lambda source: source.name.lower())
            total = len(sorted_sources)
            sources = sorted_sources[offset : offset + limit]
            return SourcePublicPageResponse(
                items=[_source_public_response(source) for source in sources],
                page=page,
                limit=limit,
                total=total,
                has_next=offset + limit < total,
            )
        sorted_sources = _sort_sources(filtered, params.sort, _all_jobs(session))
        total = len(sorted_sources)
        sources = sorted_sources[offset : offset + limit]
        jobs_by_source = _group_jobs(_all_jobs(session), [source.id for source in sources])
    return SourceStatusPageResponse(
        items=[_source_response(source, jobs_by_source.get(source.id, [])) for source in sources],
        page=page,
        limit=limit,
        total=total,
        has_next=offset + limit < total,
    )


@router.get("/jobs", response_model=JobLogPageResponse)
async def list_job_logs(
    source_id: UUID | None = Query(default=None),
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    job_name: str | None = Query(default=None, min_length=1, max_length=160),
    run_status: str | None = Query(default=None, min_length=1, max_length=40),
    retried: bool | None = Query(default=None),
    skipped: bool | None = Query(default=None),
    sort: JobLogSort = JobLogSort.RECENT,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> JobLogPageResponse:
    del current_user
    params = JobSearchParams(
        source_id=source_id,
        status=status_filter,
        job_name=_clean(job_name),
        run_status=_clean(run_status),
        retried=retried,
        skipped=skipped,
        sort=sort,
    )
    statement = _job_statement(params)
    offset = (page - 1) * limit
    if isinstance(session, Session):
        total = session.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        jobs = list(session.scalars(statement.offset(offset).limit(limit)).all())
        sources_by_id = _sources_by_id(session, [job.source_id for job in jobs if job.source_id])
    else:
        all_jobs = list(session.scalars(statement).all())
        filtered = [job for job in all_jobs if _matches_job(job, params)]
        sorted_jobs = _sort_jobs(filtered, params.sort)
        total = len(sorted_jobs)
        jobs = sorted_jobs[offset : offset + limit]
        sources_by_id = {source.id: source for source in _all_sources(session)}
    return JobLogPageResponse(
        items=[_job_response(job, sources_by_id.get(job.source_id)) for job in jobs],
        page=page,
        limit=limit,
        total=total,
        has_next=offset + limit < total,
    )


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
    pipeline_client: PipelineTaskClient = Depends(get_pipeline_task_client),
) -> PipelineStatusResponse:
    del current_user
    return PipelineStatusResponse(
        pending_raw_rows=_pending_raw_count(session),
        failed_raw_rows=_failed_raw_count(session),
        scoring_pending_intelligence_rows=_scoring_pending_count(session),
        open_alerts=_open_alert_count(session),
        latest_pipeline_job=_latest_pipeline_job_response(session, pipeline_client),
        latest_source_job=_latest_source_job_response(session),
        recent_failures=_recent_failures(session),
    )


@router.post("/pipeline/trigger", response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    payload: PipelineTriggerRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
    pipeline_client: PipelineTaskClient = Depends(get_pipeline_task_client),
) -> PipelineTriggerResponse:
    limits = _pipeline_limits(payload)
    enqueued = pipeline_client.enqueue_process_pipeline(**limits)
    job = JobLog(
        job_name=PROCESS_PIPELINE_TASK,
        source_id=None,
        status=JobStatus.QUEUED,
        started_at=None,
        finished_at=None,
        items_seen=0,
        items_created=0,
        items_updated=0,
        error_message=None,
        metadata_={
            "run_status": "queued",
            "celery_task_id": enqueued.task_id,
            "celery_status": enqueued.status,
            **limits,
        },
    )
    session.add(job)
    session.flush()
    record_audit_event(
        session,
        action=AuditAction.STATUS_CHANGE,
        entity_type="pipeline",
        summary="Processing pipeline triggered",
        actor_user_id=current_user.id,
        entity_id=job.id,
        after={
            "job_name": PROCESS_PIPELINE_TASK,
            "celery_task_id": enqueued.task_id,
            "limits": limits,
        },
        metadata={"task_name": PROCESS_PIPELINE_TASK},
    )
    session.commit()
    session.refresh(job)
    return PipelineTriggerResponse(
        job_id=job.id,
        celery_task_id=enqueued.task_id,
        task_name=PROCESS_PIPELINE_TASK,
        status=_pipeline_response_status(enqueued),
        message="处理流水线已加入队列。",
    )


@router.get("/{source_id}", response_model=SourceStatusResponse | SourcePublicResponse)
async def get_source(
    source_id: UUID,
    current_user: User | None = Depends(get_optional_current_user),
    session: Session = Depends(get_request_session),
) -> SourceStatusResponse | SourcePublicResponse:
    source = _get_source_or_404(session, source_id)
    if current_user is None:
        return _source_public_response(source)
    jobs = _jobs_for_source(session, source.id)
    return _source_response(source, jobs)


@router.patch("/{source_id}/status", response_model=SourceStatusResponse)
async def update_source_status(
    source_id: UUID,
    payload: SourceStatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> SourceStatusResponse:
    source = _get_source_or_404(session, source_id)
    before = _source_audit_snapshot(source)
    source.status = payload.status
    if payload.status != SourceStatus.ERROR:
        source.last_error_message = None
    source.updated_at = datetime.now(timezone.utc)
    after = _source_audit_snapshot(source)
    record_audit_event(
        session,
        action=AuditAction.STATUS_CHANGE,
        entity_type="source",
        summary="Source status updated",
        actor_user_id=current_user.id,
        entity_id=source.id,
        before=before,
        after=after,
        metadata={"reason": safe_text(payload.reason), "source_name": source.name},
    )
    session.commit()
    session.refresh(source)
    return _source_response(source, _jobs_for_source(session, source.id))


def _source_statement(params: SourceSearchParams) -> Select:
    statement = select(Source).options(selectinload(Source.sync_state))
    conditions = []
    if params.status:
        conditions.append(Source.status == params.status)
    if params.source_type:
        conditions.append(Source.source_type == params.source_type)
    if params.q:
        pattern = _like_pattern(params.q)
        conditions.append(Source.name.ilike(pattern))
    if conditions:
        statement = statement.where(*conditions)
    return statement.order_by(*_source_order_by(params.sort))


def _job_statement(params: JobSearchParams) -> Select:
    statement = select(JobLog)
    conditions = []
    if params.source_id:
        conditions.append(JobLog.source_id == params.source_id)
    if params.status:
        conditions.append(JobLog.status == params.status)
    if params.job_name:
        conditions.append(JobLog.job_name.ilike(_like_pattern(params.job_name)))
    if params.run_status:
        conditions.append(JobLog.metadata_["run_status"].as_string() == params.run_status)
    if params.retried is not None:
        conditions.append(_retried_condition(params.retried))
    if params.skipped is not None:
        conditions.append(_skipped_condition(params.skipped))
    if conditions:
        statement = statement.where(*conditions)
    return statement.order_by(*_job_order_by(params.sort))


def _source_order_by(sort: SourceSort):
    if sort is SourceSort.RECENT:
        return (Source.updated_at.desc(), Source.name.asc(), Source.id.asc())
    if sort is SourceSort.FAILURES:
        return (Source.last_error_at.desc().nullslast(), Source.updated_at.desc(), Source.name.asc(), Source.id.asc())
    return (Source.name.asc(), Source.id.asc())


def _job_order_by(sort: JobLogSort):
    if sort is JobLogSort.STARTED:
        return (JobLog.started_at.desc().nullslast(), JobLog.id.asc())
    return (JobLog.finished_at.desc().nullslast(), JobLog.started_at.desc().nullslast(), JobLog.id.asc())


def _retried_condition(expected: bool):
    retried_flag = JobLog.metadata_["retried"].as_boolean()
    attempts = JobLog.metadata_["attempts"].as_integer()
    derived_retried = or_(retried_flag.is_(True), attempts > 1)
    if expected:
        return derived_retried
    return and_(retried_flag.is_not(True), or_(attempts.is_(None), attempts <= 1))


def _skipped_condition(expected: bool):
    skipped_flag = JobLog.metadata_["skipped"].as_boolean()
    run_status = JobLog.metadata_["run_status"].as_string()
    derived_skipped = or_(skipped_flag.is_(True), run_status == "skipped")
    if expected:
        return derived_skipped
    return and_(skipped_flag.is_not(True), or_(run_status.is_(None), run_status != "skipped"))


def _get_source_or_404(session: Session, source_id: UUID) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "source_not_found", "message": "来源不存在。"}},
        )
    return source


def _source_public_response(source: Source) -> SourcePublicResponse:
    return SourcePublicResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        status=source.status,
        enabled=source.status == SourceStatus.ENABLED,
        base_url=safe_url(source.base_url),
    )


def _source_response(source: Source, jobs: list[JobLog]) -> SourceStatusResponse:
    return SourceStatusResponse(
        id=source.id,
        name=source.name,
        source_type=source.source_type,
        status=source.status,
        enabled=source.status == SourceStatus.ENABLED,
        base_url=safe_url(source.base_url),
        config=safe_metadata(source.config or {}),
        last_success_at=source.last_success_at,
        last_error_at=source.last_error_at,
        last_error_message=safe_text(source.last_error_message),
        failure_count=_failure_count(source, jobs),
        sync_state=_sync_state_response(source.sync_state),
        recent_jobs=_job_summary(jobs),
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def _sync_state_response(sync_state: SyncState | None) -> SyncStateResponse | None:
    if sync_state is None:
        return None
    return SyncStateResponse(
        id=sync_state.id,
        status=sync_state.status,
        cursor=safe_text(sync_state.cursor),
        last_run_at=sync_state.last_run_at,
        next_run_at=sync_state.next_run_at,
        consecutive_failures=sync_state.consecutive_failures,
        metadata=safe_metadata(sync_state.metadata_ or {}),
        created_at=sync_state.created_at,
        updated_at=sync_state.updated_at,
    )


def _job_summary(jobs: list[JobLog]) -> SourceJobSummaryResponse:
    sorted_jobs = _sort_jobs(jobs, JobLogSort.RECENT)
    latest = sorted_jobs[0] if sorted_jobs else None
    latest_metadata = _safe_job_metadata(latest) if latest else {}
    return SourceJobSummaryResponse(
        total=len(jobs),
        success=sum(1 for job in jobs if _enum_value(job.status) == JobStatus.SUCCESS.value),
        failed=sum(1 for job in jobs if _enum_value(job.status) == JobStatus.FAILED.value),
        skipped=sum(1 for job in jobs if _is_skipped(job)),
        retried=sum(1 for job in jobs if _is_retried(job)),
        items_seen=sum(job.items_seen or 0 for job in jobs),
        items_created=sum(job.items_created or 0 for job in jobs),
        items_updated=sum(job.items_updated or 0 for job in jobs),
        latest_job_id=latest.id if latest else None,
        latest_job_status=latest.status if latest else None,
        latest_run_status=_run_status(latest) if latest else None,
        latest_started_at=latest.started_at if latest else None,
        latest_finished_at=latest.finished_at if latest else None,
        latest_attempts=_attempts(latest) if latest else None,
        latest_retried=_is_retried(latest) if latest else False,
        latest_skipped=_is_skipped(latest) if latest else False,
        latest_metadata=latest_metadata,
    )


def _job_response(job: JobLog, source: Source | None) -> JobLogResponse:
    return JobLogResponse(
        id=job.id,
        job_name=job.job_name,
        source_id=job.source_id,
        source_name=source.name if source else None,
        source_type=source.source_type if source else None,
        status=job.status,
        run_status=_run_status(job),
        started_at=job.started_at,
        finished_at=job.finished_at,
        items_seen=job.items_seen,
        items_created=job.items_created,
        items_updated=job.items_updated,
        error_message=safe_text(job.error_message),
        attempts=_attempts(job),
        retried=_is_retried(job),
        skipped=_is_skipped(job),
        metadata=_safe_job_metadata(job),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _pipeline_job_response(job: JobLog, source: Source | None, *, celery_status: str | None = None) -> PipelineJobResponse:
    metadata = _safe_job_metadata(job)
    return PipelineJobResponse(
        id=job.id,
        job_name=job.job_name,
        source_id=job.source_id,
        source_name=source.name if source else None,
        source_type=source.source_type if source else None,
        status=job.status,
        run_status=_run_status(job),
        celery_task_id=_metadata_text(metadata, "celery_task_id"),
        celery_status=celery_status or _metadata_text(metadata, "celery_status"),
        started_at=job.started_at,
        finished_at=job.finished_at,
        items_seen=job.items_seen,
        items_created=job.items_created,
        items_updated=job.items_updated,
        error_message=safe_text(job.error_message),
        metadata=metadata,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _latest_pipeline_job_response(session: Session, pipeline_client: PipelineTaskClient) -> PipelineJobResponse | None:
    job = _latest_pipeline_job(session)
    if job is None:
        return None
    metadata = _safe_job_metadata(job)
    celery_status = _metadata_text(metadata, "celery_status")
    task_id = _metadata_text(metadata, "celery_task_id")
    if task_id:
        try:
            celery_status = pipeline_client.task_status(task_id) or celery_status
        except Exception:
            pass
    return _pipeline_job_response(job, None, celery_status=celery_status)


def _latest_source_job_response(session: Session) -> PipelineJobResponse | None:
    job = _latest_source_job(session)
    if job is None:
        return None
    source = _sources_by_id(session, [job.source_id]).get(job.source_id) if job.source_id else None
    return _pipeline_job_response(job, source)


def _jobs_by_source(session: Session, source_ids: list[UUID]) -> dict[UUID, list[JobLog]]:
    if not source_ids:
        return {}
    jobs = list(
        session.scalars(
            select(JobLog).where(JobLog.source_id.in_(source_ids)).order_by(JobLog.finished_at.desc().nullslast(), JobLog.id.asc())
        ).all()
    )
    return _group_jobs(jobs, source_ids)


def _jobs_for_source(session: Session, source_id: UUID) -> list[JobLog]:
    jobs = list(
        session.scalars(
            select(JobLog).where(JobLog.source_id == source_id).order_by(JobLog.finished_at.desc().nullslast(), JobLog.id.asc())
        ).all()
    )
    return jobs


def _sources_by_id(session: Session, source_ids: list[UUID]) -> dict[UUID, Source]:
    if not source_ids:
        return {}
    return {source.id: source for source in session.scalars(select(Source).where(Source.id.in_(source_ids))).all()}


def _group_jobs(jobs: list[JobLog], source_ids: list[UUID]) -> dict[UUID, list[JobLog]]:
    grouped: dict[UUID, list[JobLog]] = {source_id: [] for source_id in source_ids}
    for job in jobs:
        if job.source_id in grouped:
            grouped[job.source_id].append(job)
    return grouped


def _matches_source(source: Source, params: SourceSearchParams) -> bool:
    if params.status and _enum_value(source.status) != params.status.value:
        return False
    if params.source_type and _enum_value(source.source_type) != params.source_type.value:
        return False
    if params.q and params.q.lower() not in source.name.lower():
        return False
    return True


def _matches_job(job: JobLog, params: JobSearchParams) -> bool:
    if params.source_id and job.source_id != params.source_id:
        return False
    if params.status and _enum_value(job.status) != params.status.value:
        return False
    if params.job_name and params.job_name.lower() not in job.job_name.lower():
        return False
    if params.run_status and _normalize(_run_status(job)) != _normalize(params.run_status):
        return False
    if params.retried is not None and _is_retried(job) is not params.retried:
        return False
    if params.skipped is not None and _is_skipped(job) is not params.skipped:
        return False
    return True


def _sort_sources(sources: list[Source], sort: SourceSort, jobs: list[JobLog]) -> list[Source]:
    grouped = _group_jobs(jobs, [source.id for source in sources])
    sorted_sources = sorted(sources, key=lambda source: str(source.id))
    if sort is SourceSort.RECENT:
        sorted_sources.sort(key=lambda source: _datetime_key(source.updated_at), reverse=True)
    elif sort is SourceSort.FAILURES:
        sorted_sources.sort(
            key=lambda source: (
                _failure_count(source, grouped.get(source.id, [])),
                _datetime_key(source.last_error_at),
                _datetime_key(source.updated_at),
            ),
            reverse=True,
        )
    else:
        sorted_sources.sort(key=lambda source: source.name.lower())
    return sorted_sources


def _sort_jobs(jobs: list[JobLog], sort: JobLogSort) -> list[JobLog]:
    sorted_jobs = sorted(jobs, key=lambda job: str(job.id))
    if sort is JobLogSort.STARTED:
        sorted_jobs.sort(key=lambda job: _datetime_key(job.started_at), reverse=True)
    else:
        sorted_jobs.sort(key=lambda job: (_datetime_key(job.finished_at), _datetime_key(job.started_at)), reverse=True)
    return sorted_jobs


def _failure_count(source: Source, jobs: list[JobLog]) -> int:
    sync_state = source.sync_state
    if sync_state is not None:
        return int(sync_state.consecutive_failures or 0)
    return sum(1 for job in jobs if _enum_value(job.status) == JobStatus.FAILED.value)


def _pipeline_limits(payload: PipelineTriggerRequest) -> dict[str, int]:
    return {
        "normalization_limit": payload.normalization_limit or DEFAULT_PIPELINE_LIMIT,
        "scoring_limit": payload.scoring_limit or DEFAULT_PIPELINE_LIMIT,
        "alert_limit": payload.alert_limit or DEFAULT_PIPELINE_LIMIT,
    }


def _pipeline_response_status(enqueued: EnqueuedPipelineTask) -> str:
    status_value = enqueued.status.strip().lower()
    return status_value or JobStatus.QUEUED.value


def _pending_raw_count(session: Session) -> int:
    if isinstance(session, Session):
        return _count(
            session,
            select(func.count()).select_from(RawIntelligence).where(
                RawIntelligence.processing_status.in_((ProcessingStatus.PENDING, ProcessingStatus.COLLECTED))
            ),
        )
    return sum(
        1
        for row in _all_raw_intelligence(session)
        if _enum_value(row.processing_status) in {ProcessingStatus.PENDING.value, ProcessingStatus.COLLECTED.value}
    )


def _failed_raw_count(session: Session) -> int:
    if isinstance(session, Session):
        return _count(
            session,
            select(func.count()).select_from(RawIntelligence).where(RawIntelligence.processing_status == ProcessingStatus.FAILED),
        )
    return sum(1 for row in _all_raw_intelligence(session) if _enum_value(row.processing_status) == ProcessingStatus.FAILED.value)


def _scoring_pending_count(session: Session) -> int:
    if isinstance(session, Session):
        return _count(
            session,
            select(func.count())
            .select_from(ThreatIntelligence)
            .where(
                ThreatIntelligence.processing_status == ProcessingStatus.NORMALIZED,
                or_(ThreatIntelligence.risk_score.is_(None), ThreatIntelligence.risk_level == RiskLevel.INFO),
            ),
        )
    return sum(1 for row in _all_intelligence(session) if _is_scoring_pending(row))


def _open_alert_count(session: Session) -> int:
    if isinstance(session, Session):
        return _count(session, select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.OPEN))
    return sum(1 for row in _all_alerts(session) if _enum_value(row.status) == AlertStatus.OPEN.value)


def _latest_pipeline_job(session: Session) -> JobLog | None:
    if isinstance(session, Session):
        return session.scalar(
            select(JobLog)
            .where(JobLog.source_id.is_(None), JobLog.job_name == PROCESS_PIPELINE_TASK)
            .order_by(JobLog.created_at.desc(), JobLog.id.asc())
            .limit(1)
        )
    jobs = [job for job in _all_jobs(session) if job.source_id is None and job.job_name == PROCESS_PIPELINE_TASK]
    return _latest_job(jobs)


def _latest_source_job(session: Session) -> JobLog | None:
    if isinstance(session, Session):
        return session.scalar(
            select(JobLog).where(JobLog.source_id.is_not(None)).order_by(JobLog.finished_at.desc().nullslast(), JobLog.created_at.desc()).limit(1)
        )
    jobs = [job for job in _all_jobs(session) if job.source_id is not None]
    return _latest_job(jobs)


def _recent_failures(session: Session) -> list[PipelineFailureResponse]:
    failures = [
        *_raw_failures(session),
        *_job_failures(session),
    ]
    failures.sort(key=lambda item: _datetime_key(item.occurred_at), reverse=True)
    return failures[:RECENT_FAILURE_LIMIT]


def _raw_failures(session: Session) -> list[PipelineFailureResponse]:
    if isinstance(session, Session):
        rows = list(
            session.scalars(
                select(RawIntelligence)
                .where(RawIntelligence.processing_status == ProcessingStatus.FAILED)
                .order_by(RawIntelligence.updated_at.desc())
                .limit(RECENT_FAILURE_LIMIT)
            ).all()
        )
    else:
        rows = [row for row in _all_raw_intelligence(session) if _enum_value(row.processing_status) == ProcessingStatus.FAILED.value]
    return [
        PipelineFailureResponse(
            category="raw",
            id=row.id,
            source_id=row.source_id,
            source_name=safe_text(row.source_name),
            source_url=safe_url(row.source_url),
            status=_enum_value(row.processing_status) or "failed",
            stage=_enum_value(row.parsing_status),
            error_message=safe_text(row.error_message),
            occurred_at=row.updated_at,
            metadata=_safe_metadata_dict(row.metadata_ or {}),
        )
        for row in rows
    ]


def _job_failures(session: Session) -> list[PipelineFailureResponse]:
    if isinstance(session, Session):
        rows = list(
            session.scalars(
                select(JobLog).where(JobLog.status == JobStatus.FAILED).order_by(JobLog.updated_at.desc()).limit(RECENT_FAILURE_LIMIT)
            ).all()
        )
    else:
        rows = [row for row in _all_jobs(session) if _enum_value(row.status) == JobStatus.FAILED.value]
    sources = _sources_by_id(session, [row.source_id for row in rows if row.source_id])
    return [
        PipelineFailureResponse(
            category="job",
            id=row.id,
            source_id=row.source_id,
            source_name=safe_text(sources[row.source_id].name) if row.source_id in sources else None,
            source_url=safe_url(sources[row.source_id].base_url) if row.source_id in sources else None,
            status=_enum_value(row.status) or "failed",
            stage=_run_status(row),
            error_message=safe_text(row.error_message),
            occurred_at=row.finished_at or row.updated_at,
            metadata=_safe_job_metadata(row),
        )
        for row in rows
    ]


def _count(session: Session, statement: Select) -> int:
    return int(session.scalar(statement) or 0)


def _is_scoring_pending(row: ThreatIntelligence) -> bool:
    return (
        _enum_value(row.processing_status) == ProcessingStatus.NORMALIZED.value
        and (row.risk_score is None or _enum_value(row.risk_level) == RiskLevel.INFO.value)
    )


def _latest_job(jobs: list[JobLog]) -> JobLog | None:
    if not jobs:
        return None
    return max(jobs, key=lambda job: (_datetime_key(job.finished_at), _datetime_key(job.created_at), str(job.id)))


def _safe_job_metadata(job: JobLog | None) -> dict[str, Any]:
    if job is None:
        return {}
    return _safe_metadata_dict(job.metadata_ or {})


def _safe_metadata_dict(value: Any) -> dict[str, Any]:
    safe_value = safe_metadata(value)
    cleaned = _drop_internal_metadata(safe_value)
    if not isinstance(cleaned, dict):
        return {}
    return cleaned


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return safe_text(str(value))


def _is_internal_job_metadata_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return (
        "broker" in normalized
        or "result_backend" in normalized
        or normalized in {"redis_url", "database_url"}
    )


def _drop_internal_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned_dict: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_internal_job_metadata_key(key_text):
                continue
            cleaned = _drop_internal_metadata(item)
            if cleaned is not None:
                cleaned_dict[key_text] = cleaned
        return cleaned_dict
    if isinstance(value, list):
        return [cleaned for item in value if (cleaned := _drop_internal_metadata(item)) is not None]
    if isinstance(value, str) and _looks_internal_url(value):
        return None
    return value


def _looks_internal_url(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized.startswith(("redis://", "rediss://", "postgresql://", "postgresql+psycopg://"))


def _run_status(job: JobLog | None) -> str | None:
    if job is None:
        return None
    metadata = job.metadata_ or {}
    value = metadata.get("run_status")
    return str(value) if value is not None else None


def _attempts(job: JobLog | None) -> int | None:
    if job is None:
        return None
    metadata = job.metadata_ or {}
    value = metadata.get("attempts")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_retried(job: JobLog | None) -> bool:
    if job is None:
        return False
    metadata = job.metadata_ or {}
    return bool(metadata.get("retried") or (_attempts(job) or 0) > 1)


def _is_skipped(job: JobLog | None) -> bool:
    if job is None:
        return False
    metadata = job.metadata_ or {}
    return bool(metadata.get("skipped") or metadata.get("run_status") == "skipped")


def _source_audit_snapshot(source: Source) -> dict[str, Any]:
    return {
        "id": str(source.id),
        "name": source.name,
        "status": _enum_value(source.status),
        "base_url": safe_url(source.base_url),
    }


def _all_sources(session: Session) -> list[Source]:
    return list(session.scalars(select(Source)).all())


def _all_jobs(session: Session) -> list[JobLog]:
    return list(session.scalars(select(JobLog)).all())


def _all_raw_intelligence(session: Session) -> list[RawIntelligence]:
    return list(session.scalars(select(RawIntelligence)).all())


def _all_intelligence(session: Session) -> list[ThreatIntelligence]:
    return list(session.scalars(select(ThreatIntelligence)).all())


def _all_alerts(session: Session) -> list[Alert]:
    return list(session.scalars(select(Alert)).all())


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip().lower().replace("-", "_")


def _datetime_key(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return value.timestamp()
