from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_request_session, require_admin_user
from app.api.schemas.auth import UserCreateRequest, UserResponse, UserStatusUpdateRequest
from app.db.types import AuditAction
from app.models.security import User
from app.security.passwords import hash_password
from app.services.audit import record_audit_event

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin_user),
    session: Session = Depends(get_request_session),
) -> list[User]:
    del current_user
    return list(session.scalars(select(User).order_by(User.created_at, User.email)).all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    current_user: User = Depends(require_admin_user),
    session: Session = Depends(get_request_session),
) -> User:
    email = payload.email.lower()
    existing = session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "user_exists", "message": "用户已存在。"}},
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_active=True,
        is_admin=payload.is_admin,
    )
    session.add(user)
    session.flush()
    record_audit_event(
        session,
        action=AuditAction.USER_CHANGE,
        entity_type="user",
        summary="User created",
        actor_user_id=current_user.id,
        entity_id=user.id,
        after={
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
        },
    )
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: UUID,
    payload: UserStatusUpdateRequest,
    current_user: User = Depends(require_admin_user),
    session: Session = Depends(get_request_session),
) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "user_not_found", "message": "用户不存在。"}},
        )

    before = {"is_active": user.is_active}
    user.is_active = payload.is_active
    record_audit_event(
        session,
        action=AuditAction.USER_CHANGE,
        entity_type="user",
        summary="User status updated",
        actor_user_id=current_user.id,
        entity_id=user.id,
        before=before,
        after={"is_active": user.is_active},
    )
    session.commit()
    session.refresh(user)
    return user
