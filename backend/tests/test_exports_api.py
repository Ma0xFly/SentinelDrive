from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import AlertStatus, IntelligenceType, ProcessingStatus, RiskLevel, Severity
from app.main import create_app
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import Alert, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class ExportSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.alerts: dict[UUID, Alert] = {}

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

    def seed_entry(self, **overrides) -> ThreatIntelligence:
        now = datetime.now(timezone.utc)
        entry_id = overrides.pop("id", uuid4())
        first_seen_at = overrides.pop("first_seen_at", now - timedelta(hours=2))
        last_seen_at = overrides.pop("last_seen_at", now)
        source_names = overrides.pop("source_names", ["NVD"])
        source_urls = overrides.pop("source_urls", ["https://nvd.test/CVE-2026-4001?api_key=secret&ref=public"])
        entry = ThreatIntelligence(
            id=entry_id,
            raw_intelligence_id=overrides.pop("raw_intelligence_id", uuid4()),
            title=overrides.pop("title", "CVE-2026-4001 affects T-Box firmware"),
            summary=overrides.pop("summary", "Remote exploit path for telematics firmware."),
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=source_names,
            source_urls=source_urls,
            canonical_source_url=overrides.pop("canonical_source_url", source_urls[0]),
            external_ids=overrides.pop("external_ids", {}),
            cve_id=overrides.pop("cve_id", "CVE-2026-4001"),
            cwe_id=overrides.pop("cwe_id", None),
            cvss_score=overrides.pop("cvss_score", 9.1),
            cvss_vector=overrides.pop("cvss_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
            severity=overrides.pop("severity", Severity.CRITICAL),
            affected_vendor=overrides.pop("affected_vendor", "ExampleAuto"),
            affected_product=overrides.pop("affected_product", "T-Box"),
            affected_version=overrides.pop("affected_version", None),
            vehicle_component=overrides.pop("vehicle_component", "tbox"),
            attack_surface=overrides.pop("attack_surface", "cellular"),
            exploit_status=overrides.pop("exploit_status", "unknown"),
            confidence=overrides.pop("confidence", "high"),
            risk_score=overrides.pop("risk_score", Decimal("92.00")),
            risk_level=overrides.pop("risk_level", RiskLevel.CRITICAL),
            tags=overrides.pop("tags", ["ota"]),
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            dedup_key=overrides.pop("dedup_key", f"export-test:{entry_id}"),
            normalized_text_hash=overrides.pop("normalized_text_hash", f"hash-{entry_id}"),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status=overrides.pop("status", "active"),
            metadata_=overrides.pop("metadata_", {"token": "secret"}),
            created_at=overrides.pop("created_at", first_seen_at),
            updated_at=overrides.pop("updated_at", last_seen_at),
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

    def seed_alert(self, entry: ThreatIntelligence, **overrides) -> Alert:
        now = datetime.now(timezone.utc)
        alert = Alert(
            id=overrides.pop("id", uuid4()),
            title=overrides.pop("title", "关键风险情报"),
            threat_intelligence_id=entry.id,
            triggering_rule=overrides.pop("triggering_rule", "critical-intelligence"),
            risk_level=overrides.pop("risk_level", entry.risk_level),
            triggered_at=overrides.pop("triggered_at", now),
            status=overrides.pop("status", AlertStatus.OPEN),
            notes=overrides.pop("notes", "token=secret"),
            metadata_=overrides.pop("metadata_", {"secret": "redacted"}),
            created_at=overrides.pop("created_at", now),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled alert overrides: {sorted(overrides)}")
        alert.intelligence = entry
        entry.alerts.append(alert)
        self.alerts[alert.id] = alert
        return alert

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is ThreatIntelligence:
            return self.entries.get(object_id)
        if model is Alert:
            return self.alerts.get(object_id)
        return None

    def scalars(self, statement):
        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity is Alert:
            return FakeScalarResult(self.alerts.values())
        if entity is ThreatIntelligence:
            return FakeScalarResult(self.entries.values())
        return FakeScalarResult([])


def make_app(session: ExportSession):
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


def csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text)))


@pytest.mark.anyio
async def test_export_routes_require_authentication():
    session = ExportSession()
    entry = session.seed_entry()
    session.seed_user()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        intelligence_csv = await client.get("/exports/intelligence.csv")
        markdown = await client.get(f"/exports/intelligence/{entry.id}/markdown")
        alerts_csv = await client.get("/exports/alerts.csv")
        pdf = await client.get("/exports/summary.pdf")

    assert intelligence_csv.status_code == 401
    assert markdown.status_code == 401
    assert alerts_csv.status_code == 401
    assert pdf.status_code == 401


@pytest.mark.anyio
async def test_intelligence_csv_export_honors_filters_and_redacts_urls():
    session = ExportSession()
    user = session.seed_user()
    included = session.seed_entry()
    session.seed_entry(
        title="Medium IVI advisory",
        cve_id="CVE-2026-4999",
        affected_vendor="OtherAuto",
        risk_level=RiskLevel.MEDIUM,
        severity=Severity.MEDIUM,
        dedup_key="export-test:other",
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/exports/intelligence.csv",
            headers=auth_header(token),
            params={"vendor": "Example", "risk_level": "critical"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment;" in response.headers["content-disposition"]
    rows = csv_rows(response.text)
    assert len(rows) == 1
    assert rows[0]["id"] == str(included.id)
    assert rows[0]["cve_id"] == "CVE-2026-4001"
    assert rows[0]["source_urls"] == "https://nvd.test/CVE-2026-4001?ref=public"
    assert "secret" not in response.text.lower()


@pytest.mark.anyio
async def test_single_intelligence_markdown_export_includes_sources_and_alerts_safely():
    session = ExportSession()
    user = session.seed_user()
    entry = session.seed_entry()
    session.seed_alert(entry, notes="token=secret")
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/exports/intelligence/{entry.id}/markdown", headers=auth_header(token))

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# CVE-2026-4001 affects T-Box firmware" in response.text
    assert "https://nvd.test/CVE-2026-4001?ref=public" in response.text
    assert "Related Alerts" in response.text
    assert "secret" not in response.text.lower()


@pytest.mark.anyio
async def test_alert_csv_export_honors_filters_and_redacts_notes():
    session = ExportSession()
    user = session.seed_user()
    entry = session.seed_entry()
    open_alert = session.seed_alert(entry, notes="token=secret")
    session.seed_alert(
        entry,
        triggering_rule="known-exploited",
        risk_level=RiskLevel.HIGH,
        status=AlertStatus.CLOSED,
        notes="已处理",
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/exports/alerts.csv", headers=auth_header(token), params={"status": "open"})

    assert response.status_code == 200
    rows = csv_rows(response.text)
    assert len(rows) == 1
    assert rows[0]["id"] == str(open_alert.id)
    assert rows[0]["notes"] == ""
    assert rows[0]["intelligence_title"] == entry.title
    assert "secret" not in response.text.lower()


@pytest.mark.anyio
async def test_alert_csv_export_invalid_intelligence_id_returns_structured_error():
    session = ExportSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/exports/alerts.csv",
            headers=auth_header(token),
            params={"intelligence_id": "   "},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_intelligence_id",
        "message": "情报 ID 格式无效。",
    }


@pytest.mark.anyio
async def test_summary_pdf_export_returns_pdf_without_sensitive_text():
    session = ExportSession()
    user = session.seed_user()
    entry = session.seed_entry()
    session.seed_alert(entry)
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/exports/summary.pdf", headers=auth_header(token))

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-1.4")
    assert b"SentinelDrive Security Summary" in response.content
    assert b"secret" not in response.content.lower()


@pytest.mark.anyio
async def test_missing_intelligence_markdown_export_returns_404():
    session = ExportSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/exports/intelligence/{uuid4()}/markdown", headers=auth_header(token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "intelligence_not_found"
