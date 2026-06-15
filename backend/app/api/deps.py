from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db.session import SessionLocal
from app.models.security import User
from app.security.tokens import TokenError, decode_access_token
from app.services.pipeline import PipelineTaskClient

bearer_scheme = HTTPBearer(auto_error=False)


async def get_request_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


async def get_request_session():
    with SessionLocal() as session:
        yield session


async def get_pipeline_task_client(settings: Settings = Depends(get_request_settings)) -> PipelineTaskClient:
    return PipelineTaskClient(settings)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_request_session),
    settings: Settings = Depends(get_request_settings),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _auth_error()

    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError, TokenError):
        raise _auth_error() from None

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise _auth_error()
    return user


async def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "权限不足。"}},
        )
    return current_user


def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "unauthorized", "message": "认证失败。"}},
        headers={"WWW-Authenticate": "Bearer"},
    )
