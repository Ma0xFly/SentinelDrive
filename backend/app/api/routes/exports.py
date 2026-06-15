from __future__ import annotations

import csv
import io
import textwrap
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_request_session
from app.api.routes.alerts import (
    AlertSearchParams,
    _alert_detail_response,
    _build_alert_statement,
    _matches_alert,
    _parse_alert_intelligence_id,
    _sort_alerts,
)
from app.api.routes.intelligence import (
    IntelligenceSearchParams,
    _build_search_statement,
    _detail_response,
    _matches_params,
    _normalize_cve,
    _sort_entries,
)
from app.api.safety import safe_text, safe_url
from app.api.schemas.alerts import AlertSort
from app.api.schemas.intelligence import IntelligenceSort
from app.db.types import AlertStatus, AttackSurface, IntelligenceType, RiskLevel, VehicleComponent
from app.models.intelligence import ThreatIntelligence
from app.models.security import Alert, User

router = APIRouter(prefix="/exports", tags=["exports"])

DEFAULT_EXPORT_LIMIT = 100
PDF_SUMMARY_LIMIT = 20


@router.get("/intelligence.csv")
async def export_intelligence_csv(
    q: str | None = Query(default=None, min_length=1, max_length=200),
    cve: str | None = Query(default=None, min_length=1, max_length=32),
    vendor: str | None = Query(default=None, min_length=1, max_length=160),
    product: str | None = Query(default=None, min_length=1, max_length=200),
    vehicle_component: VehicleComponent | None = None,
    attack_surface: AttackSurface | None = None,
    risk_level: RiskLevel | None = None,
    tag: str | None = Query(default=None, min_length=1, max_length=80),
    source: str | None = Query(default=None, min_length=1, max_length=240),
    status_filter: str | None = Query(default=None, alias="status", min_length=1, max_length=40),
    intelligence_type: IntelligenceType | None = None,
    sort: IntelligenceSort = IntelligenceSort.RECENT,
    limit: int = Query(default=DEFAULT_EXPORT_LIMIT, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> Response:
    del current_user
    params = IntelligenceSearchParams(
        q=_clean(q),
        cve=_normalize_cve(cve),
        vendor=_clean(vendor),
        product=_clean(product),
        vehicle_component=vehicle_component,
        attack_surface=attack_surface,
        risk_level=risk_level,
        tag=_clean(tag),
        source=_clean(source),
        status=_clean(status_filter),
        intelligence_type=intelligence_type,
        sort=sort,
    )
    entries = _intelligence_entries(session, params, limit)
    headers = [
        "id",
        "title",
        "summary",
        "intelligence_type",
        "cve_id",
        "severity",
        "risk_level",
        "risk_score",
        "status",
        "affected_vendor",
        "affected_product",
        "vehicle_component",
        "attack_surface",
        "source_names",
        "source_urls",
        "first_seen_at",
        "last_seen_at",
    ]
    return _csv_response(
        "sentineldrive-intelligence.csv",
        headers,
        [_intelligence_csv_row(entry) for entry in entries],
    )


@router.get("/intelligence/{intelligence_id}/markdown")
async def export_intelligence_markdown(
    intelligence_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> Response:
    del current_user
    entry = session.get(ThreatIntelligence, intelligence_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "intelligence_not_found", "message": "情报记录不存在。"}},
        )
    detail = _detail_response(entry)
    body = _intelligence_markdown(detail.model_dump(mode="json"))
    return _download_response(
        body,
        media_type="text/markdown; charset=utf-8",
        filename=f"sentineldrive-intelligence-{intelligence_id}.md",
    )


@router.get("/alerts.csv")
async def export_alerts_csv(
    risk_level: RiskLevel | None = None,
    status_filter: AlertStatus | None = Query(default=None, alias="status"),
    triggering_rule: str | None = Query(default=None, min_length=1, max_length=240),
    intelligence_id: str | None = Query(default=None),
    sort: AlertSort = AlertSort.RECENT,
    limit: int = Query(default=DEFAULT_EXPORT_LIMIT, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> Response:
    del current_user
    params = AlertSearchParams(
        risk_level=risk_level,
        status=status_filter,
        triggering_rule=_clean(triggering_rule),
        intelligence_id=_parse_alert_intelligence_id(intelligence_id),
        sort=sort,
    )
    alerts = _alert_entries(session, params, limit)
    headers = [
        "id",
        "title",
        "threat_intelligence_id",
        "triggering_rule",
        "risk_level",
        "status",
        "triggered_at",
        "notes",
        "intelligence_title",
        "cve_id",
        "source_names",
    ]
    return _csv_response("sentineldrive-alerts.csv", headers, [_alert_csv_row(alert) for alert in alerts])


@router.get("/summary.pdf")
async def export_summary_pdf(
    limit: int = Query(default=PDF_SUMMARY_LIMIT, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_request_session),
) -> Response:
    del current_user
    intelligence = _intelligence_entries(session, IntelligenceSearchParams(sort=IntelligenceSort.RISK_SCORE), limit)
    alerts = _alert_entries(session, AlertSearchParams(sort=AlertSort.RISK_LEVEL), limit)
    body = _summary_pdf(intelligence, alerts)
    return _download_response(body, media_type="application/pdf", filename="sentineldrive-summary.pdf")


def _intelligence_entries(session: Session, params: IntelligenceSearchParams, limit: int) -> list[ThreatIntelligence]:
    statement = _build_search_statement(params)
    if isinstance(session, Session):
        return list(session.scalars(statement.limit(limit)).all())
    entries = list(session.scalars(statement).all())
    filtered = [entry for entry in entries if _matches_params(entry, params)]
    return _sort_entries(filtered, params.sort)[:limit]


def _alert_entries(session: Session, params: AlertSearchParams, limit: int) -> list[Alert]:
    statement = _build_alert_statement(params)
    if isinstance(session, Session):
        return list(session.scalars(statement.limit(limit)).all())
    alerts = list(session.scalars(statement).all())
    filtered = [alert for alert in alerts if _matches_alert(alert, params)]
    return _sort_alerts(filtered, params.sort)[:limit]


def _intelligence_csv_row(entry: ThreatIntelligence) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "title": _safe_text(entry.title),
        "summary": _safe_text(entry.summary),
        "intelligence_type": _enum_value(entry.intelligence_type),
        "cve_id": entry.cve_id,
        "severity": _enum_value(entry.severity),
        "risk_level": _enum_value(entry.risk_level),
        "risk_score": _number(entry.risk_score),
        "status": entry.status,
        "affected_vendor": _safe_text(entry.affected_vendor),
        "affected_product": _safe_text(entry.affected_product),
        "vehicle_component": _enum_value(entry.vehicle_component),
        "attack_surface": _enum_value(entry.attack_surface),
        "source_names": _join(entry.source_names or []),
        "source_urls": _join([clean_url for url in (entry.source_urls or []) if (clean_url := safe_url(url))]),
        "first_seen_at": _iso(entry.first_seen_at),
        "last_seen_at": _iso(entry.last_seen_at),
    }


def _alert_csv_row(alert: Alert) -> dict[str, Any]:
    detail = _alert_detail_response(alert)
    intelligence = detail.intelligence
    return {
        "id": str(alert.id),
        "title": _safe_text(alert.title),
        "threat_intelligence_id": str(alert.threat_intelligence_id),
        "triggering_rule": alert.triggering_rule,
        "risk_level": _enum_value(alert.risk_level),
        "status": _enum_value(alert.status),
        "triggered_at": _iso(alert.triggered_at),
        "notes": _safe_text(alert.notes),
        "intelligence_title": _safe_text(intelligence.title) if intelligence else None,
        "cve_id": intelligence.cve_id if intelligence else None,
        "source_names": _join(intelligence.source_names) if intelligence else None,
    }


def _intelligence_markdown(detail: dict[str, Any]) -> str:
    lines = [
        f"# {_safe_text(detail.get('title')) or 'Intelligence'}",
        "",
        f"- ID: {detail.get('id')}",
        f"- Type: {detail.get('intelligence_type')}",
        f"- Status: {detail.get('status')}",
        f"- CVE: {detail.get('cve_id') or '-'}",
        f"- Severity: {detail.get('severity')}",
        f"- Risk: {detail.get('risk_level')} ({detail.get('risk_score') or '-'})",
        f"- Vendor: {_safe_text(detail.get('affected_vendor')) or '-'}",
        f"- Product: {_safe_text(detail.get('affected_product')) or '-'}",
        "",
        "## Summary",
        "",
        _safe_text(detail.get("summary")) or "-",
        "",
        "## Sources",
        "",
    ]
    sources = detail.get("sources") or []
    if sources:
        for source in sources:
            source_name = _safe_text(source.get("source_name")) or "source"
            source_url = safe_url(source.get("source_url")) or ""
            external_id = _safe_text(source.get("external_id"))
            suffix = f" ({external_id})" if external_id else ""
            lines.append(f"- {source_name}: {source_url}{suffix}")
    else:
        for source_name, source_url in zip(detail.get("source_names") or [], detail.get("source_urls") or []):
            lines.append(f"- {_safe_text(source_name) or 'source'}: {safe_url(source_url) or ''}")
    lines.extend(["", "## Related Alerts", ""])
    alerts = detail.get("related_alerts") or []
    if alerts:
        for alert in alerts:
            lines.append(
                f"- {_safe_text(alert.get('title')) or alert.get('id')}: {alert.get('risk_level')} / {alert.get('status')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _summary_pdf(intelligence: list[ThreatIntelligence], alerts: list[Alert]) -> bytes:
    high_risk = sum(1 for entry in intelligence if _enum_value(entry.risk_level) in {"high", "critical"})
    open_alerts = sum(1 for alert in alerts if _enum_value(alert.status) == "open")
    lines = [
        "SentinelDrive Security Summary",
        f"Generated at: {datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"Intelligence rows included: {len(intelligence)}",
        f"High or critical intelligence: {high_risk}",
        f"Alerts included: {len(alerts)}",
        f"Open alerts: {open_alerts}",
        "",
        "Top Intelligence",
    ]
    for entry in intelligence[:8]:
        lines.append(
            f"- {entry.cve_id or 'no-cve'} | {_enum_value(entry.risk_level)} | {_safe_text(entry.title) or entry.id}"
        )
    lines.extend(["", "Top Alerts"])
    for alert in alerts[:8]:
        lines.append(f"- {_enum_value(alert.risk_level)} | {_enum_value(alert.status)} | {_safe_text(alert.title) or alert.id}")
    return _build_simple_pdf(lines)


def _build_simple_pdf(lines: list[str]) -> bytes:
    content_lines: list[str] = []
    y = 744
    for index, line in enumerate(_wrap_pdf_lines(lines)):
        size = 16 if index == 0 else 10
        content_lines.append(f"BT /F1 {size} Tf 72 {y} Td ({_pdf_escape(line)}) Tj ET")
        y -= 18 if index == 0 else 14
        if y < 72:
            break
    stream = "\n".join(content_lines).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = io.BytesIO()
    pdf.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(pdf.tell())
        pdf.write(f"{index} 0 obj\n".encode("ascii"))
        pdf.write(obj)
        pdf.write(b"\nendobj\n")
    xref_offset = pdf.tell()
    pdf.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
    return pdf.getvalue()


def _wrap_pdf_lines(lines: list[str]) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(_pdf_text(line), width=92) or [""])
    return wrapped


def _csv_response(filename: str, headers: list[str], rows: list[dict[str, Any]]) -> Response:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return _download_response(output.getvalue(), media_type="text/csv; charset=utf-8", filename=filename)


def _download_response(content: str | bytes, *, media_type: str, filename: str) -> Response:
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    return safe_text(str(value))


def _join(values: list[Any]) -> str:
    return " | ".join(str(value) for value in values if value is not None)


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(value: str) -> str:
    return value.encode("latin-1", "replace").decode("latin-1")
