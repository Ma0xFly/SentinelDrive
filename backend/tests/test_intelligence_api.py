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


class IntelligenceSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}

    def seed_user(
        self,
        *,
        email: str = "analyst@example.test",
        password: str = "analyst-password",
        is_active: bool = True,
    ) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            display_name="Analyst",
            is_active=is_active,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self.users[user.id] = user
        return user

    def seed_entry(self, **overrides) -> ThreatIntelligence:
        now = datetime.now(timezone.utc)
        first_seen_at = overrides.pop("first_seen_at", now - timedelta(days=1))
        last_seen_at = overrides.pop("last_seen_at", now)
        entry_id = overrides.pop("id", uuid4())
        entry = ThreatIntelligence(
            id=entry_id,
            raw_intelligence_id=overrides.pop("raw_intelligence_id", uuid4()),
            title=overrides.pop("title", "CVE-2026-1001 affects T-Box cellular stack"),
            summary=overrides.pop("summary", "Remote cellular exposure in telematics firmware."),
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=overrides.pop("source_names", ["NVD"]),
            source_urls=overrides.pop("source_urls", ["https://nvd.nist.gov/vuln/detail/CVE-2026-1001"]),
            canonical_source_url=overrides.pop("canonical_source_url", "https://nvd.nist.gov/vuln/detail/CVE-2026-1001"),
            external_ids=overrides.pop("external_ids", {"cve": "CVE-2026-1001"}),
            cve_id=overrides.pop("cve_id", "CVE-2026-1001"),
            cwe_id=overrides.pop("cwe_id", "CWE-79"),
            cvss_score=overrides.pop("cvss_score", 8.8),
            cvss_vector=overrides.pop("cvss_vector", "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
            severity=overrides.pop("severity", Severity.HIGH),
            affected_vendor=overrides.pop("affected_vendor", "ExampleAuto"),
            affected_product=overrides.pop("affected_product", "T-Box"),
            affected_version=overrides.pop("affected_version", "1.0"),
            vehicle_component=overrides.pop("vehicle_component", "tbox"),
            attack_surface=overrides.pop("attack_surface", "cellular"),
            exploit_status=overrides.pop("exploit_status", "proof_of_concept"),
            confidence=overrides.pop("confidence", "high"),
            risk_score=overrides.pop("risk_score", Decimal("87.50")),
            risk_level=overrides.pop("risk_level", RiskLevel.HIGH),
            tags=overrides.pop("tags", ["ota", "telematics"]),
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            dedup_key=overrides.pop("dedup_key", f"cve:CVE-2026-1001:{entry_id}"),
            normalized_text_hash=overrides.pop("normalized_text_hash", "hash-1001"),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status=overrides.pop("status", "active"),
            metadata_=overrides.pop(
                "metadata_",
                {
                    "score_metadata": {"base": 70, "token": "redacted"},
                    "score_explanation": "CVSS high severity and exposed cellular attack surface.",
                    "collector_headers": {"Authorization": "Bearer secret"},
                    "safe_note": "operator visible",
                },
            ),
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
            title=overrides.pop("title", "高风险车端情报命中"),
            threat_intelligence_id=entry.id,
            triggering_rule=overrides.pop("triggering_rule", "high-risk-tbox"),
            risk_level=overrides.pop("risk_level", entry.risk_level),
            triggered_at=overrides.pop("triggered_at", now),
            status=overrides.pop("status", AlertStatus.OPEN),
            notes=overrides.pop("notes", None),
            metadata_=overrides.pop("metadata_", {}),
            created_at=overrides.pop("created_at", now),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled alert overrides: {sorted(overrides)}")
        entry.alerts.append(alert)
        return alert

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is ThreatIntelligence:
            return self.entries.get(object_id)
        return None

    def scalars(self, statement):
        del statement
        return FakeScalarResult(self.entries.values())


def make_app(session: IntelligenceSession):
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


@pytest.mark.anyio
async def test_intelligence_routes_require_authentication():
    session = IntelligenceSession()
    session.seed_user()
    entry = session.seed_entry()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/intelligence")
        detail = await client.get(f"/intelligence/{entry.id}")

    assert listing.status_code == 401
    assert detail.status_code == 401
    assert listing.json()["error"]["code"] == "unauthorized"


@pytest.mark.anyio
async def test_intelligence_search_filters_normalized_fields_and_source_attribution():
    session = IntelligenceSession()
    user = session.seed_user()
    matching = session.seed_entry()
    session.seed_entry(
        title="Unrelated charging advisory",
        summary="Charging station exposure",
        intelligence_type=IntelligenceType.ADVISORY,
        source_names=["Vendor RSS"],
        source_urls=["https://vendor.example.test/advisory"],
        canonical_source_url="https://vendor.example.test/advisory",
        cve_id=None,
        severity=Severity.MEDIUM,
        affected_vendor="OtherAuto",
        affected_product="Charger",
        vehicle_component="charging",
        attack_surface="cloud_api",
        risk_level=RiskLevel.MEDIUM,
        tags=["charging"],
        status="under_review",
        dedup_key="vendor:charging",
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/intelligence",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "q": "cellular",
                "cve": "cve-2026-1001",
                "vendor": "exampleauto",
                "product": "T-Box",
                "vehicle_component": "tbox",
                "attack_surface": "cellular",
                "risk_level": "high",
                "tag": "ota",
                "source": "NVD",
                "status": "active",
                "intelligence_type": "vulnerability",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["has_next"] is False
    assert body["items"][0]["id"] == str(matching.id)
    assert body["items"][0]["source_names"] == ["NVD"]
    assert body["items"][0]["sources"][0]["source_url"].startswith("https://nvd.nist.gov/")
    assert body["items"][0]["risk_score"] == 87.5


@pytest.mark.anyio
async def test_intelligence_pagination_and_sorting_are_stable():
    session = IntelligenceSession()
    user = session.seed_user()
    base = datetime(2026, 5, 20, tzinfo=timezone.utc)
    high = session.seed_entry(
        title="High risk T-Box finding",
        cve_id="CVE-2026-2001",
        risk_score=Decimal("80.00"),
        severity=Severity.HIGH,
        last_seen_at=base - timedelta(days=2),
        dedup_key="risk:high",
    )
    critical = session.seed_entry(
        title="Critical IVI finding",
        cve_id="CVE-2026-2002",
        risk_score=Decimal("95.00"),
        severity=Severity.CRITICAL,
        vehicle_component="ivi",
        attack_surface="wifi",
        last_seen_at=base - timedelta(days=3),
        dedup_key="risk:critical",
    )
    medium = session.seed_entry(
        title="Medium OTA finding",
        cve_id="CVE-2026-2003",
        risk_score=Decimal("45.00"),
        severity=Severity.MEDIUM,
        vehicle_component="ota",
        attack_surface="cloud_api",
        last_seen_at=base - timedelta(days=1),
        dedup_key="risk:medium",
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_page = await client.get(
            "/intelligence",
            headers={"Authorization": f"Bearer {token}"},
            params={"sort": "risk_score", "page": 1, "limit": 2},
        )
        second_page = await client.get(
            "/intelligence",
            headers={"Authorization": f"Bearer {token}"},
            params={"sort": "risk_score", "page": 2, "limit": 2},
        )
        severity_sorted = await client.get(
            "/intelligence",
            headers={"Authorization": f"Bearer {token}"},
            params={"sort": "severity", "limit": 3},
        )

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["has_next"] is True
    assert [item["id"] for item in first_page.json()["items"]] == [str(critical.id), str(high.id)]
    assert second_page.json()["items"][0]["id"] == str(medium.id)
    assert second_page.json()["has_next"] is False
    assert [item["id"] for item in severity_sorted.json()["items"]] == [
        str(critical.id),
        str(high.id),
        str(medium.id),
    ]


@pytest.mark.anyio
async def test_intelligence_detail_includes_safe_metadata_scoring_and_alert_references():
    session = IntelligenceSession()
    user = session.seed_user()
    entry = session.seed_entry()
    entry.source_urls = ["https://nvd.nist.gov/vuln/detail/CVE-2026-1001?api_key=secret&ref=public"]
    entry.canonical_source_url = entry.source_urls[0]
    entry.source_links[0].source_url = entry.source_urls[0]
    entry.external_ids = {"cve": "CVE-2026-1001", "api_key": "secret"}
    entry.metadata_["callback"] = "https://nvd.nist.gov/vuln/detail/CVE-2026-1001#token=secret"
    alert = session.seed_alert(entry)
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/intelligence/{entry.id}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(entry.id)
    assert body["dedup_key"] == entry.dedup_key
    assert body["external_ids"] == {"cve": "CVE-2026-1001"}
    assert body["source_urls"] == ["https://nvd.nist.gov/vuln/detail/CVE-2026-1001?ref=public"]
    assert body["sources"][0]["source_url"] == "https://nvd.nist.gov/vuln/detail/CVE-2026-1001?ref=public"
    assert body["metadata"] == {
        "score_metadata": {"base": 70},
        "score_explanation": body["score_explanation"],
        "safe_note": "operator visible",
        "callback": "https://nvd.nist.gov/vuln/detail/CVE-2026-1001",
    }
    assert body["score_metadata"] == {"base": 70}
    assert body["score_explanation"] == "CVSS high severity and exposed cellular attack surface."
    assert "secret" not in response.text.lower()
    assert "authorization" not in response.text.lower()
    assert body["related_alert_count"] == 1
    assert body["related_alerts"][0]["id"] == str(alert.id)
    assert body["related_alerts"][0]["status"] == "open"


@pytest.mark.anyio
async def test_intelligence_detail_returns_deterministic_not_found():
    session = IntelligenceSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/intelligence/{uuid4()}", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "intelligence_not_found"
