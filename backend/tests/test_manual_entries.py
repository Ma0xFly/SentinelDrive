from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import AuditAction
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.intelligence import RawIntelligence, ThreatIntelligence, ThreatIntelligenceSource
from app.models.security import User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class ManualEntrySession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.raw_items: dict[UUID, RawIntelligence] = {}
        self.entries: dict[UUID, ThreatIntelligence] = {}
        self.source_links: list[ThreatIntelligenceSource] = []
        self.audit_events: list[AuditEvent] = []
        self.commits = 0

    def seed_user(
        self,
        *,
        email: str = "analyst@example.test",
        password: str = "analyst-password",
        is_active: bool = True,
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            is_active=is_active,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
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
        dedup_key = self._where_value(statement)
        if dedup_key is None:
            return None
        return next((entry for entry in self.entries.values() if entry.dedup_key == dedup_key), None)

    def scalars(self, statement):
        del statement
        manual_entries = [
            entry
            for entry in self.entries.values()
            if entry.metadata_.get("entry_origin") == "manual" or "manual" in entry.tags
        ]
        return FakeScalarResult(sorted(manual_entries, key=lambda entry: entry.last_seen_at, reverse=True))

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
            if instance.tags is None:
                instance.tags = []
            if instance.source_links is None:
                instance.source_links = []
            if instance.metadata_ is None:
                instance.metadata_ = {}
        if isinstance(instance, RawIntelligence) and instance.metadata_ is None:
            instance.metadata_ = {}
        if isinstance(instance, AuditEvent) and instance.metadata_ is None:
            instance.metadata_ = {}

    def _where_value(self, statement) -> str | None:
        whereclause = getattr(statement, "whereclause", None)
        right = getattr(whereclause, "right", None)
        value = getattr(right, "value", None)
        return value if isinstance(value, str) else None


def make_app(session: ManualEntrySession):
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


def manual_payload(**overrides):
    payload = {
        "category": "vulnerability",
        "title": "CVE-2026-0001 affects T-Box firmware",
        "summary": "Manual analyst finding for an affected telematics firmware.",
        "source_name": "Analyst Desk",
        "source_url": "https://example.test/research/cve-2026-0001",
        "cve_id": "CVE-2026-0001",
        "severity": "high",
        "affected_vendor": "ExampleAuto",
        "affected_product": "T-Box",
        "vehicle_component": "tbox",
        "attack_surface": "cellular",
        "risk_level": "high",
        "tags": ["Manual", "TBox"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.anyio
async def test_manual_entry_requires_authentication():
    session = ManualEntrySession()
    session.seed_user()
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/manual-entries", json=manual_payload())

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert not session.entries


@pytest.mark.anyio
async def test_manual_entry_validation_rejects_bad_cve_and_missing_source():
    session = ManualEntrySession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        bad_cve = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(cve_id="2026-0001"),
        )
        missing_source = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(cve_id=None, source_name=None, source_url=None),
        )

    assert bad_cve.status_code == 422
    assert missing_source.status_code == 422
    assert not session.entries


@pytest.mark.anyio
async def test_manual_entry_create_persists_normalized_records_and_audit():
    session = ManualEntrySession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "vulnerability"
    assert body["intelligence_type"] == "vulnerability"
    assert body["cve_id"] == "CVE-2026-0001"
    assert body["source_name"] == "Analyst Desk"
    assert body["source_url"] == "https://example.test/research/cve-2026-0001"
    assert body["dedup_key"] == "manual:cve:CVE-2026-0001"
    assert body["tags"] == ["manual", "tbox", "vulnerability"]
    assert len(session.raw_items) == 1
    assert len(session.entries) == 1
    assert len(session.source_links) == 1
    entry = next(iter(session.entries.values()))
    assert entry.raw_item is not None
    assert entry.metadata_["entry_origin"] == "manual"
    assert entry.source_links[0].source_url == body["source_url"]
    assert session.audit_events[-1].action == AuditAction.MANUAL_ENTRY
    assert session.audit_events[-1].actor_user_id == user.id
    assert session.audit_events[-1].entity_id == entry.id


@pytest.mark.anyio
async def test_manual_entry_duplicate_returns_existing_record_without_new_core_entry():
    session = ManualEntrySession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(),
        )
        second = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(title="Different title but same CVE"),
        )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(session.entries) == 1
    assert len(session.raw_items) == 1
    assert session.audit_events[-1].metadata_["duplicate"] is True


@pytest.mark.anyio
async def test_manual_entry_list_detail_and_status_update():
    session = ManualEntrySession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(category="research_leads", cve_id=None, title="Investigate public charger exposure"),
        )
        entry_id = created.json()["id"]
        listing = await client.get("/manual-entries", headers={"Authorization": f"Bearer {token}"})
        detail = await client.get(f"/manual-entries/{entry_id}", headers={"Authorization": f"Bearer {token}"})
        updated = await client.patch(
            f"/manual-entries/{entry_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"status": "resolved", "tags": ["charging", "triaged"]},
        )

    assert created.status_code == 201
    assert created.json()["category"] == "research_lead"
    assert created.json()["intelligence_type"] == "advisory"
    assert created.json()["status"] == "under_review"
    assert "research_lead" in created.json()["tags"]
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [entry_id]
    assert detail.status_code == 200
    assert detail.json()["id"] == entry_id
    assert updated.status_code == 200
    assert updated.json()["status"] == "resolved"
    assert updated.json()["tags"] == ["charging", "manual", "research_lead", "triaged"]
    assert session.audit_events[-1].action == AuditAction.STATUS_CHANGE
    assert session.audit_events[-1].before["status"] == "under_review"
    assert session.audit_events[-1].after["status"] == "resolved"


@pytest.mark.anyio
async def test_manual_entry_update_rejects_dedup_collision():
    session = ManualEntrySession()
    user = session.seed_user()
    app = make_app(session)
    token = token_for(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(cve_id="CVE-2026-0001"),
        )
        second = await client.post(
            "/manual-entries",
            headers={"Authorization": f"Bearer {token}"},
            json=manual_payload(cve_id="CVE-2026-0002", title="Second manual finding"),
        )
        collision = await client.patch(
            f"/manual-entries/{second.json()['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"cve_id": first.json()["cve_id"]},
        )

    assert collision.status_code == 409
    assert collision.json()["error"]["code"] == "manual_entry_duplicate"
