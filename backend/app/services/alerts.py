from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.types import AlertStatus, RiskLevel, Severity
from app.models.intelligence import ThreatIntelligence
from app.models.security import Alert

VEHICLE_CRITICAL_COMPONENTS = {
    "app",
    "tbox",
    "ota",
    "cloud_api",
    "can",
    "v2x",
    "charging",
}
BURST_LOOKBACK = timedelta(days=7)
BURST_MIN_ITEMS = 3
HIGH_RISK_LEVELS = {"high", "critical"}
KNOWN_EXPLOITED_TAGS = {"cisa-kev", "kev", "known_exploited", "known-exploited"}
CONTEXT_LIMIT = 500


@dataclass(frozen=True)
class AlertRuleCandidate:
    rule: str
    title: str
    risk_level: RiskLevel
    metadata: dict[str, Any]


def evaluate_and_create_alerts(
    session: Session,
    *,
    intelligence_id: object | None = None,
    limit: int = 100,
) -> list[Alert]:
    entries = _candidate_entries(session, intelligence_id=intelligence_id, limit=limit)
    context_entries = _candidate_entries(session, limit=max(limit, CONTEXT_LIMIT))
    context_ids = {entry.id for entry in context_entries}
    for entry in entries:
        if entry.id not in context_ids:
            context_entries.append(entry)
    created: list[Alert] = []
    for entry in entries:
        created.extend(create_alerts_for_intelligence(session, entry, entries=context_entries))
    return created


def create_alerts_for_intelligence(
    session: Session,
    entry: ThreatIntelligence,
    *,
    entries: list[ThreatIntelligence] | None = None,
    now: datetime | None = None,
) -> list[Alert]:
    now = now or datetime.now(timezone.utc)
    related_entries = entries if entries is not None else _candidate_entries(session, limit=CONTEXT_LIMIT)
    created: list[Alert] = []
    for candidate in alert_candidates(entry, related_entries, now=now):
        if _existing_alert(session, entry, candidate.rule) is not None:
            continue
        alert = Alert(
            title=candidate.title,
            threat_intelligence_id=entry.id,
            triggering_rule=candidate.rule,
            risk_level=candidate.risk_level,
            triggered_at=now,
            status=AlertStatus.OPEN,
            notes=None,
            metadata_=candidate.metadata,
        )
        session.add(alert)
        _attach_alert(entry, alert)
        created.append(alert)
    return created


def alert_candidates(
    entry: ThreatIntelligence,
    entries: list[ThreatIntelligence],
    *,
    now: datetime,
) -> list[AlertRuleCandidate]:
    candidates: list[AlertRuleCandidate] = []
    risk_level = _risk_level(entry.risk_level)
    if _is_critical(entry):
        candidates.append(
            _candidate(
                entry,
                rule="critical-intelligence",
                title="关键风险情报",
                risk_level=RiskLevel.CRITICAL,
                reason="critical intelligence",
            )
        )
    if _known_exploited(entry):
        candidates.append(
            _candidate(
                entry,
                rule="known-exploited",
                title="已知在野利用情报",
                risk_level=_max_risk(risk_level, RiskLevel.HIGH),
                reason="known exploited signal",
            )
        )
    if _is_high_risk_vehicle_critical(entry):
        candidates.append(
            _candidate(
                entry,
                rule=f"vehicle-critical-{_component_key(entry)}",
                title="高风险车端关键组件情报",
                risk_level=_max_risk(risk_level, RiskLevel.HIGH),
                reason="high-risk vehicle critical component",
            )
        )
    cve_source_count = _cve_source_count(entry, entries)
    if entry.cve_id and cve_source_count >= 2:
        candidates.append(
            _candidate(
                entry,
                rule=f"multi-source-cve-{entry.cve_id.upper()}",
                title="多来源 CVE 情报",
                risk_level=_max_risk(risk_level, RiskLevel.MEDIUM),
                reason="same CVE observed across multiple sources",
                metadata={"source_count": cve_source_count},
            )
        )
    burst = _burst_context(entry, entries, now=now)
    if burst:
        candidates.append(
            _candidate(
                entry,
                rule=f"burst-{burst['scope']}-{burst['value']}",
                title="短期高风险情报集中出现",
                risk_level=_max_risk(risk_level, RiskLevel.HIGH),
                reason="multiple high-risk items in short period",
                metadata=burst,
            )
        )
    return candidates


def _candidate(
    entry: ThreatIntelligence,
    *,
    rule: str,
    title: str,
    risk_level: RiskLevel,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> AlertRuleCandidate:
    payload = {
        "reason": reason,
        "intelligence_id": str(entry.id),
        "cve_id": entry.cve_id,
        "risk_score": _float_or_none(entry.risk_score),
        "risk_level": _enum_value(entry.risk_level),
        "severity": _enum_value(entry.severity),
        "vehicle_component": _enum_value(entry.vehicle_component),
        "attack_surface": _enum_value(entry.attack_surface),
        "scoring": _scoring_metadata(entry),
    }
    payload.update(metadata or {})
    return AlertRuleCandidate(rule=rule, title=title, risk_level=risk_level, metadata=payload)


def _candidate_entries(
    session: Session,
    *,
    intelligence_id: object | None = None,
    limit: int = 100,
) -> list[ThreatIntelligence]:
    statement = select(ThreatIntelligence).order_by(ThreatIntelligence.last_seen_at.desc(), ThreatIntelligence.id.asc())
    if intelligence_id is not None:
        statement = statement.where(ThreatIntelligence.id == intelligence_id)
    else:
        statement = statement.limit(limit)
    return list(session.scalars(statement).all())


def _existing_alert(session: Session, entry: ThreatIntelligence, rule: str) -> Alert | None:
    for alert in entry.alerts or []:
        if alert.triggering_rule == rule:
            return alert
    return session.scalar(
        select(Alert).where(
            Alert.threat_intelligence_id == entry.id,
            Alert.triggering_rule == rule,
        )
    )


def _attach_alert(entry: ThreatIntelligence, alert: Alert) -> None:
    try:
        alerts = entry.alerts
    except Exception:
        return
    if alerts is None:
        entry.alerts = [alert]
    elif alert not in alerts:
        alerts.append(alert)


def _is_critical(entry: ThreatIntelligence) -> bool:
    return _enum_value(entry.risk_level) == RiskLevel.CRITICAL.value or _enum_value(entry.severity) == Severity.CRITICAL.value


def _known_exploited(entry: ThreatIntelligence) -> bool:
    metadata = entry.metadata_ or {}
    scoring = _scoring_metadata(entry)
    signals = scoring.get("signals") if isinstance(scoring.get("signals"), dict) else {}
    tags = {_normalize(value) for value in (entry.tags or [])}
    source_names = {_normalize(value) for value in (entry.source_names or [])}
    return (
        _enum_value(entry.exploit_status) == "exploited"
        or bool(signals.get("known_exploited"))
        or bool(tags.intersection(KNOWN_EXPLOITED_TAGS))
        or "cisa-kev" in source_names
        or "cisa_kev" in source_names
        or bool(metadata.get("date_added") or metadata.get("known_ransomware_campaign_use") or metadata.get("vulnerability_name"))
    )


def _is_high_risk_vehicle_critical(entry: ThreatIntelligence) -> bool:
    return _enum_value(entry.risk_level) in HIGH_RISK_LEVELS and _component_key(entry) in VEHICLE_CRITICAL_COMPONENTS


def _component_key(entry: ThreatIntelligence) -> str:
    return _normalize(entry.vehicle_component) or _normalize(entry.attack_surface)


def _source_count(entry: ThreatIntelligence) -> int:
    source_urls = {value for value in (entry.source_urls or []) if value}
    source_names = {value for value in (entry.source_names or []) if value}
    links = {source.source_url for source in (entry.source_links or []) if source.source_url}
    return max(len(source_urls | links), len(source_names))


def _cve_source_count(entry: ThreatIntelligence, entries: list[ThreatIntelligence]) -> int:
    if not entry.cve_id:
        return 0
    cve_id = entry.cve_id.upper()
    source_names: set[str] = set()
    source_urls: set[str] = set()
    for other in entries:
        if (other.cve_id or "").upper() != cve_id:
            continue
        source_names.update(value for value in (other.source_names or []) if value)
        source_urls.update(value for value in (other.source_urls or []) if value)
        source_urls.update(source.source_url for source in (other.source_links or []) if source.source_url)
    return max(_source_count(entry), len(source_names), len(source_urls))


def _burst_context(entry: ThreatIntelligence, entries: list[ThreatIntelligence], *, now: datetime) -> dict[str, Any] | None:
    first_seen = _aware_datetime(entry.first_seen_at) or now
    window_start = first_seen - BURST_LOOKBACK
    scopes = (
        ("vendor", entry.affected_vendor),
        ("component", _component_key(entry)),
    )
    for scope, value in scopes:
        normalized_value = _normalize(value)
        if not normalized_value:
            continue
        matches = [
            other
            for other in entries
            if _enum_value(other.risk_level) in HIGH_RISK_LEVELS
            and window_start <= (_aware_datetime(other.first_seen_at) or first_seen) <= first_seen
            and (
                _normalize(other.affected_vendor) == normalized_value
                if scope == "vendor"
                else _component_key(other) == normalized_value
            )
        ]
        if len({str(item.id) for item in matches}) >= BURST_MIN_ITEMS:
            return {
                "scope": scope,
                "value": normalized_value,
                "lookback_days": BURST_LOOKBACK.days,
                "match_count": len({str(item.id) for item in matches}),
                "matched_intelligence_ids": sorted(str(item.id) for item in matches),
            }
    return None


def _max_risk(*levels: RiskLevel) -> RiskLevel:
    order = {
        RiskLevel.INFO: 0,
        RiskLevel.LOW: 1,
        RiskLevel.MEDIUM: 2,
        RiskLevel.HIGH: 3,
        RiskLevel.CRITICAL: 4,
    }
    return max(levels, key=lambda level: order[level])


def _risk_level(value: Any) -> RiskLevel:
    normalized = _enum_value(value)
    try:
        return RiskLevel(normalized)
    except ValueError:
        return RiskLevel.INFO


def _scoring_metadata(entry: ThreatIntelligence) -> dict[str, Any]:
    metadata = entry.metadata_ or {}
    scoring = metadata.get("scoring")
    if isinstance(scoring, dict):
        return scoring
    score_metadata = metadata.get("score_metadata")
    if isinstance(score_metadata, dict):
        return score_metadata
    return {}


def _aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    return str(value).strip().lower().replace("-", "_")


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
