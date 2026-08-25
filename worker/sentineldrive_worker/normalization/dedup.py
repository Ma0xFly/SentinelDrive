from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping
from urllib.parse import urldefrag, urlsplit, urlunsplit

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
CWE_PATTERN = re.compile(r"\bCWE-\d+\b", re.IGNORECASE)


def stable_hash(value: Mapping[str, Any]) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def normalize_text(value: object) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_cve(value: object) -> str | None:
    if value is None:
        return None
    match = CVE_PATTERN.search(str(value))
    return match.group(0).upper() if match else None


def find_cve(*values: object) -> str | None:
    for value in values:
        cve = normalize_cve(value)
        if cve:
            return cve
    return None


def normalize_cwe(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        for item in value:
            cwe = normalize_cwe(item)
            if cwe:
                return cwe
        return None
    match = CWE_PATTERN.search(str(value))
    return match.group(0).upper() if match else None


def canonical_url(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    url, _fragment = urldefrag(text)
    parsed = urlsplit(url)
    if parsed.scheme in {"http", "https"}:
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        return urlunsplit((scheme, netloc, path, parsed.query, ""))
    return text


def external_ingest_dedup_key(
    *,
    cve_id: str | None,
    dedup_key: str | None,
    external_id: str | None,
    source_name: str,
    source_url: str | None,
    content_hash: str | None,
    normalized_text_hash: str | None,
) -> str:
    """Mirror the backend ingest `_dedup_key` priority and string format.

    External/AI raw records normalized by the worker must converge on the
    same key the backend ingest API produces, so a record entering through
    either path lands on a single core intelligence row.
    """
    if cve_id:
        return f"cve:{cve_id.upper()}"
    if dedup_key:
        return f"external:{stable_hash({'dedup_key': dedup_key})[:48]}"
    if external_id:
        return f"external:{stable_hash({'source_name': source_name, 'external_id': external_id})[:48]}"
    if content_hash:
        return f"content:{content_hash}"
    if source_url:
        return f"url:{stable_hash({'url': source_url})[:48]}"
    return f"text:{normalized_text_hash or content_hash}"


def dedup_key(*, cve_id: str | None, source_url: str | None, title: str | None, source_name: str | None, content_hash: str | None, normalized_text_hash: str | None) -> str:
    if cve_id:
        return f"cve:{cve_id.upper()}"
    url = canonical_url(source_url)
    if url:
        return f"url:{stable_hash({'url': url})[:48]}"
    title_key = normalize_text(title)
    source_key = normalize_text(source_name)
    if title_key and source_key:
        return f"title-source:{stable_hash({'title': title_key, 'source_name': source_key})[:48]}"
    if content_hash:
        return f"content:{content_hash}"
    if normalized_text_hash:
        return f"text:{normalized_text_hash}"
    return f"fallback:{stable_hash({'title': title, 'source': source_name})[:48]}"
