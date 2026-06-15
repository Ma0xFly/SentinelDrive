from sqlalchemy import select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.db.types import AuditAction
from app.models.security import User
from app.security.passwords import hash_password, verify_password
from app.services.audit import record_audit_event


def bootstrap_admin() -> None:
    settings = get_settings()
    email = settings.admin_bootstrap_email.strip().lower()
    password = settings.admin_bootstrap_password.get_secret_value()

    if not email:
        raise ValueError("ADMIN_BOOTSTRAP_EMAIL must not be empty")
    if not password:
        raise ValueError("ADMIN_BOOTSTRAP_PASSWORD must not be empty")

    with SessionLocal() as session:
        existing = session.scalar(select(User).where(User.email == email))
        if existing is None:
            user = User(
                email=email,
                password_hash=hash_password(password),
                display_name="Administrator",
                is_active=True,
                is_admin=True,
            )
            session.add(user)
            session.flush()
            record_audit_event(
                session,
                action=AuditAction.USER_CHANGE,
                entity_type="user",
                summary="Initial admin user created",
                entity_id=user.id,
                after={"email": email, "is_active": True, "is_admin": True},
            )
            session.commit()
            print(f"Admin user created: {email}")
            return

        password_needs_update = not verify_password(password, existing.password_hash)
        if not existing.is_admin or not existing.is_active or password_needs_update:
            before = {
                "is_active": existing.is_active,
                "is_admin": existing.is_admin,
                "password_updated": False,
            }
            existing.is_admin = True
            existing.is_active = True
            if password_needs_update:
                existing.password_hash = hash_password(password)
            record_audit_event(
                session,
                action=AuditAction.USER_CHANGE,
                entity_type="user",
                summary="Initial admin user updated",
                entity_id=existing.id,
                before=before,
                after={
                    "email": email,
                    "is_active": True,
                    "is_admin": True,
                    "password_updated": password_needs_update,
                },
            )
            session.commit()
            print(f"Admin user updated: {email}")
            return

        print(f"Admin user already exists: {email}")


if __name__ == "__main__":
    bootstrap_admin()
