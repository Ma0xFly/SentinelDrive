from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql

from app.api.deps import get_pipeline_task_client, get_request_session
from app.api.routes.sources import JobSearchParams, _job_statement
from app.core.settings import Settings
from app.db.types import AlertStatus, AuditAction, IntelligenceType, JobStatus, ProcessingStatus, RiskLevel, Severity, SourceStatus, SourceType
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.intelligence import RawIntelligence, ThreatIntelligence
from app.models.job import JobLog
from app.models.security import Alert, User
from app.models.source import Source, SyncState
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class SourceSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.sources: dict[UUID, Source] = {}
        self.sync_states: dict[UUID, SyncState] = {}
        self.jobs: dict[UUID, JobLog] = {}
        self.raw_items: dict[UUID, RawIntelligence] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.alerts: dict[UUID, Alert] = {}
        self.audit_events: list[AuditEvent] = []
        self.commits = 0

    def seed_user(self, *, email: str = "analyst@example.test", password: str = "analyst-password") -> User:
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            display_name="Analyst",
            is_active=True,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self.users[user.id] = user
        return user

    def seed_source(self, **overrides) -> Source:
        now = datetime.now(timezone.utc)
        source = Source(
            id=overrides.pop("id", uuid4()),
            name=overrides.pop("name", "nvd"),
            source_type=overrides.pop("source_type", SourceType.API),
            base_url=overrides.pop("base_url", "https://nvd.test/api?api_key=secret&safe=1"),
            status=overrides.pop("status", SourceStatus.ENABLED),
            config=overrides.pop(
                "config",
                {"retry_attempts": 2, "credentials": {"api_key": "secret"}, "metadata": {"owner": "security"}},
            ),
            last_success_at=overrides.pop("last_success_at", now - timedelta(hours=2)),
            last_error_at=overrides.pop("last_error_at", None),
            last_error_message=overrides.pop("last_error_message", None),
            created_at=overrides.pop("created_at", now - timedelta(days=1)),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled source overrides: {sorted(overrides)}")
        self.sources[source.id] = source
        source.sync_state = None
        return source

    def seed_sync_state(self, source: Source, **overrides) -> SyncState:
        now = datetime.now(timezone.utc)
        sync_state = SyncState(
            id=overrides.pop("id", uuid4()),
            source_id=source.id,
            cursor=overrides.pop("cursor", "cursor-1"),
            status=overrides.pop("status", JobStatus.SUCCESS),
            last_run_at=overrides.pop("last_run_at", now - timedelta(hours=1)),
            next_run_at=overrides.pop("next_run_at", now + timedelta(hours=1)),
            consecutive_failures=overrides.pop("consecutive_failures", 0),
            metadata_=overrides.pop("metadata_", {"attempts": 2, "token": "secret"}),
            created_at=overrides.pop("created_at", now - timedelta(days=1)),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled sync overrides: {sorted(overrides)}")
        self.sync_states[sync_state.id] = sync_state
        source.sync_state = sync_state
        sync_state.source = source
        return sync_state

    def seed_job(self, source: Source | None = None, **overrides) -> JobLog:
        now = datetime.now(timezone.utc)
        job = JobLog(
            id=overrides.pop("id", uuid4()),
            job_name=overrides.pop("job_name", "sentineldrive.sync_sources"),
            source_id=overrides.pop("source_id", source.id if source else None),
            status=overrides.pop("status", JobStatus.SUCCESS),
            started_at=overrides.pop("started_at", now - timedelta(minutes=5)),
            finished_at=overrides.pop("finished_at", now),
            items_seen=overrides.pop("items_seen", 5),
            items_created=overrides.pop("items_created", 3),
            items_updated=overrides.pop("items_updated", 2),
            error_message=overrides.pop("error_message", None),
            metadata_=overrides.pop("metadata_", {"run_status": "success", "attempts": 1}),
            created_at=overrides.pop("created_at", now),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled job overrides: {sorted(overrides)}")
        self.jobs[job.id] = job
        return job

    def seed_raw(self, source: Source | None = None, **overrides) -> RawIntelligence:
        now = datetime.now(timezone.utc)
        raw = RawIntelligence(
            id=overrides.pop("id", uuid4()),
            source_id=overrides.pop("source_id", source.id if source else None),
            source_name=overrides.pop("source_name", source.name if source else "manual"),
            source_type=overrides.pop("source_type", source.source_type if source else SourceType.MANUAL),
            source_url=overrides.pop("source_url", "https://source.test/item?api_key=secret&safe=1"),
            external_id=overrides.pop("external_id", "RAW-1"),
            fetched_at=overrides.pop("fetched_at", now),
            first_seen_at=overrides.pop("first_seen_at", now - timedelta(hours=2)),
            title=overrides.pop("title", "Raw item"),
            summary=overrides.pop("summary", "Raw summary"),
            snippet=overrides.pop("snippet", "Raw snippet"),
            raw_content=overrides.pop("raw_content", {"token": "secret"}),
            raw_hash=overrides.pop("raw_hash", f"raw-{uuid4()}"),
            content_hash=overrides.pop("content_hash", None),
            parsing_status=overrides.pop("parsing_status", ProcessingStatus.PENDING),
            processing_status=overrides.pop("processing_status", ProcessingStatus.COLLECTED),
            error_message=overrides.pop("error_message", None),
            metadata_=overrides.pop("metadata_", {"token": "secret", "safe": "value"}),
            retained_payload_mode=overrides.pop("retained_payload_mode", "metadata_only"),
            created_at=overrides.pop("created_at", now - timedelta(hours=2)),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled raw overrides: {sorted(overrides)}")
        self.raw_items[raw.id] = raw
        return raw

    def seed_entry(self, **overrides) -> ThreatIntelligence:
        now = datetime.now(timezone.utc)
        entry = ThreatIntelligence(
            id=overrides.pop("id", uuid4()),
            raw_intelligence_id=overrides.pop("raw_intelligence_id", None),
            title=overrides.pop("title", "Normalized intelligence"),
            summary=overrides.pop("summary", "Normalized summary"),
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=overrides.pop("source_names", ["NVD"]),
            source_urls=overrides.pop("source_urls", ["https://nvd.test/CVE-2026-7001"]),
            canonical_source_url=overrides.pop("canonical_source_url", "https://nvd.test/CVE-2026-7001"),
            external_ids=overrides.pop("external_ids", {}),
            cve_id=overrides.pop("cve_id", "CVE-2026-7001"),
            cwe_id=overrides.pop("cwe_id", None),
            cvss_score=overrides.pop("cvss_score", None),
            cvss_vector=overrides.pop("cvss_vector", None),
            severity=overrides.pop("severity", Severity.HIGH),
            affected_vendor=overrides.pop("affected_vendor", "ExampleAuto"),
            affected_product=overrides.pop("affected_product", "T-Box"),
            affected_version=overrides.pop("affected_version", None),
            vehicle_component=overrides.pop("vehicle_component", "tbox"),
            attack_surface=overrides.pop("attack_surface", "cellular"),
            exploit_status=overrides.pop("exploit_status", "unknown"),
            confidence=overrides.pop("confidence", "medium"),
            risk_score=overrides.pop("risk_score", None),
            risk_level=overrides.pop("risk_level", RiskLevel.INFO),
            tags=overrides.pop("tags", []),
            first_seen_at=overrides.pop("first_seen_at", now - timedelta(hours=2)),
            last_seen_at=overrides.pop("last_seen_at", now),
            dedup_key=overrides.pop("dedup_key", f"ops:{uuid4()}"),
            normalized_text_hash=overrides.pop("normalized_text_hash", None),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status=overrides.pop("status", "active"),
            metadata_=overrides.pop("metadata_", {}),
            created_at=overrides.pop("created_at", now - timedelta(hours=2)),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled entry overrides: {sorted(overrides)}")
        self.entries[entry.id] = entry
        return entry

    def seed_alert(self, entry: ThreatIntelligence, **overrides) -> Alert:
        now = datetime.now(timezone.utc)
        alert = Alert(
            id=overrides.pop("id", uuid4()),
            title=overrides.pop("title", "Open pipeline alert"),
            threat_intelligence_id=entry.id,
            triggering_rule=overrides.pop("triggering_rule", "critical-intelligence"),
            risk_level=overrides.pop("risk_level", RiskLevel.HIGH),
            triggered_at=overrides.pop("triggered_at", now),
            status=overrides.pop("status", AlertStatus.OPEN),
            notes=overrides.pop("notes", None),
            metadata_=overrides.pop("metadata_", {}),
            created_at=overrides.pop("created_at", now),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled alert overrides: {sorted(overrides)}")
        self.alerts[alert.id] = alert
        return alert

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is Source:
            return self.sources.get(object_id)
        return None

    def scalar(self, statement):
        del statement
        return None

    def scalars(self, statement):
        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity is Source:
            return FakeScalarResult(self.sources.values())
        if entity is JobLog:
            return FakeScalarResult(self.jobs.values())
        if entity is RawIntelligence:
            return FakeScalarResult(self.raw_items.values())
        if entity is ThreatIntelligence:
            return FakeScalarResult(self.entries.values())
        if entity is Alert:
            return FakeScalarResult(self.alerts.values())
        return FakeScalarResult([])

    def add(self, instance):
        self._assign_identity(instance)
        if isinstance(instance, AuditEvent):
            self.audit_events.append(instance)
        elif isinstance(instance, User):
            self.users[instance.id] = instance
        elif isinstance(instance, Source):
            self.sources[instance.id] = instance
        elif isinstance(instance, JobLog):
            self.jobs[instance.id] = instance

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def refresh(self, instance):
        del instance

    def _assign_identity(self, instance):
        if getattr(instance, "id", None) is None:
            instance.id = uuid4()
        now = datetime.now(timezone.utc)
        if getattr(instance, "created_at", None) is None:
            instance.created_at = now
        if getattr(instance, "updated_at", None) is None:
            instance.updated_at = now
        if isinstance(instance, AuditEvent) and instance.metadata_ is None:
            instance.metadata_ = {}
        if isinstance(instance, JobLog) and instance.metadata_ is None:
            instance.metadata_ = {}


class FakePipelineClient:
    def __init__(self):
        self.calls: list[dict[str, int]] = []

    def enqueue_process_pipeline(self, **limits):
        self.calls.append(limits)
        return type("EnqueuedTask", (), {"task_id": "celery-test-id", "task_name": "sentineldrive.process_pipeline", "status": "queued"})()

    def task_status(self, task_id: str) -> str:
        assert task_id == "celery-test-id"
        return "queued"


def make_app(session: SourceSession, pipeline_client: FakePipelineClient | None = None):
    app = create_app(
        settings=Settings(
            APP_SECRET_KEY="test-secret-key",
            DATABASE_URL="postgresql+psycopg://user:pass@postgres:5432/app",
            ADMIN_BOOTSTRAP_EMAIL="admin@example.test",
            ADMIN_BOOTSTRAP_PASSWORD="change-me-development-only",
        )
    )

    async def override_session():
        yield session

    app.dependency_overrides[get_request_session] = override_session
    if pipeline_client is not None:
        app.dependency_overrides[get_pipeline_task_client] = lambda: pipeline_client
    return app


def token_for(app, user: User) -> str:
    return create_access_token(user.id, user.email, user.is_admin, app.state.settings)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_source_routes_split_public_read_from_authenticated_operations():
    session = SourceSession()
    source = session.seed_source()
    session.seed_user()
    app = make_app(session, FakePipelineClient())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sources = await client.get("/sources")
        detail = await client.get(f"/sources/{source.id}")
        jobs = await client.get("/sources/jobs")
        pipeline_status = await client.get("/sources/pipeline/status")
        pipeline_trigger = await client.post("/sources/pipeline/trigger", json={})
        update = await client.patch(f"/sources/{source.id}/status", json={"status": "disabled"})

    assert sources.status_code == 200
    assert detail.status_code == 200
    assert jobs.status_code == 401
    assert pipeline_status.status_code == 401
    assert pipeline_trigger.status_code == 401
    assert update.status_code == 401


@pytest.mark.anyio
async def test_source_status_list_includes_safe_state_job_summary_and_redaction():
    session = SourceSession()
    user = session.seed_user()
    source = session.seed_source()
    session.seed_sync_state(source)
    session.seed_job(
        source,
        metadata_={"run_status": "success", "attempts": 2, "retried": True, "token": "secret"},
    )
    session.seed_job(
        source,
        status=JobStatus.SUCCESS,
        metadata_={"run_status": "skipped", "skipped": True, "reason": "disabled"},
        items_seen=0,
        items_created=0,
        items_updated=0,
        finished_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sources", headers=auth_header(token), params={"source_type": "api", "q": "nv"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["name"] == "nvd"
    assert item["enabled"] is True
    assert item["base_url"] == "https://nvd.test/api?safe=1"
    assert item["config"] == {"retry_attempts": 2, "metadata": {"owner": "security"}}
    assert item["sync_state"]["consecutive_failures"] == 0
    assert item["sync_state"]["metadata"] == {"attempts": 2}
    assert item["recent_jobs"]["total"] == 2
    assert item["recent_jobs"]["retried"] == 1
    assert item["recent_jobs"]["skipped"] == 1
    assert item["recent_jobs"]["items_seen"] == 5
    assert "secret" not in response.text.lower()


@pytest.mark.anyio
async def test_pipeline_status_returns_counts_jobs_failures_and_redacts_sensitive_data():
    session = SourceSession()
    user = session.seed_user()
    source = session.seed_source(name="nvd", base_url="https://nvd.test/api?api_key=secret&safe=1")
    pending_raw = session.seed_raw(source, processing_status=ProcessingStatus.COLLECTED)
    failed_raw = session.seed_raw(
        source,
        processing_status=ProcessingStatus.FAILED,
        parsing_status=ProcessingStatus.FAILED,
        error_message="token=secret",
        metadata_={"reason": "parse_error", "api_key": "secret"},
        updated_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    assert pending_raw.id != failed_raw.id
    entry = session.seed_entry(risk_score=None, risk_level=RiskLevel.INFO)
    session.seed_alert(entry, status=AlertStatus.OPEN)
    session.seed_alert(entry, status=AlertStatus.CLOSED)
    session.seed_job(
        None,
        job_name="sentineldrive.process_pipeline",
        source_id=None,
        status=JobStatus.QUEUED,
        metadata_={
            "run_status": "queued",
            "celery_task_id": "celery-test-id",
            "celery_status": "queued",
            "broker_url": "redis://:secret@redis:6379/1",
        },
    )
    failed_job = session.seed_job(
        source,
        status=JobStatus.FAILED,
        error_message="api_key=secret",
        metadata_={"run_status": "failed", "attempts": 2, "password": "secret"},
        updated_at=datetime.now(timezone.utc),
    )
    app = make_app(session, FakePipelineClient())
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sources/pipeline/status", headers=auth_header(token))

    assert response.status_code == 200
    body = response.json()
    assert body["pending_raw_rows"] == 1
    assert body["failed_raw_rows"] == 1
    assert body["scoring_pending_intelligence_rows"] == 1
    assert body["open_alerts"] == 1
    assert body["latest_pipeline_job"]["job_name"] == "sentineldrive.process_pipeline"
    assert body["latest_pipeline_job"]["celery_task_id"] == "celery-test-id"
    assert body["latest_pipeline_job"]["celery_status"] == "queued"
    assert body["latest_source_job"]["id"] == str(failed_job.id)
    assert body["recent_failures"][0]["category"] == "raw"
    assert body["recent_failures"][0]["error_message"] is None
    assert body["recent_failures"][0]["metadata"] == {"reason": "parse_error"}
    assert body["recent_failures"][1]["category"] == "job"
    assert body["recent_failures"][1]["source_url"] == "https://nvd.test/api?safe=1"
    assert "secret" not in response.text.lower()
    assert "redis://" not in response.text.lower()


@pytest.mark.anyio
async def test_pipeline_trigger_enqueues_only_approved_task_records_job_and_audit_event():
    session = SourceSession()
    user = session.seed_user()
    fake_pipeline = FakePipelineClient()
    app = make_app(session, fake_pipeline)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/sources/pipeline/trigger",
            headers=auth_header(token),
            json={"normalization_limit": 10, "scoring_limit": 20, "alert_limit": 30},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["task_name"] == "sentineldrive.process_pipeline"
    assert body["celery_task_id"] == "celery-test-id"
    assert body["status"] == "queued"
    assert body["message"] == "处理流水线已加入队列。"
    assert fake_pipeline.calls == [{"normalization_limit": 10, "scoring_limit": 20, "alert_limit": 30}]
    job = session.jobs[UUID(body["job_id"])]
    assert job.source_id is None
    assert job.job_name == "sentineldrive.process_pipeline"
    assert job.status == JobStatus.QUEUED
    assert job.metadata_["celery_task_id"] == "celery-test-id"
    assert session.audit_events[-1].action == AuditAction.STATUS_CHANGE
    assert session.audit_events[-1].actor_user_id == user.id
    assert session.audit_events[-1].entity_type == "pipeline"
    assert session.audit_events[-1].entity_id == job.id


@pytest.mark.anyio
async def test_pipeline_trigger_rejects_extra_task_control_fields():
    session = SourceSession()
    user = session.seed_user()
    fake_pipeline = FakePipelineClient()
    app = make_app(session, fake_pipeline)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/sources/pipeline/trigger",
            headers=auth_header(token),
            json={"task_name": "sentineldrive.sync_sources"},
        )

    assert response.status_code == 422
    assert fake_pipeline.calls == []


@pytest.mark.anyio
async def test_job_log_filters_source_retry_skip_status_and_redacts_errors():
    session = SourceSession()
    user = session.seed_user()
    source = session.seed_source(name="rss-feed", source_type=SourceType.RSS)
    session.seed_job(
        source,
        status=JobStatus.FAILED,
        error_message="token=secret",
        metadata_={"run_status": "failed", "attempts": 2, "retried": True, "api_key": "secret"},
        items_seen=1,
        items_created=0,
        items_updated=0,
    )
    session.seed_job(
        source,
        status=JobStatus.SUCCESS,
        metadata_={"run_status": "skipped", "skipped": True, "reason": "disabled"},
        items_seen=0,
        items_created=0,
        items_updated=0,
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        failed = await client.get(
            "/sources/jobs",
            headers=auth_header(token),
            params={"source_id": str(source.id), "status": "failed", "retried": "true", "run_status": "failed"},
        )
        skipped = await client.get(
            "/sources/jobs",
            headers=auth_header(token),
            params={"source_id": str(source.id), "skipped": "true"},
        )

    assert failed.status_code == 200
    assert failed.json()["total"] == 1
    failed_job = failed.json()["items"][0]
    assert failed_job["source_name"] == "rss-feed"
    assert failed_job["error_message"] is None
    assert failed_job["attempts"] == 2
    assert failed_job["retried"] is True
    assert failed_job["metadata"] == {"run_status": "failed", "attempts": 2, "retried": True}
    assert "secret" not in failed.text.lower()
    assert skipped.status_code == 200
    assert skipped.json()["total"] == 1
    assert skipped.json()["items"][0]["skipped"] is True


@pytest.mark.anyio
async def test_source_status_update_is_audited_and_validates_sensitive_reason():
    session = SourceSession()
    user = session.seed_user()
    source = session.seed_source(status=SourceStatus.ENABLED, last_error_message="old failure")
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_reason = await client.patch(
            f"/sources/{source.id}/status",
            headers=auth_header(token),
            json={"status": "disabled", "reason": "token=secret"},
        )
        updated = await client.patch(
            f"/sources/{source.id}/status",
            headers=auth_header(token),
            json={"status": "disabled", "reason": "维护窗口"},
        )

    assert bad_reason.status_code == 422
    assert updated.status_code == 200
    assert updated.json()["status"] == "disabled"
    assert updated.json()["enabled"] is False
    assert updated.json()["last_error_message"] is None
    assert session.audit_events[-1].action == AuditAction.STATUS_CHANGE
    assert session.audit_events[-1].actor_user_id == user.id
    assert session.audit_events[-1].entity_id == source.id
    assert session.audit_events[-1].before["status"] == "enabled"
    assert session.audit_events[-1].after["status"] == "disabled"
    assert session.audit_events[-1].metadata_["reason"] == "维护窗口"


@pytest.mark.anyio
async def test_missing_source_returns_deterministic_404():
    session = SourceSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/sources/{uuid4()}", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "source_not_found"


def test_job_sql_filters_derive_skipped_and_retried_from_metadata():
    statement = _job_statement(JobSearchParams(skipped=True, retried=True))

    compiled = statement.compile(dialect=postgresql.dialect())

    assert "metadata ->>" in str(compiled)
    assert "OR" in str(compiled)
    assert set(compiled.params.values()) >= {"retried", "attempts", "skipped", "run_status"}
