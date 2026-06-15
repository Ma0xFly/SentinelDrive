from uuid import UUID

from sqlalchemy.orm import Session

from app.db.types import AuditAction
from app.models.audit import AuditEvent


def record_audit_event(
    session: Session,
    *,
    action: AuditAction,
    entity_type: str,
    summary: str,
    actor_user_id: UUID | None = None,
    entity_id: UUID | None = None,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
        before=before,
        after=after,
        metadata_=metadata or {},
    )
    session.add(event)
    return event
