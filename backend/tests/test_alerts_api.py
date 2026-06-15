from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import AlertStatus, AuditAction, IntelligenceType, ProcessingStatus, RiskLevel, Severity
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.intelligence import ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import Alert, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services.alerts import create_alerts_for_intelligence, evaluate_and_create_alerts


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class AlertSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.alerts: dict[UUID, Alert] = {}
        self.audit_events: list[AuditEvent] = []
        self.commits = 0

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
        entry_id = overrides.pop("id", uuid4())
        first_seen_at = overrides.pop("first_seen_at", now - timedelta(hours=1))
        last_seen_at = overrides.pop("last_seen_at", now)
        source_names = overrides.pop("source_names", ["NVD"])
        source_urls = overrides.pop("source_urls", ["https://nvd.nist.gov/vuln/detail/CVE-2026-3001"])
        entry = ThreatIntelligence(
            id=entry_id,
            raw_intelligence_id=overrides.pop("raw_intelligence_id", uuid4()),
            title=overrides.pop("title", "CVE-2026-3001 affects vehicle T-Box"),
            summary=overrides.pop("summary", "Remote unauthenticated exploit path."),
            intelligence_type=overrides.pop("intelligence_type", IntelligenceType.VULNERABILITY),
            source_names=source_names,
            source_urls=source_urls,
            canonical_source_url=overrides.pop("canonical_source_url", source_urls[0]),
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
            last_seen_at=last_seen_at,
            dedup_key=overrides.pop("dedup_key", f"alert-test:{entry_id}"),
            normalized_text_hash=overrides.pop("normalized_text_hash", f"hash-{entry_id}"),
            processing_status=overrides.pop("processing_status", ProcessingStatus.NORMALIZED),
            status=overrides.pop("status", "active"),
            metadata_=overrides.pop(
                "metadata_",
                {
                    "scoring": {
                        "rule_version": "fixed-risk-v1",
                        "signals": {"known_exploited": False, "vehicle_component": "tbox"},
                    },
                    "token": "redacted",
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
            title=overrides.pop("title", "关键风险情报"),
            threat_intelligence_id=entry.id,
            triggering_rule=overrides.pop("triggering_rule", "critical-intelligence"),
            risk_level=overrides.pop("risk_level", entry.risk_level),
            triggered_at=overrides.pop("triggered_at", now),
            status=overrides.pop("status", AlertStatus.OPEN),
            notes=overrides.pop("notes", None),
            metadata_=overrides.pop("metadata_", {"secret": "redacted", "reason": "critical"}),
            created_at=overrides.pop("created_at", now),
            updated_at=overrides.pop("updated_at", now),
        )
        if overrides:
            raise AssertionError(f"Unhandled alert overrides: {sorted(overrides)}")
        self.add(alert)
        return alert

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is ThreatIntelligence:
            return self.entries.get(object_id)
        if model is Alert:
            return self.alerts.get(object_id)
        return None

    def scalar(self, statement):
        del statement
        return None

    def scalars(self, statement):
        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity is Alert:
            return FakeScalarResult(self.alerts.values())
        if entity is ThreatIntelligence:
            for criterion in getattr(statement, "_where_criteria", ()):
                value = getattr(getattr(criterion, "right", None), "value", None)
                if value in self.entries:
                    return FakeScalarResult([self.entries[value]])
        return FakeScalarResult(self.entries.values())

    def add(self, instance):
        self._assign_identity(instance)
        if isinstance(instance, User):
            self.users[instance.id] = instance
        elif isinstance(instance, ThreatIntelligence):
            self.entries[instance.id] = instance
        elif isinstance(instance, Alert):
            self.alerts[instance.id] = instance
            entry = self.entries.get(instance.threat_intelligence_id)
            if entry is not None:
                instance.intelligence = entry
                if instance not in entry.alerts:
                    entry.alerts.append(instance)
        elif isinstance(instance, AuditEvent):
            self.audit_events.append(instance)

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
        if isinstance(instance, Alert) and instance.metadata_ is None:
            instance.metadata_ = {}
        if isinstance(instance, AuditEvent) and instance.metadata_ is None:
            instance.metadata_ = {}


def make_app(session: AlertSession):
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


def test_alert_service_creates_expected_rules_and_avoids_duplicates():
    session = AlertSession()
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    entry = session.seed_entry(
        source_names=["NVD", "CISA KEV"],
        source_urls=["https://nvd.test/CVE-2026-3001", "https://cisa.test/kev/CVE-2026-3001"],
        exploit_status="exploited",
        tags=["cisa-kev"],
        metadata_={"scoring": {"signals": {"known_exploited": True, "vehicle_component": "tbox"}}},
        first_seen_at=now,
        last_seen_at=now,
    )

    first = create_alerts_for_intelligence(session, entry, entries=[entry], now=now)
    second = create_alerts_for_intelligence(session, entry, entries=[entry], now=now)

    assert {alert.triggering_rule for alert in first} == {
        "critical-intelligence",
        "known-exploited",
        "vehicle-critical-tbox",
        "multi-source-cve-CVE-2026-3001",
    }
    assert second == []


def test_alert_service_detects_vendor_or_component_bursts():
    session = AlertSession()
    base = datetime(2026, 5, 20, tzinfo=timezone.utc)
    entries = [
        session.seed_entry(cve_id=f"CVE-2026-31{index:02d}", first_seen_at=base - timedelta(days=index), dedup_key=f"burst:{index}")
        for index in range(3)
    ]

    created = create_alerts_for_intelligence(session, entries[0], entries=entries, now=base)

    assert any(alert.triggering_rule == "burst-vendor-exampleauto" for alert in created)


def test_alert_service_targeted_evaluation_uses_context_entries_for_cross_record_rules():
    session = AlertSession()
    base = datetime(2026, 5, 20, tzinfo=timezone.utc)
    target = session.seed_entry(
        cve_id="CVE-2026-3999",
        source_names=["NVD"],
        source_urls=["https://nvd.test/CVE-2026-3999"],
        first_seen_at=base,
        last_seen_at=base,
        dedup_key="targeted:target",
    )
    session.seed_entry(
        cve_id="CVE-2026-3999",
        source_names=["CISA KEV"],
        source_urls=["https://cisa.test/CVE-2026-3999"],
        first_seen_at=base - timedelta(days=1),
        last_seen_at=base - timedelta(days=1),
        dedup_key="targeted:context",
    )

    created = evaluate_and_create_alerts(session, intelligence_id=target.id)

    assert any(alert.triggering_rule == "multi-source-cve-CVE-2026-3999" for alert in created)


@pytest.mark.anyio
async def test_alert_routes_require_authentication():
    session = AlertSession()
    entry = session.seed_entry()
    alert = session.seed_alert(entry)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/alerts")
        detail = await client.get(f"/alerts/{alert.id}")
        update = await client.patch(f"/alerts/{alert.id}/status", json={"status": "closed"})
        evaluate = await client.post("/alerts/evaluate", json={"intelligence_id": str(entry.id)})

    assert listing.status_code == 401
    assert detail.status_code == 401
    assert update.status_code == 401
    assert evaluate.status_code == 401


@pytest.mark.anyio
async def test_alert_evaluate_endpoint_creates_alerts_and_preserves_intelligence_detail_refs():
    session = AlertSession()
    user = session.seed_user()
    entry = session.seed_entry()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/alerts/evaluate",
            headers=auth_header(token),
            json={"intelligence_id": str(entry.id)},
        )
        duplicate = await client.post(
            "/alerts/evaluate",
            headers=auth_header(token),
            json={"intelligence_id": str(entry.id)},
        )
        detail = await client.get(f"/intelligence/{entry.id}", headers=auth_header(token))

    assert created.status_code == 200
    assert created.json()["created"] >= 2
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] == 0
    assert detail.status_code == 200
    assert detail.json()["related_alert_count"] == created.json()["created"]
    assert {alert["status"] for alert in detail.json()["related_alerts"]} == {"open"}


@pytest.mark.anyio
async def test_alert_list_detail_filters_sorting_and_redaction():
    session = AlertSession()
    user = session.seed_user()
    entry = session.seed_entry(
        source_urls=["https://nvd.test/CVE-2026-3001?api_key=secret&ref=public"],
        canonical_source_url="https://nvd.test/CVE-2026-3001?api_key=secret&ref=public",
    )
    critical = session.seed_alert(
        entry,
        triggering_rule="critical-intelligence",
        metadata_={"reason": "critical", "token": "secret"},
        triggered_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
    )
    session.seed_alert(
        entry,
        triggering_rule="known-exploited",
        risk_level=RiskLevel.HIGH,
        triggered_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
    )
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get(
            "/alerts",
            headers=auth_header(token),
            params={"risk_level": "critical", "status": "open", "triggering_rule": "critical", "sort": "risk_level"},
        )
        detail = await client.get(f"/alerts/{critical.id}", headers=auth_header(token))

    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == str(critical.id)
    assert detail.status_code == 200
    body = detail.json()
    assert body["metadata"] == {"reason": "critical"}
    assert body["intelligence"]["source_urls"] == ["https://nvd.test/CVE-2026-3001?ref=public"]
    assert body["intelligence"]["sources"][0]["source_url"] == "https://nvd.test/CVE-2026-3001?ref=public"
    assert "secret" not in detail.text.lower()


@pytest.mark.anyio
async def test_alert_list_invalid_intelligence_id_returns_structured_error():
    session = AlertSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/alerts",
            headers=auth_header(token),
            params={"intelligence_id": "   "},
        )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_intelligence_id",
        "message": "情报 ID 格式无效。",
    }


@pytest.mark.anyio
async def test_alert_status_update_is_audited_and_rejects_secret_notes():
    session = AlertSession()
    user = session.seed_user()
    entry = session.seed_entry()
    alert = session.seed_alert(entry, status=AlertStatus.OPEN)
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_notes = await client.patch(
            f"/alerts/{alert.id}/status",
            headers=auth_header(token),
            json={"status": "acknowledged", "notes": "token=secret"},
        )
        updated = await client.patch(
            f"/alerts/{alert.id}/status",
            headers=auth_header(token),
            json={"status": "closed", "notes": "已处理"},
        )

    assert bad_notes.status_code == 422
    assert updated.status_code == 200
    assert updated.json()["status"] == "closed"
    assert updated.json()["notes"] == "已处理"
    assert session.audit_events[-1].action == AuditAction.ALERT_CLOSURE
    assert session.audit_events[-1].actor_user_id == user.id
    assert session.audit_events[-1].entity_id == alert.id
    assert session.audit_events[-1].before["status"] == "open"
    assert session.audit_events[-1].after["status"] == "closed"


@pytest.mark.anyio
async def test_alert_status_update_preserves_notes_when_omitted_and_clears_when_null():
    session = AlertSession()
    user = session.seed_user()
    entry = session.seed_entry()
    alert = session.seed_alert(entry, status=AlertStatus.OPEN, notes="保留备注")
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        preserved = await client.patch(
            f"/alerts/{alert.id}/status",
            headers=auth_header(token),
            json={"status": "acknowledged"},
        )
        cleared = await client.patch(
            f"/alerts/{alert.id}/status",
            headers=auth_header(token),
            json={"status": "closed", "notes": None},
        )

    assert preserved.status_code == 200
    assert preserved.json()["notes"] == "保留备注"
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None


@pytest.mark.anyio
async def test_alert_missing_paths_return_deterministic_404s():
    session = AlertSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_alert = await client.get(f"/alerts/{uuid4()}", headers=auth_header(token))
        missing_intelligence = await client.post(
            "/alerts/evaluate",
            headers=auth_header(token),
            json={"intelligence_id": str(uuid4())},
        )

    assert missing_alert.status_code == 404
    assert missing_alert.json()["error"]["code"] == "alert_not_found"
    assert missing_intelligence.status_code == 404
    assert missing_intelligence.json()["error"]["code"] == "intelligence_not_found"
