from __future__ import annotations

from datetime import datetime, time, timezone
from email.utils import parsedate_to_datetime


def parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return ensure_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            return ensure_utc(datetime.fromisoformat(candidate))
        except ValueError:
            pass
    try:
        return ensure_utc(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        pass
    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.combine(datetime.strptime(text, date_format).date(), time.min, tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)

def isoformat_utc(value: datetime) -> str:
    return ensure_utc(value).replace(microsecond=0).isoformat().replace("+00:00", "Z")
