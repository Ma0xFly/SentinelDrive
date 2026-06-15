import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.settings import Settings

TOKEN_TTL = timedelta(hours=8)


class TokenError(ValueError):
    pass


def create_access_token(user_id: UUID, email: str, is_admin: bool, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + TOKEN_TTL).timestamp()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_segment = _encode(payload_bytes)
    signature = _signature(payload_segment, settings)
    return f"{payload_segment}.{signature}"


def decode_access_token(token: str, settings: Settings) -> dict[str, object]:
    try:
        payload_segment, signature = token.split(".", 1)
    except ValueError as exc:
        raise TokenError("invalid token") from exc

    expected_signature = _signature(payload_segment, settings)
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("invalid token")

    try:
        payload = json.loads(_decode(payload_segment))
    except (ValueError, json.JSONDecodeError) as exc:
        raise TokenError("invalid token") from exc

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(datetime.now(timezone.utc).timestamp()):
        raise TokenError("expired token")
    if not isinstance(payload.get("sub"), str):
        raise TokenError("invalid token")

    return payload


def _signature(payload_segment: str, settings: Settings) -> str:
    secret = settings.app_secret_key.get_secret_value().encode()
    digest = hmac.new(secret, payload_segment.encode(), hashlib.sha256).digest()
    return _encode(digest)


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
