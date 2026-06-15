from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from sentineldrive_worker.connectors.contracts import RetryPolicy, SourceConfig, SourceType


@dataclass(frozen=True)
class SourceConfigRow:
    name: str
    source_type: str
    base_url: str | None = None
    status: str = "enabled"
    config: dict[str, Any] | None = None
    cursor: str | None = None


def load_source_configs(
    env: dict[str, str] | None = None,
    db_sources: list[SourceConfigRow] | None = None,
) -> list[SourceConfig]:
    values = os.environ if env is None else env
    configs = list(_default_env_sources(values))
    if db_sources:
        configs.extend(_source_from_row(row, values) for row in db_sources)
    return configs


def _default_env_sources(values: dict[str, str]) -> tuple[SourceConfig, ...]:
    sync_interval = _positive_int(values.get("SOURCE_SYNC_INTERVAL_SECONDS"), 3600)
    timeout = _positive_float(values.get("SOURCE_TIMEOUT_SECONDS"), 20.0)
    rate_limit = _positive_int(values.get("SOURCE_RATE_LIMIT_PER_MINUTE"), 20)
    retry_policy = RetryPolicy(attempts=_non_negative_int(values.get("SOURCE_RETRY_ATTEMPTS"), 3))
    nvd_api_key = values.get("NVD_API_KEY", "").strip()
    rss_feeds = _json_list(values.get("SOURCE_RSS_FEEDS"), [])
    vendor_endpoints = _json_list(values.get("SOURCE_VENDOR_ADVISORY_ENDPOINTS"), DEFAULT_VENDOR_ENDPOINTS)

    sources = (
        SourceConfig(
            name="nvd",
            source_type=SourceType.API,
            enabled=_bool(values.get("SOURCE_ENABLED_NVD"), True),
            base_url="https://services.nvd.nist.gov/rest/json/cves/2.0",
            sync_interval_seconds=sync_interval,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit if nvd_api_key else min(rate_limit, 5),
            retry_policy=retry_policy,
            credentials={"api_key": nvd_api_key} if nvd_api_key else {},
            metadata={"connector": "nvd", "credential_configured": bool(nvd_api_key)},
        ),
        SourceConfig(
            name="cisa-kev",
            source_type=SourceType.API,
            enabled=_bool(values.get("SOURCE_ENABLED_CISA_KEV"), True),
            base_url="https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
            sync_interval_seconds=sync_interval,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            retry_policy=retry_policy,
            metadata={"connector": "cisa-kev"},
        ),
        SourceConfig(
            name="vendor-advisories",
            source_type=SourceType.VENDOR,
            enabled=_bool(values.get("SOURCE_ENABLED_VENDOR_ADVISORIES"), False),
            sync_interval_seconds=sync_interval,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            retry_policy=retry_policy,
            metadata={"connector": "vendor-advisories", "endpoints": vendor_endpoints},
        ),
        SourceConfig(
            name="rss",
            source_type=SourceType.RSS,
            enabled=_bool(values.get("SOURCE_ENABLED_RSS"), True),
            sync_interval_seconds=sync_interval,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            retry_policy=retry_policy,
            metadata={"connector": "rss", "feeds": rss_feeds},
        ),
        SourceConfig(
            name="sample",
            source_type=SourceType.API,
            enabled=_bool(values.get("SOURCE_ENABLED_SAMPLE"), True),
            base_url="sentineldrive://sample",
            sync_interval_seconds=sync_interval,
            timeout_seconds=timeout,
            rate_limit_per_minute=rate_limit,
            retry_policy=retry_policy,
            metadata={"connector": "sample"},
        ),
    )
    return sources


def _source_from_row(row: SourceConfigRow, values: dict[str, str]) -> SourceConfig:
    source_config = row.config or {}
    retry_policy = RetryPolicy(
        attempts=_non_negative_int(source_config.get("retry_attempts"), _non_negative_int(values.get("SOURCE_RETRY_ATTEMPTS"), 3)),
        backoff_seconds=_non_negative_float(source_config.get("retry_backoff_seconds"), 1.0),
        max_backoff_seconds=_non_negative_float(source_config.get("retry_max_backoff_seconds"), 30.0),
    )
    return SourceConfig(
        name=row.name,
        source_type=SourceType(row.source_type),
        enabled=row.status.strip().lower() == "enabled" and _bool(source_config.get("enabled"), True),
        base_url=row.base_url,
        sync_interval_seconds=_positive_int(source_config.get("sync_interval_seconds"), _positive_int(values.get("SOURCE_SYNC_INTERVAL_SECONDS"), 3600)),
        timeout_seconds=_positive_float(source_config.get("timeout_seconds"), _positive_float(values.get("SOURCE_TIMEOUT_SECONDS"), 20.0)),
        rate_limit_per_minute=_positive_int(
            source_config.get("rate_limit_per_minute"),
            _positive_int(values.get("SOURCE_RATE_LIMIT_PER_MINUTE"), 20),
        ),
        retry_policy=retry_policy,
        cursor=row.cursor,
        credentials=_redactable_mapping(source_config.get("credentials")),
        headers=_redactable_mapping(source_config.get("headers")),
        metadata=_source_metadata_from_config(row.name, source_config),
    )


def _bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _positive_int(value: object, default: int) -> int:
    if value is None or value == "":
        return default
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("expected a positive integer")
    return parsed


def _non_negative_int(value: object, default: int) -> int:
    if value is None or value == "":
        return default
    parsed = int(value)
    if parsed < 0:
        raise ValueError("expected a non-negative integer")
    return parsed


def _positive_float(value: object, default: float) -> float:
    if value is None or value == "":
        return default
    parsed = float(value)
    if parsed <= 0:
        raise ValueError("expected a positive number")
    return parsed


def _non_negative_float(value: object, default: float) -> float:
    if value is None or value == "":
        return default
    parsed = float(value)
    if parsed < 0:
        raise ValueError("expected a non-negative number")
    return parsed


def _redactable_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _source_metadata_from_config(source_name: str, source_config: dict[str, Any]) -> dict[str, Any]:
    redacted_keys = {"credentials", "headers"}
    metadata = {
        key: value
        for key, value in source_config.items()
        if key not in redacted_keys
    }
    metadata["connector"] = source_config.get("connector", source_name)
    metadata["db_backed"] = True
    return metadata


def _json_list(value: object, default: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if value is None or value == "":
        return list(default)
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError("expected a JSON list") from exc
    if not isinstance(parsed, list):
        raise ValueError("expected a JSON list")
    if not all(isinstance(item, dict) for item in parsed):
        raise ValueError("expected a JSON list of objects")
    return parsed


DEFAULT_VENDOR_ENDPOINTS: list[dict[str, Any]] = [
    {
        "vendor": "BYD",
        "url": "https://www.bydglobal.com/",
        "verification_status": "needs_manual_review",
        "endpoint_type": "official_fallback",
    },
    {
        "vendor": "NIO",
        "url": "https://niosrc.bugbank.cn/",
        "verification_status": "official_security_entry",
    },
    {
        "vendor": "NIO",
        "url": "https://niosrc-en.bugbank.cn/",
        "verification_status": "official_security_entry",
    },
    {
        "vendor": "Li Auto",
        "url": "https://security.lixiang.com/",
        "verification_status": "official_security_entry",
    },
    {
        "vendor": "Qualcomm",
        "url": "https://www.qualcomm.com/company/product-security",
        "verification_status": "official_security_entry",
    },
    {
        "vendor": "Qualcomm",
        "url": "https://docs.qualcomm.com/product/publicresources/securitybulletin",
        "verification_status": "official_security_bulletin",
    },
    {
        "vendor": "Bosch",
        "url": "https://psirt.bosch.com/security-advisories/",
        "verification_status": "official_security_entry",
    },
]
