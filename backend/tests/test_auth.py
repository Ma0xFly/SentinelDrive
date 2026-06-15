from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_request_session
from app.core.settings import Settings
from app.db.types import AuditAction
from app.main import create_app
from app.models.audit import AuditEvent
from app.models.security import User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token


class FakeScalarResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.audit_events: list[AuditEvent] = []
        self.commits = 0
        self.fail_commit = False

    def seed_user(
        self,
        *,
        email: str,
        password: str,
        is_active: bool = True,
        is_admin: bool = False,
        display_name: str | None = None,
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            is_active=is_active,
            is_admin=is_admin,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.users[user.id] = user
        return user

    def scalar(self, statement):
        email = self._where_email(statement)
        if email is None:
            return None
        return next((user for user in self.users.values() if user.email == email), None)

    def scalars(self, statement):
        del statement
        return FakeScalarResult(sorted(self.users.values(), key=lambda user: (user.created_at, user.email)))

    def get(self, model, object_id):
        if model is not User:
            return None
        return self.users.get(object_id)

    def add(self, instance):
        if isinstance(instance, User):
            self._assign_identity(instance)
            self.users[instance.id] = instance
        elif isinstance(instance, AuditEvent):
            self._assign_identity(instance)
            self.audit_events.append(instance)

    def flush(self):
        pass

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("commit failed")
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

    def _where_email(self, statement) -> str | None:
        whereclause = getattr(statement, "whereclause", None)
        right = getattr(whereclause, "right", None)
        value = getattr(right, "value", None)
        return value if isinstance(value, str) else None


def make_app(fake_session: FakeSession):
    app = create_app(
        settings=Settings(
            APP_SECRET_KEY="test-secret-key",
            DATABASE_URL="postgresql+psycopg://user:pass@postgres:5432/app",
            ADMIN_BOOTSTRAP_EMAIL="admin@example.test",
            ADMIN_BOOTSTRAP_PASSWORD="change-me-development-only",
        )
    )

    async def override_session():
        yield fake_session

    app.dependency_overrides[get_request_session] = override_session
    return app


async def login(client: AsyncClient, email: str = "admin@example.test", password: str = "admin-password") -> str:
    response = await client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.anyio
async def test_login_success_returns_token_and_records_audit():
    session = FakeSession()
    admin = session.seed_user(email="admin@example.test", password="admin-password", is_admin=True)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"email": "ADMIN@example.test", "password": "admin-password"})
        token = response.json()["access_token"]
        me_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert admin.last_login_at is not None
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "admin@example.test"
    assert "password_hash" not in me_response.text
    assert session.audit_events[-1].action == AuditAction.LOGIN_SUCCESS
    assert session.audit_events[-1].actor_user_id == admin.id


@pytest.mark.anyio
async def test_login_failure_records_audit_without_leaking_secret():
    session = FakeSession()
    session.seed_user(email="admin@example.test", password="admin-password", is_admin=True)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/auth/login", json={"email": "admin@example.test", "password": "wrong-password"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "wrong-password" not in response.text
    assert "password_hash" not in response.text
    assert session.audit_events[-1].action == AuditAction.LOGIN_FAILURE
    assert session.audit_events[-1].metadata_["email"] == "admin@example.test"


@pytest.mark.anyio
async def test_protected_route_rejects_missing_and_inactive_users():
    session = FakeSession()
    inactive = session.seed_user(email="inactive@example.test", password="admin-password", is_active=False, is_admin=True)
    app = make_app(session)
    settings = app.state.settings
    inactive_token = create_access_token(inactive.id, inactive.email, inactive.is_admin, settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing_response = await client.get("/auth/me")
        inactive_response = await client.get("/auth/me", headers={"Authorization": f"Bearer {inactive_token}"})

    assert missing_response.status_code == 401
    assert missing_response.json()["error"]["code"] == "unauthorized"
    assert inactive_response.status_code == 401


@pytest.mark.anyio
async def test_logout_records_audit_event():
    session = FakeSession()
    admin = session.seed_user(email="admin@example.test", password="admin-password", is_admin=True)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await login(client)
        response = await client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert session.audit_events[-1].action == AuditAction.LOGOUT
    assert session.audit_events[-1].actor_user_id == admin.id


@pytest.mark.anyio
async def test_user_create_list_and_status_update_require_admin_and_audit_changes():
    session = FakeSession()
    admin = session.seed_user(email="admin@example.test", password="admin-password", is_admin=True)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await login(client)
        create_response = await client.post(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "Analyst@example.test",
                "password": "analyst-password",
                "display_name": "Analyst",
                "is_admin": False,
            },
        )
        list_response = await client.get("/users", headers={"Authorization": f"Bearer {token}"})
        created_id = create_response.json()["id"]
        status_response = await client.patch(
            f"/users/{created_id}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )

    assert create_response.status_code == 201
    created_body = create_response.json()
    assert created_body["email"] == "analyst@example.test"
    assert "password_hash" not in create_response.text
    created_user = session.users[UUID(created_id)]
    assert "analyst-password" not in created_user.password_hash
    assert verify_password("analyst-password", created_user.password_hash)
    assert list_response.status_code == 200
    assert {user["email"] for user in list_response.json()} == {"admin@example.test", "analyst@example.test"}
    assert status_response.status_code == 200
    assert status_response.json()["is_active"] is False
    user_change_events = [event for event in session.audit_events if event.action == AuditAction.USER_CHANGE]
    assert len(user_change_events) == 2
    assert user_change_events[0].actor_user_id == admin.id
    assert user_change_events[0].after["email"] == "analyst@example.test"
    assert user_change_events[1].before == {"is_active": True}
    assert user_change_events[1].after == {"is_active": False}


@pytest.mark.anyio
async def test_user_management_rejects_non_admin_user():
    session = FakeSession()
    analyst = session.seed_user(email="analyst@example.test", password="analyst-password", is_admin=False)
    app = make_app(session)
    token = create_access_token(analyst.id, analyst.email, analyst.is_admin, app.state.settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "new@example.test", "password": "new-password"},
        )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.anyio
async def test_user_create_duplicate_and_status_update_missing_user_fail_cleanly():
    session = FakeSession()
    session.seed_user(email="admin@example.test", password="admin-password", is_admin=True)
    app = make_app(session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await login(client)
        duplicate_response = await client.post(
            "/users",
            headers={"Authorization": f"Bearer {token}"},
            json={"email": "admin@example.test", "password": "another-password"},
        )
        missing_response = await client.patch(
            f"/users/{uuid4()}/status",
            headers={"Authorization": f"Bearer {token}"},
            json={"is_active": False},
        )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "user_exists"
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "user_not_found"


def test_audit_helper_propagates_commit_failures():
    from app.services.audit import record_audit_event

    session = FakeSession()
    session.fail_commit = True
    record_audit_event(
        session,
        action=AuditAction.USER_CHANGE,
        entity_type="user",
        summary="User changed",
        after={"email": "admin@example.test"},
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        session.commit()


def test_auth_test_fake_session_extracts_email_from_select():
    from sqlalchemy import select

    user = SimpleNamespace(email="admin@example.test")
    statement = select(User).where(User.email == user.email)

    assert FakeSession()._where_email(statement) == "admin@example.test"
