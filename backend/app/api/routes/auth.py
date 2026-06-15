from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_session, get_request_settings
from app.api.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.core.settings import Settings
from app.db.types import AuditAction
from app.models.security import User
from app.security.passwords import verify_password
from app.security.tokens import create_access_token
from app.services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Session = Depends(get_request_session),
    settings: Settings = Depends(get_request_settings),
) -> TokenResponse:
    email = payload.email.lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        record_audit_event(
            session,
            action=AuditAction.LOGIN_FAILURE,
            entity_type="user",
            summary="Failed login attempt",
            entity_id=user.id if user else None,
            metadata={"email": email, "client": _client_host(request)},
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "invalid_credentials", "message": "邮箱或密码无效。"}},
        )

    user.last_login_at = datetime.now(timezone.utc)
    record_audit_event(
        session,
        action=AuditAction.LOGIN_SUCCESS,
        entity_type="user",
        summary="User logged in",
        actor_user_id=user.id,
        entity_id=user.id,
        metadata={"client": _client_host(request)},
    )
    session.commit()
    session.refresh(user)
    return TokenResponse(
        access_token=create_access_token(user.id, user.email, user.is_admin, settings),
    )


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> dict[str, str]:
    record_audit_event(
        session,
        action=AuditAction.LOGOUT,
        entity_type="user",
        summary="User logged out",
        actor_user_id=current_user.id,
        entity_id=current_user.id,
        metadata={"client": _client_host(request)},
    )
    session.commit()
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None
