from datetime import datetime, time, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import (
    AlertStatus,
    IntelligenceType,
    ProcessingStatus,
    RiskLevel,
    Severity,
    SourceStatus,
    SourceType,
)
from app.main import create_app
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import Alert, User
from app.models.source import Source
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class StatsSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.alerts: dict[UUID, Alert] = {}
        self.sources: dict[UUID, Source] = {}
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
        entry_id = overrides.pop("id", uuid4())
        first_seen_at = overrides.pop("first_seen_at", now - timedelta(hours=1))
        created_at = overrides.pop("created_at", first_seen_at)
        updated_at = overrides.pop("updated_at", created_at)
        entry = ThreatIntelligence(
            id=entry_id,
            title=overrides.pop("title", f"CVE-2026-3001 affects vehicle T-Box {len(self.entries)}"),
            summary="Remote unauthenticated exploit path.",
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=overrides.pop("source_names", ["NVD"]),
            source_urls=overrides.pop("source_urls", ["https://nvd.nist.gov/vuln/detail/CVE-2026-3001"]),
            canonical_source_url="https://nvd.nist.gov/vuln/detail/CVE-2026-3001",
            cve_id="CVE-2026-3001",
            severity=overrides.pop("severity", Severity.CRITICAL),
            risk_score=None,
            risk_level=overrides.pop("risk_level", RiskLevel.CRITICAL),
            tags=["ota"],
            first_seen_at=first_seen_at,
            last_seen_at=overrides.pop("last_seen_at", first_seen_at),
            dedup_key=overrides.pop("dedup_key", f"stats-test:{entry_id}"),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status="active",
            created_at=created_at,
            updated_at=updated_at,
        )
        if overrides:
            raise AssertionError(f"Unhandled entry overrides: {sorted(overrides)}")
        self.entries[entry.id] = entry
        return entry

    def seed_alert(self, entry: ThreatIntelligence, **overrides) -> Alert:
        now = datetime.now(timezone.utc)
        alert_id = overrides.pop("id", uuid4())
        alert = Alert(
            id=alert_id,
            title="关键风险情报",
            threat_intelligence_id=entry.id,
            triggering_rule="critical-intelligence",
            risk_level=overrides.pop("risk_level", entry.risk_level),
            triggered_at=overrides.pop("triggered_at", now),
            status=overrides.pop("status", AlertStatus.OPEN),
            notes=None,
            metadata_={},
            created_at=now,
            updated_at=now,
        )
        if overrides:
            raise AssertionError(f"Unhandled alert overrides: {sorted(overrides)}")
        self.alerts[alert.id] = alert
        return alert

    def seed_source(self, *, name: str, status: SourceStatus = SourceStatus.ENABLED) -> Source:
        now = datetime.now(timezone.utc)
        source = Source(
            id=uuid4(),
            name=name,
            source_type=SourceType.RSS,
            status=status,
            config={},
            created_at=now,
            updated_at=now,
        )
        self.sources[source.id] = source
        return source

    def seed_source_link(
        self,
        entry: ThreatIntelligence,
        source: Source | None,
        *,
        url: str = "https://nvd.nist.gov/vuln/detail/CVE-2026-3001",
    ) -> ThreatIntelligenceSource:
        now = datetime.now(timezone.utc)
        link = ThreatIntelligenceSource(
            id=uuid4(),
            threat_intelligence_id=entry.id,
            source_id=source.id if source is not None else None,
            source_name=source.name if source is not None else "unknown",
            source_url=url,
            external_id=entry.cve_id,
            first_seen_at=entry.first_seen_at,
            last_seen_at=entry.last_seen_at,
            created_at=now,
            updated_at=now,
        )
        self.source_links[link.id] = link
        return link

    def scalars(self, statement):
        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity is Alert:
            return FakeScalarResult(self.alerts.values())
        if entity is ThreatIntelligence:
            return FakeScalarResult(self.entries.values())
        if entity is Source:
            return FakeScalarResult(self.sources.values())
        if entity is ThreatIntelligenceSource:
            return FakeScalarResult(self.source_links.values())
        return FakeScalarResult([])

    def scalar(self, statement):
        del statement
        return None

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        return None


def make_app(session: StatsSession):
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


async def fetch_overview(session: StatsSession) -> dict:
    app = make_app(session)
    token = token_for(app, session.seed_user())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/stats/overview", headers=auth_header(token))
    assert response.status_code == 200
    return response.json()


def expected_trend_dates() -> list[str]:
    today = datetime.now(timezone.utc).date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(29, -1, -1)]


@pytest.mark.anyio
async def test_stats_overview_allows_anonymous_read_but_rejects_invalid_token():
    app = make_app(StatsSession())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        anon = await client.get("/stats/overview")
        bad = await client.get("/stats/overview", headers=auth_header("invalid-token"))

    assert anon.status_code == 200
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "unauthorized"


@pytest.mark.anyio
async def test_stats_overview_empty_database_returns_zero_structure():
    body = await fetch_overview(StatsSession())

    assert body["totals"] == {"total_intelligence": 0, "new_last_24_hours": 0, "new_last_7_days": 0}
    assert body["by_intelligence_type"] == {
        "vulnerability": 0,
        "exposure": 0,
        "incident": 0,
        "advisory": 0,
    }
    assert body["by_severity"] == {
        "unknown": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }
    assert body["by_risk_level"] == {
        "info": 0,
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }
    assert body["by_processing_status"] == {
        "pending": 0,
        "collected": 0,
        "processing": 0,
        "normalized": 0,
        "failed": 0,
        "skipped": 0,
    }
    assert body["trend"] == [{"date": day, "count": 0} for day in expected_trend_dates()]
    assert body["alerts"]["total"] == 0
    assert body["alerts"]["by_status"] == {"open": 0, "acknowledged": 0, "closed": 0}
    assert body["alerts"]["trend"] == [{"date": day, "count": 0} for day in expected_trend_dates()]
    assert body["sources"] == {"enabled": 0, "top": []}


@pytest.mark.anyio
async def test_stats_overview_aggregates_distributions_and_recent_totals():
    session = StatsSession()
    now = datetime.now(timezone.utc)
    session.seed_entry(first_seen_at=now - timedelta(hours=1))
    session.seed_entry(
        intelligence_type=IntelligenceType.VULNERABILITY,
        severity=Severity.CRITICAL,
        risk_level=RiskLevel.HIGH,
        first_seen_at=now - timedelta(hours=2),
    )
    session.seed_entry(
        intelligence_type=IntelligenceType.ADVISORY,
        severity=Severity.HIGH,
        risk_level=RiskLevel.MEDIUM,
        processing_status=ProcessingStatus.COLLECTED,
        first_seen_at=now - timedelta(days=3),
    )
    session.seed_entry(
        severity=Severity.LOW,
        risk_level=RiskLevel.INFO,
        processing_status=ProcessingStatus.FAILED,
        first_seen_at=now - timedelta(days=10),
    )

    body = await fetch_overview(session)

    assert body["totals"] == {
        "total_intelligence": 4,
        "new_last_24_hours": 2,
        "new_last_7_days": 3,
    }
    assert body["by_intelligence_type"] == {
        "vulnerability": 3,
        "exposure": 0,
        "incident": 0,
        "advisory": 1,
    }
    assert body["by_severity"] == {
        "unknown": 0,
        "low": 1,
        "medium": 0,
        "high": 1,
        "critical": 2,
    }
    assert body["by_risk_level"] == {
        "info": 1,
        "low": 0,
        "medium": 1,
        "high": 1,
        "critical": 1,
    }
    assert body["by_processing_status"] == {
        "pending": 0,
        "collected": 1,
        "processing": 0,
        "normalized": 2,
        "failed": 1,
        "skipped": 0,
    }


@pytest.mark.anyio
async def test_stats_overview_trend_zero_fills_missing_days_and_respects_window_boundaries():
    session = StatsSession()
    now = datetime.now(timezone.utc)
    today = now.date()
    window_start_day = today - timedelta(days=29)
    window_start = datetime.combine(window_start_day, time.min, tzinfo=timezone.utc)
    session.seed_entry(first_seen_at=datetime.combine(today, time(8, 0), tzinfo=timezone.utc))
    session.seed_entry(first_seen_at=window_start)
    session.seed_entry(first_seen_at=window_start + timedelta(hours=23, minutes=30))
    session.seed_entry(
        first_seen_at=window_start - timedelta(microseconds=1),
        dedup_key="stats-test:outside-window",
    )

    body = await fetch_overview(session)

    trend = body["trend"]
    assert len(trend) == 30
    assert [point["date"] for point in trend] == expected_trend_dates()
    assert trend[0] == {"date": window_start_day.isoformat(), "count": 2}
    assert trend[-1] == {"date": today.isoformat(), "count": 1}
    assert trend[5] == {"date": trend[5]["date"], "count": 0}
    assert sum(point["count"] for point in trend) == 3
    assert body["totals"]["total_intelligence"] == 4


@pytest.mark.anyio
async def test_stats_overview_trend_uses_ingestion_date_not_publish_date():
    """近30天「新增」按入库时间 created_at 统计，而非发布日 first_seen_at。

    发布日很旧、但近期才被采集入库的情报应计入近30天趋势与新增总量；
    发布日在近30天、但入库已久的情报不应仅因发布日而被计入。
    """
    session = StatsSession()
    now = datetime.now(timezone.utc)
    today = now.date()
    ingested_today = datetime.combine(today, time(8, 0), tzinfo=timezone.utc)
    # 发布日 3 年前，但今天才入库 → 应计入近30天
    session.seed_entry(
        first_seen_at=now - timedelta(days=1095),
        created_at=ingested_today,
        dedup_key="stats-test:old-publish-new-ingest",
    )
    # 发布日今天，但入库在 40 天前 → 不计入近30天新增
    session.seed_entry(
        first_seen_at=now - timedelta(hours=1),
        created_at=now - timedelta(days=40),
        dedup_key="stats-test:new-publish-old-ingest",
    )

    body = await fetch_overview(session)

    assert body["totals"]["total_intelligence"] == 2
    assert body["totals"]["new_last_24_hours"] == 1
    assert body["totals"]["new_last_7_days"] == 1
    trend = body["trend"]
    assert sum(point["count"] for point in trend) == 1
    assert trend[-1] == {"date": today.isoformat(), "count": 1}


@pytest.mark.anyio
async def test_stats_overview_alerts_block_counts_status_and_trend():
    session = StatsSession()
    now = datetime.now(timezone.utc)
    entry = session.seed_entry()
    session.seed_alert(entry, status=AlertStatus.OPEN, triggered_at=now - timedelta(hours=1))
    session.seed_alert(entry, status=AlertStatus.OPEN, triggered_at=now - timedelta(hours=2))
    session.seed_alert(
        entry,
        status=AlertStatus.ACKNOWLEDGED,
        triggered_at=now - timedelta(days=3),
    )
    session.seed_alert(
        entry,
        status=AlertStatus.CLOSED,
        triggered_at=now - timedelta(days=40),
    )

    body = await fetch_overview(session)

    assert body["alerts"]["total"] == 4
    assert body["alerts"]["by_status"] == {"open": 2, "acknowledged": 1, "closed": 1}
    assert body["alerts"]["trend"][-1] == {"date": now.date().isoformat(), "count": 2}
    assert sum(point["count"] for point in body["alerts"]["trend"]) == 3
    assert body["trend"][-1] == {"date": now.date().isoformat(), "count": 1}


@pytest.mark.anyio
async def test_stats_overview_sources_block_ranks_by_distinct_intelligence():
    session = StatsSession()
    kev = session.seed_source(name="kev")
    nvd = session.seed_source(name="nvd")
    alpha = session.seed_source(name="alpha")
    blog = session.seed_source(name="blog", status=SourceStatus.DISABLED)
    session.seed_source(name="empty")

    entries = [session.seed_entry() for _ in range(5)]
    for entry in entries:
        session.seed_source_link(entry, kev)
    for entry in entries[:3]:
        session.seed_source_link(entry, nvd)
    session.seed_source_link(entries[0], nvd, url="https://nvd.nist.gov/mirror/CVE-2026-3001")
    for entry in entries[3:]:
        session.seed_source_link(entry, alpha)
    for entry in entries[:2]:
        session.seed_source_link(entry, blog)
    session.seed_source_link(entries[0], None, url="https://unknown.example.test/item")

    body = await fetch_overview(session)

    assert body["sources"]["enabled"] == 4
    assert body["sources"]["top"] == [
        {"id": str(kev.id), "name": "kev", "intelligence_count": 5},
        {"id": str(nvd.id), "name": "nvd", "intelligence_count": 3},
        {"id": str(alpha.id), "name": "alpha", "intelligence_count": 2},
        {"id": str(blog.id), "name": "blog", "intelligence_count": 2},
    ]
