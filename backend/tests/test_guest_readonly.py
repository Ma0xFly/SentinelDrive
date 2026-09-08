from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import (
    AlertStatus,
    IntelligenceType,
    JobStatus,
    ProcessingStatus,
    RiskLevel,
    Severity,
    SourceStatus,
    SourceType,
)
from app.main import create_app
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
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


class GuestSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.sources: dict[UUID, Source] = {}
        self.jobs: dict[UUID, JobLog] = {}
        self.alerts: dict[UUID, Alert] = {}
        self.source_links: dict[UUID, ThreatIntelligenceSource] = {}

    def seed_user(self, *, email: str = "analyst@example.test") -> User:
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password("analyst-password"),
            display_name="Analyst",
            is_active=True,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self.users[user.id] = user
        return user

    def seed_entry(self, **overrides) -> ThreatIntelligence:
        now = datetime.now(timezone.utc)
        first_seen_at = overrides.pop("first_seen_at", now - timedelta(hours=2))
        entry_id = overrides.pop("id", uuid4())
        entry = ThreatIntelligence(
            id=entry_id,
            raw_intelligence_id=overrides.pop("raw_intelligence_id", uuid4()),
            title=overrides.pop("title", "CVE-2026-3001 affects vehicle T-Box"),
            summary=overrides.pop("summary", "Remote unauthenticated exploit path."),
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=overrides.pop("source_names", ["NVD"]),
            source_urls=overrides.pop("source_urls", ["https://nvd.nist.gov/vuln/detail/CVE-2026-3001"]),
            canonical_source_url=overrides.pop("canonical_source_url", "https://nvd.nist.gov/vuln/detail/CVE-2026-3001"),
            external_ids=overrides.pop("external_ids", {}),
            cve_id=overrides.pop("cve_id", "CVE-2026-3001"),
            cwe_id=overrides.pop("cwe_id", None),
            cvss_score=overrides.pop("cvss_score", 9.8),
            cvss_vector=overrides.pop("cvss_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
            severity=overrides.pop("severity", Severity.CRITICAL),
            affected_vendor=overrides.pop("affected_vendor", "ExampleAuto"),
            affected_product=overrides.pop("affected_product", "T-Box"),
            affected_version=overrides.pop("affected_version", None),
            vehicle_component=overrides.pop("vehicle_component", "tbox"),
            attack_surface=overrides.pop("attack_surface", "cellular"),
            exploit_status=overrides.pop("exploit_status", "unknown"),
            confidence=overrides.pop("confidence", "high"),
            risk_score=overrides.pop("risk_score", Decimal("95.00")),
            risk_level=overrides.pop("risk_level", RiskLevel.CRITICAL),
            tags=overrides.pop("tags", ["ota"]),
            first_seen_at=first_seen_at,
            last_seen_at=overrides.pop("last_seen_at", now),
            dedup_key=overrides.pop("dedup_key", f"guest:{entry_id}"),
            normalized_text_hash=overrides.pop("normalized_text_hash", f"hash-{entry_id}"),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status=overrides.pop("status", "active"),
            metadata_=overrides.pop("metadata_", {"scoring": {"base": 95}, "token": "redacted"}),
            created_at=overrides.pop("created_at", first_seen_at),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled entry overrides: {sorted(overrides)}")
        entry.source_links = [
            ThreatIntelligenceSource(
                id=uuid4(),
                threat_intelligence_id=entry.id,
                source_id=uuid4(),
                raw_intelligence_id=entry.raw_intelligence_id,
                source_name=entry.source_names[0],
                source_url=entry.source_urls[0],
                external_id=entry.cve_id,
                first_seen_at=entry.first_seen_at,
                last_seen_at=entry.last_seen_at,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
        ]
        entry.alerts = []
        self.entries[entry.id] = entry
        return entry

    def seed_source(self, *, name: str = "nvd", status: SourceStatus = SourceStatus.ENABLED) -> Source:
        now = datetime.now(timezone.utc)
        source = Source(
            id=uuid4(),
            name=name,
            source_type=SourceType.API,
            base_url="https://nvd.test/api?api_key=secret&safe=1",
            status=status,
            config={"retry_attempts": 2, "credentials": {"api_key": "secret"}},
            last_success_at=now - timedelta(hours=2),
            last_error_at=None,
            last_error_message=None,
            created_at=now - timedelta(days=1),
            updated_at=now,
        )
        source.sync_state = None
        self.sources[source.id] = source
        return source

    def seed_sync_state(self, source: Source, *, consecutive_failures: int = 3) -> SyncState:
        now = datetime.now(timezone.utc)
        sync_state = SyncState(
            id=uuid4(),
            source_id=source.id,
            cursor="cursor-1",
            status=JobStatus.FAILED,
            last_run_at=now - timedelta(hours=1),
            next_run_at=now + timedelta(hours=1),
            consecutive_failures=consecutive_failures,
            metadata_={"attempts": 2, "token": "secret"},
            created_at=now - timedelta(days=1),
            updated_at=now,
        )
        source.sync_state = sync_state
        return sync_state

    def seed_job(self, source: Source) -> JobLog:
        now = datetime.now(timezone.utc)
        job = JobLog(
            id=uuid4(),
            job_name="sentineldrive.sync_sources",
            source_id=source.id,
            status=JobStatus.FAILED,
            started_at=now - timedelta(minutes=5),
            finished_at=now,
            items_seen=5,
            items_created=3,
            items_updated=2,
            error_message="token=secret",
            metadata_={"run_status": "failed", "attempts": 2},
            created_at=now,
            updated_at=now,
        )
        self.jobs[job.id] = job
        return job

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is ThreatIntelligence:
            return self.entries.get(object_id)
        if model is Source:
            return self.sources.get(object_id)
        if model is Alert:
            return self.alerts.get(object_id)
        return None

    def scalar(self, statement):
        del statement
        return None

    def scalars(self, statement):
        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity is ThreatIntelligence:
            return FakeScalarResult(self.entries.values())
        if entity is Source:
            return FakeScalarResult(self.sources.values())
        if entity is JobLog:
            return FakeScalarResult(self.jobs.values())
        if entity is Alert:
            return FakeScalarResult(self.alerts.values())
        if entity is ThreatIntelligenceSource:
            return FakeScalarResult(self.source_links.values())
        return FakeScalarResult([])


def make_app(session: GuestSession):
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
    return app


def token_for(app, user: User) -> str:
    return create_access_token(user.id, user.email, user.is_admin, app.state.settings)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_guest_can_read_intelligence_list_and_detail():
    session = GuestSession()
    entry = session.seed_entry()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/intelligence")
        detail = await client.get(f"/intelligence/{entry.id}")

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["id"] == str(entry.id)


@pytest.mark.anyio
async def test_guest_can_read_stats_overview():
    session = GuestSession()
    session.seed_entry()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/stats/overview")

    assert response.status_code == 200
    assert response.json()["totals"]["total_intelligence"] == 1


@pytest.mark.anyio
async def test_guest_sources_redact_operational_fields():
    session = GuestSession()
    source = session.seed_source()
    session.seed_sync_state(source, consecutive_failures=7)
    session.seed_job(source)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/sources")
        detail = await client.get(f"/sources/{source.id}")

    assert listing.status_code == 200
    listing_body = listing.json()
    assert listing_body["total"] == 1
    item = listing_body["items"][0]
    assert detail.status_code == 200
    detail_body = detail.json()

    public_keys = {"id", "name", "source_type", "status", "enabled", "base_url"}
    operational_keys = {
        "config",
        "last_success_at",
        "last_error_at",
        "last_error_message",
        "failure_count",
        "sync_state",
        "recent_jobs",
        "created_at",
        "updated_at",
    }
    for body in (item, detail_body):
        assert public_keys <= set(body.keys())
        assert not (operational_keys & set(body.keys()))
        assert body["name"] == "nvd"
        assert body["base_url"] == "https://nvd.test/api?safe=1"
        assert body["enabled"] is True
    assert "secret" not in listing.text.lower()
    assert "secret" not in detail.text.lower()


@pytest.mark.anyio
async def test_authenticated_sources_include_operational_fields():
    session = GuestSession()
    user = session.seed_user()
    source = session.seed_source()
    session.seed_sync_state(source, consecutive_failures=7)
    session.seed_job(source)
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/sources", headers=auth_header(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["config"] == {"retry_attempts": 2}
    assert item["sync_state"]["consecutive_failures"] == 7
    assert item["recent_jobs"]["total"] == 1
    assert item["failure_count"] == 7
    assert item["last_success_at"] is not None


@pytest.mark.anyio
async def test_guest_write_and_export_endpoints_require_authentication():
    session = GuestSession()
    source = session.seed_source()
    entry = session.seed_entry()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        manual = await client.post(
            "/manual-entries",
            json={"category": "vulnerability", "title": "CVE-2026-0001 manual", "summary": "x"},
        )
        alert_status = await client.patch(f"/alerts/{uuid4()}/status", json={"status": "closed"})
        source_status = await client.patch(f"/sources/{source.id}/status", json={"status": "disabled"})
        pipeline = await client.post("/sources/pipeline/trigger", json={})
        evaluate = await client.post("/alerts/evaluate", json={})
        export = await client.get("/exports/intelligence.csv")

    assert manual.status_code == 401
    assert alert_status.status_code == 401
    assert source_status.status_code == 401
    assert pipeline.status_code == 401
    assert evaluate.status_code == 401
    assert export.status_code == 401


@pytest.mark.anyio
async def test_invalid_token_returns_401_on_public_reads():
    session = GuestSession()
    session.seed_entry()
    session.seed_source()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        intelligence = await client.get("/intelligence", headers=auth_header("invalid-token"))
        stats = await client.get("/stats/overview", headers=auth_header("invalid-token"))
        sources = await client.get("/sources", headers=auth_header("invalid-token"))

    assert intelligence.status_code == 401
    assert stats.status_code == 401
    assert sources.status_code == 401
    assert intelligence.json()["error"]["code"] == "unauthorized"