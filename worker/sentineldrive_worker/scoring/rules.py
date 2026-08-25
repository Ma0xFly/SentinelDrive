from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from sentineldrive_worker.normalization.dedup import normalize_text

RULE_VERSION = "fixed-risk-v1"

RISK_LEVELS = (
    (90.0, "critical"),
    (70.0, "high"),
    (40.0, "medium"),
    (0.0, "low"),
)

SEVERITY_FALLBACK = {
    "critical": 62.0,
    "high": 50.0,
    "medium": 32.0,
    "low": 15.0,
    "unknown": 10.0,
}

REMOTE_SURFACES = {
    "app",
    "tbox",
    "ota",
    "v2x",
    "charging",
    "cloud_api",
    "bluetooth",
    "wifi",
    "cellular",
}

CRITICAL_COMPONENT_WEIGHTS = {
    "tbox": 14.0,
    "ota": 14.0,
    "can": 14.0,
    "v2x": 14.0,
    "cloud_api": 13.0,
    "app": 12.0,
    "charging": 12.0,
    "cellular": 10.0,
    "wifi": 8.0,
    "bluetooth": 8.0,
    "ivi": 7.0,
    "usb": 4.0,
}

KNOWN_EXPLOITED_TAGS = {"cisa-kev", "kev", "known_exploited", "known-exploited"}
POC_TERMS = (
    "proof of concept",
    "public poc",
    "poc available",
    "exploit code",
    "metasploit",
    "exploit-db",
    "github.com",
)
REMOTE_TERMS = (
    "remote",
    "network exploitable",
    "network-exploitable",
    "internet facing",
    "internet-facing",
    "over the air",
    "over-the-air",
    "cloud api",
    "mobile app",
    "cellular",
    "v2x",
)
UNAUTHENTICATED_TERMS = (
    "unauthenticated",
    "without authentication",
    "no authentication",
    "authentication bypass",
    "auth bypass",
)
AUTHENTICATED_TERMS = (
    "authenticated user",
    "requires authentication",
    "authentication required",
    "privileges required",
)
MULTI_VENDOR_TERMS = (
    "multi vendor",
    "multi-vendor",
    "multiple vendors",
    "common component",
    "third party component",
    "third-party component",
    "supply chain",
    "shared component",
    "widely used",
)
COMMON_COMPONENT_TERMS = (
    "openssl",
    "linux",
    "android",
    "autosar",
    "bluetooth stack",
    "wifi chipset",
    "wi-fi chipset",
    "baseband",
    "qualcomm",
    "evse",
    "charging station",
)


@dataclass(frozen=True)
class ScoreFactor:
    key: str
    label: str
    contribution: float
    evidence: str | float | int | bool | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "contribution": round(self.contribution, 2),
        }
        if self.evidence is not None:
            payload["evidence"] = self.evidence
        return payload


@dataclass(frozen=True)
class ScoringResult:
    risk_score: float
    risk_level: str
    explanation: dict[str, Any]


def score_threat_intelligence(record: Mapping[str, Any]) -> ScoringResult:
    metadata = metadata_without_scoring(record.get("metadata"))
    tags = normalized_tags(record.get("tags"))
    signal_text = searchable_text(record, metadata)
    factors: list[ScoreFactor] = []

    factors.append(cvss_or_severity_factor(record))

    if known_exploited(record, tags, metadata):
        factors.append(ScoreFactor("known_exploited", "已知在野利用或 CISA KEV 信号", 25.0, True))
    elif normalize_key(record.get("exploit_status")) == "proof_of_concept":
        factors.append(ScoreFactor("exploit_status", "概念验证（PoC）利用状态", 12.0, "proof_of_concept"))

    if has_any_term(signal_text, POC_TERMS) or "poc" in tags or "proof_of_concept" in tags:
        factors.append(ScoreFactor("public_poc", "公开 PoC 或利用代码信号", 10.0, True))

    remote_signal = remote_exploitability_signal(record, signal_text)
    if remote_signal:
        factors.append(ScoreFactor("remote_exploitability", "可远程利用信号", remote_signal[1], remote_signal[0]))

    auth_signal = authentication_signal(record, signal_text)
    if auth_signal:
        factors.append(ScoreFactor("authentication_requirement", "身份认证要求信号", auth_signal[1], auth_signal[0]))

    component_signal = vehicle_component_signal(record)
    if component_signal:
        factors.append(ScoreFactor("vehicle_critical_component", "车控关键组件影响", component_signal[1], component_signal[0]))

    if multi_vendor_or_common_component(record, signal_text):
        factors.append(ScoreFactor("multi_vendor_common_component", "多厂商或通用组件影响", 8.0, True))

    factors.append(confidence_factor(record))

    score = bounded_score(sum(factor.contribution for factor in factors))
    level = risk_level_for_score(score)
    explanation = {
        "rule_version": RULE_VERSION,
        "source_fingerprint": source_fingerprint(record, metadata),
        "score": score,
        "level": level,
        "factors": [factor.to_payload() for factor in factors],
        "signals": {
            "known_exploited": known_exploited(record, tags, metadata),
            "public_poc": any(factor.key == "public_poc" for factor in factors),
            "remote_exploitability": remote_signal is not None,
            "authentication": auth_signal[0] if auth_signal else "unknown",
            "vehicle_component": component_signal[0] if component_signal else None,
            "multi_vendor_or_common_component": multi_vendor_or_common_component(record, signal_text),
            "source_confidence": normalize_key(record.get("confidence")) or "medium",
        },
    }
    return ScoringResult(risk_score=score, risk_level=level, explanation=explanation)


def cvss_or_severity_factor(record: Mapping[str, Any]) -> ScoreFactor:
    cvss_score = numeric_or_none(record.get("cvss_score"))
    if cvss_score is not None:
        bounded_cvss = min(max(cvss_score, 0.0), 10.0)
        return ScoreFactor("cvss", "CVSS 基础分", round(bounded_cvss * 7.0, 2), round(bounded_cvss, 1))
    severity = normalize_key(record.get("severity")) or "unknown"
    contribution = SEVERITY_FALLBACK.get(severity, SEVERITY_FALLBACK["unknown"])
    return ScoreFactor("severity", "严重度回退评分", contribution, severity)


def known_exploited(record: Mapping[str, Any], tags: set[str], metadata: Mapping[str, Any]) -> bool:
    if normalize_key(record.get("exploit_status")) == "exploited":
        return True
    if tags.intersection(KNOWN_EXPLOITED_TAGS):
        return True
    source_names = {normalize_key(value) for value in list_values(record.get("source_names"))}
    if "cisa-kev" in source_names or "cisa_kev" in source_names:
        return True
    return any(metadata.get(key) for key in ("date_added", "known_ransomware_campaign_use", "vulnerability_name"))


def remote_exploitability_signal(record: Mapping[str, Any], signal_text: str) -> tuple[str, float] | None:
    attack_surface = normalize_key(record.get("attack_surface"))
    component = normalize_key(record.get("vehicle_component"))
    vector_access = cvss_metric(record.get("cvss_vector"), "AV")
    if vector_access == "N":
        return ("network", 10.0)
    if attack_surface in REMOTE_SURFACES or component in REMOTE_SURFACES:
        return (attack_surface or component, 10.0)
    if vector_access == "A":
        return ("adjacent_network", 7.0)
    if has_any_term(signal_text, REMOTE_TERMS):
        return ("text", 8.0)
    return None


def authentication_signal(record: Mapping[str, Any], signal_text: str) -> tuple[str, float] | None:
    privileges_required = cvss_metric(record.get("cvss_vector"), "PR")
    if privileges_required == "N":
        return ("none_required", 8.0)
    if has_any_term(signal_text, UNAUTHENTICATED_TERMS):
        return ("none_required", 8.0)
    if privileges_required == "L":
        return ("low_privilege_required", 3.0)
    if privileges_required == "H":
        return ("high_privilege_required", -4.0)
    if has_any_term(signal_text, AUTHENTICATED_TERMS):
        return ("authentication_required", -4.0)
    return None


def vehicle_component_signal(record: Mapping[str, Any]) -> tuple[str, float] | None:
    component = normalize_key(record.get("vehicle_component"))
    attack_surface = normalize_key(record.get("attack_surface"))
    key = component if component in CRITICAL_COMPONENT_WEIGHTS else attack_surface
    if key in CRITICAL_COMPONENT_WEIGHTS:
        return (key, CRITICAL_COMPONENT_WEIGHTS[key])
    return None


def multi_vendor_or_common_component(record: Mapping[str, Any], signal_text: str) -> bool:
    vendor = normalize_text(record.get("affected_vendor"))
    product = normalize_text(record.get("affected_product"))
    if vendor in {"multiple", "various", "multi vendor", "multi-vendor", "multiple vendors"}:
        return True
    if has_any_term(" ".join([vendor, product, signal_text]), (*MULTI_VENDOR_TERMS, *COMMON_COMPONENT_TERMS)):
        return True
    return False


def confidence_factor(record: Mapping[str, Any]) -> ScoreFactor:
    confidence = normalize_key(record.get("confidence")) or "medium"
    contribution = {"high": 5.0, "medium": 0.0, "low": -8.0}.get(confidence, 0.0)
    return ScoreFactor("source_confidence", "数据源可信度", contribution, confidence)


def risk_level_for_score(score: float) -> str:
    for threshold, level in RISK_LEVELS:
        if score >= threshold:
            return level
    return "low"


def source_fingerprint(record: Mapping[str, Any], metadata: Mapping[str, Any] | None = None) -> str:
    payload = {
        "rule_version": RULE_VERSION,
        "title": record.get("title"),
        "summary": record.get("summary"),
        "intelligence_type": record.get("intelligence_type"),
        "source_names": sorted(list_values(record.get("source_names"))),
        "external_ids": record.get("external_ids") or {},
        "cve_id": record.get("cve_id"),
        "cwe_id": record.get("cwe_id"),
        "cvss_score": numeric_or_none(record.get("cvss_score")),
        "cvss_vector": record.get("cvss_vector"),
        "severity": record.get("severity"),
        "affected_vendor": record.get("affected_vendor"),
        "affected_product": record.get("affected_product"),
        "affected_version": record.get("affected_version"),
        "vehicle_component": record.get("vehicle_component"),
        "attack_surface": record.get("attack_surface"),
        "exploit_status": record.get("exploit_status"),
        "confidence": record.get("confidence"),
        "tags": sorted(list_values(record.get("tags"))),
        "metadata": metadata_without_scoring(record.get("metadata")) if metadata is None else dict(metadata),
    }
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def searchable_text(record: Mapping[str, Any], metadata: Mapping[str, Any]) -> str:
    values = [
        record.get("title"),
        record.get("summary"),
        record.get("source_names"),
        record.get("source_urls"),
        record.get("external_ids"),
        record.get("affected_vendor"),
        record.get("affected_product"),
        record.get("vehicle_component"),
        record.get("attack_surface"),
        record.get("exploit_status"),
        record.get("tags"),
        metadata,
    ]
    return normalize_text(" ".join(flatten_value(value) for value in values))


def metadata_without_scoring(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items() if key != "scoring"}


def normalized_tags(value: object) -> set[str]:
    return {normalize_text(item).replace(" ", "_") for item in list_values(value)}


def list_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(item) for item in value.values() if item not in (None, "")]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]


def flatten_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, Mapping):
        return " ".join(flatten_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(flatten_value(item) for item in value)
    return str(value)


def has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(term in normalized for term in terms)


def cvss_metric(vector: object, key: str) -> str | None:
    if not isinstance(vector, str):
        return None
    pattern = re.compile(rf"(?:^|/){re.escape(key)}:([A-Z])(?:/|$)")
    match = pattern.search(vector.upper())
    return match.group(1) if match else None


def normalize_key(value: object) -> str:
    return normalize_text(value).replace("-", "_")


def numeric_or_none(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def bounded_score(score: float) -> float:
    return round(min(max(score, 0.0), 100.0), 2)
