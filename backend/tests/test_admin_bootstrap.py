from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.settings import Settings
from app.db.types import AuditAction
from app.models.audit import AuditEvent
from app.models.security import User
from app.scripts import admin_bootstrap
from app.security.passwords import hash_password, verify_password


class BootstrapSession:
    def __init__(self):
        self.users: dict[UUID, User] = {}
        self.audit_events: list[AuditEvent] = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def seed_user(
        self,
        *,
        email: str,
        password: str,
        is_active: bool,
        is_admin: bool,
    ) -> User:
        user = User(
            id=uuid4(),
            email=email,
            password_hash=hash_password(password),
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
        self.commits += 1

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


def bootstrap_settings() -> Settings:
    return Settings(
        APP_SECRET_KEY="test-secret-key",
        DATABASE_URL="postgresql+psycopg://user:pass@postgres:5432/app",
        ADMIN_BOOTSTRAP_EMAIL="admin@example.test",
        ADMIN_BOOTSTRAP_PASSWORD="admin-password",
    )


def test_bootstrap_creates_admin_with_hashed_password_and_audit(monkeypatch, capsys):
    session = BootstrapSession()
    monkeypatch.setattr(admin_bootstrap, "get_settings", bootstrap_settings)
    monkeypatch.setattr(admin_bootstrap, "SessionLocal", lambda: session)

    admin_bootstrap.bootstrap_admin()

    admin = next(iter(session.users.values()))
    assert admin.email == "admin@example.test"
    assert admin.is_active is True
    assert admin.is_admin is True
    assert "admin-password" not in admin.password_hash
    assert verify_password("admin-password", admin.password_hash)
    assert session.audit_events[-1].action == AuditAction.USER_CHANGE
    assert session.audit_events[-1].entity_id == admin.id
    assert "admin-password" not in str(session.audit_events[-1].after)
    assert "Admin user created: admin@example.test" in capsys.readouterr().out


def test_bootstrap_repairs_existing_admin_and_updates_configured_password(monkeypatch, capsys):
    session = BootstrapSession()
    existing = session.seed_user(
        email="admin@example.test",
        password="old-password",
        is_active=False,
        is_admin=False,
    )
    monkeypatch.setattr(admin_bootstrap, "get_settings", bootstrap_settings)
    monkeypatch.setattr(admin_bootstrap, "SessionLocal", lambda: session)

    admin_bootstrap.bootstrap_admin()

    assert existing.is_active is True
    assert existing.is_admin is True
    assert verify_password("admin-password", existing.password_hash)
    assert not verify_password("old-password", existing.password_hash)
    assert session.audit_events[-1].before == {
        "is_active": False,
        "is_admin": False,
        "password_updated": False,
    }
    assert session.audit_events[-1].after == {
        "email": "admin@example.test",
        "is_active": True,
        "is_admin": True,
        "password_updated": True,
    }
    assert "Admin user updated: admin@example.test" in capsys.readouterr().out
