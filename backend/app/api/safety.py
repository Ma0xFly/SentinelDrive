from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEY_PARTS = (
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "credential",
    "header",
    "password",
    "private",
    "raw",
    "secret",
    "token",
)
SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"\b(password|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def safe_dict(value: dict[str, Any]) -> dict[str, Any]:
    safe_value = safe_metadata(value)
    return safe_value if isinstance(safe_value, dict) else {}


def safe_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_name(key_text):
                continue
            safe[key_text] = safe_metadata(item)
        return safe
    if isinstance(value, list):
        return [safe_metadata(item) for item in value[:50]]
    if isinstance(value, str):
        if looks_like_url(value):
            return safe_url(value)
        if looks_sensitive_value(value):
            return None
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def safe_url(value: str | None) -> str | None:
    if not value:
        return value
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None if looks_sensitive_value(value) else value
    netloc = safe_netloc(parsed)
    query_items = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not is_sensitive_name(key) and not looks_sensitive_value(item)
    ]
    return urlunsplit((parsed.scheme, netloc, parsed.path, urlencode(query_items), safe_fragment(parsed.fragment)))


def safe_text(value: str | None) -> str | None:
    if value is None or looks_sensitive_value(value):
        return None
    return value


def looks_sensitive_value(value: str) -> bool:
    return bool(SENSITIVE_ASSIGNMENT_PATTERN.search(value))


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def is_sensitive_name(value: str) -> bool:
    normalized = value.lower().replace("-", "_")
    return any(part in normalized for part in SENSITIVE_KEY_PARTS)


def safe_netloc(parsed) -> str:
    hostname = parsed.hostname or ""
    if hostname and ":" in hostname and not hostname.startswith("["):
        netloc = f"[{hostname}]"
    else:
        netloc = hostname
    try:
        port = parsed.port
    except ValueError:
        port = None
    if port is not None and netloc:
        netloc = f"{netloc}:{port}"
    if not netloc:
        if "@" in parsed.netloc or looks_sensitive_value(parsed.netloc):
            return ""
        return parsed.netloc
    return netloc


def safe_fragment(value: str) -> str:
    if not value:
        return value
    if looks_sensitive_value(value):
        return ""
    for key, item in parse_qsl(value, keep_blank_values=True):
        if is_sensitive_name(key) or looks_sensitive_value(item):
            return ""
    return value
