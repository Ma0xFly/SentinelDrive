from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import AuditAction, ProcessingStatus, RiskLevel, Severity
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.intelligence import RawIntelligence, ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class IngestSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.raw_items: dict[UUID, RawIntelligence] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.source_links: list[ThreatIntelligenceSource] = []
        self.audit_events: list[AuditEvent] = []
        self.commits = 0

    def seed_user(self) -> User:
        now = datetime.now(timezone.utc)
        user = User(
            id=uuid4(),
            email="analyst@example.test",
            password_hash=hash_password("analyst-password"),
            display_name="Analyst",
            is_active=True,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self.users[user.id] = user
        return user

    def get(self, model, object_id):
        if model is User:
            return self.users.get(object_id)
        if model is ThreatIntelligence:
            return self.entries.get(object_id)
        return None

    def scalar(self, statement):
        params = set(getattr(statement.compile(), "params", {}).values())
        for entry in self.entries.values():
            if entry.cve_id and entry.cve_id in params:
                return entry
            if entry.dedup_key and entry.dedup_key in params:
                return entry
            for link in entry.source_links or []:
                if link.external_id in params and link.source_url in params:
                    return entry
        return None

    def add(self, instance):
        self._assign_identity(instance)
        if isinstance(instance, User):
            self.users[instance.id] = instance
        elif isinstance(instance, RawIntelligence):
            self.raw_items[instance.id] = instance
        elif isinstance(instance, ThreatIntelligence):
            self.entries[instance.id] = instance
        elif isinstance(instance, ThreatIntelligenceSource):
            self.source_links.append(instance)
            entry = self.entries.get(instance.threat_intelligence_id)
            if entry is not None:
                entry.source_links.append(instance)
        elif isinstance(instance, AuditEvent):
            self.audit_events.append(instance)

    def flush(self):
        for entry in self.entries.values():
            if entry.raw_intelligence_id and entry.raw_item is None:
                entry.raw_item = self.raw_items.get(entry.raw_intelligence_id)

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
        if isinstance(instance, ThreatIntelligence):
            if instance.source_links is None:
                instance.source_links = []
            if instance.alerts is None:
                instance.alerts = []
            if instance.metadata_ is None:
                instance.metadata_ = {}
        if isinstance(instance, RawIntelligence) and instance.metadata_ is None:
            instance.metadata_ = {}
        if isinstance(instance, AuditEvent) and instance.metadata_ is None:
            instance.metadata_ = {}


def make_app(session: IngestSession):
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


def ingest_payload(**overrides):
    payload = {
        "source_name": "AI Collector",
        "source_url": "https://intel.example.test/items/CVE-2026-9001?api_key=secret&ref=public",
        "platform": "weixin",
        "title": "CVE-2026-9001 affects vehicle cloud API",
        "summary": "AI整理的车联网云端 API 漏洞线索。",
        "description": "Research note for exposed API behavior.",
        "external_id": "wx-9001",
        "cve_id": "cve-2026-9001",
        "affected_vendor": "ExampleAuto",
        "affected_products": ["Cloud Gateway", "Cloud Gateway"],
        "components": ["Cloud API"],
        "attack_surfaces": ["cloud_api"],
        "severity": "high",
        "external_score": 8.8,
        "published_at": "2026-06-01T00:00:00Z",
        "collected_at": "2026-06-15T00:00:00Z",
        "raw_payload": {
            "safe": "visible",
            "authorization": "Bearer secret",
            "nested": {"token": "secret", "note": "safe"},
        },
        "tags": ["AI", "Cloud"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.anyio
async def test_intelligence_ingest_requires_authentication():
    session = IngestSession()
    session.seed_user()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/intelligence/ingest", json=ingest_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert not session.entries


@pytest.mark.anyio
async def test_intelligence_ingest_creates_normalized_records_and_audit():
    session = IngestSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/intelligence/ingest", headers=auth_header(token), json=ingest_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "created"
    assert body["duplicate"] is False
    assert body["dedup_key"] == "cve:CVE-2026-9001"
    assert body["source_url"] == "https://intel.example.test/items/CVE-2026-9001?ref=public"
    assert body["message"] == "外部情报已接收。"
    assert len(session.raw_items) == 1
    assert len(session.entries) == 1
    assert len(session.source_links) == 1
    entry = next(iter(session.entries.values()))
    raw_item = next(iter(session.raw_items.values()))
    assert entry.raw_intelligence_id == raw_item.id
    assert entry.cve_id == "CVE-2026-9001"
    assert entry.severity == Severity.HIGH
    assert entry.risk_level == RiskLevel.HIGH
    assert entry.processing_status == ProcessingStatus.NORMALIZED
    assert entry.metadata_["entry_origin"] == "external_ingest"
    assert entry.metadata_["affected_products"] == ["cloud gateway"]
    assert raw_item.raw_content == {"safe": "visible", "nested": {"note": "safe"}}
    assert session.audit_events[-1].action == AuditAction.MANUAL_ENTRY
    assert session.audit_events[-1].entity_id == entry.id
    assert "secret" not in response.text.lower()


@pytest.mark.anyio
async def test_intelligence_ingest_duplicate_cve_updates_existing_without_new_core_record():
    session = IngestSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/intelligence/ingest", headers=auth_header(token), json=ingest_payload())
        second = await client.post(
            "/intelligence/ingest",
            headers=auth_header(token),
            json=ingest_payload(title="Different title for same CVE", external_id="wx-9001-repeat"),
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["duplicate"] is True
    assert second.json()["status"] == "updated"
    assert len(session.entries) == 1
    assert len(session.raw_items) == 1
    assert session.audit_events[-1].metadata_["duplicate"] is True
    entry = next(iter(session.entries.values()))
    assert sorted(entry.external_ids) == ["cve_id", "external_id"]
    assert len(entry.source_links) == 1


@pytest.mark.anyio
async def test_intelligence_ingest_duplicate_external_id_without_cve_reuses_existing_record():
    session = IngestSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)
    payload = ingest_payload(cve_id=None, external_id="platform-incident-42", title="Vehicle cloud exposure lead")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/intelligence/ingest", headers=auth_header(token), json=payload)
        second = await client.post("/intelligence/ingest", headers=auth_header(token), json=payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["duplicate"] is True
    assert len(session.entries) == 1
    assert len(session.raw_items) == 1


@pytest.mark.anyio
async def test_intelligence_ingest_validates_required_fields_and_rejects_sensitive_text():
    session = IngestSession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_title = await client.post(
            "/intelligence/ingest",
            headers=auth_header(token),
            json=ingest_payload(title=None),
        )
        bad_url = await client.post(
            "/intelligence/ingest",
            headers=auth_header(token),
            json=ingest_payload(source_url="not-a-url"),
        )
        secret_text = await client.post(
            "/intelligence/ingest",
            headers=auth_header(token),
            json=ingest_payload(summary="token=secret"),
        )

    assert missing_title.status_code == 422
    assert bad_url.status_code == 422
    assert secret_text.status_code == 422
    assert not session.entries
