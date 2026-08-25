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
        "编号",
        "标题",
        "摘要",
        "情报类型",
        "CVE 编号",
        "严重度",
        "风险等级",
        "风险评分",
        "状态",
        "受影响厂商",
        "受影响产品",
        "车辆组件",
        "攻击面",
        "数据源名称",
        "数据源链接",
        "首次发现时间",
        "最近更新时间",
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
        "编号",
        "标题",
        "关联情报编号",
        "触发规则",
        "风险等级",
        "状态",
        "触发时间",
        "备注",
        "情报标题",
        "CVE 编号",
        "数据源名称",
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
        "编号": str(entry.id),
        "标题": _safe_text(entry.title),
        "摘要": _safe_text(entry.summary),
        "情报类型": _enum_value(entry.intelligence_type),
        "CVE 编号": entry.cve_id,
        "严重度": _enum_value(entry.severity),
        "风险等级": _enum_value(entry.risk_level),
        "风险评分": _number(entry.risk_score),
        "状态": entry.status,
        "受影响厂商": _safe_text(entry.affected_vendor),
        "受影响产品": _safe_text(entry.affected_product),
        "车辆组件": _enum_value(entry.vehicle_component),
        "攻击面": _enum_value(entry.attack_surface),
        "数据源名称": _join(entry.source_names or []),
        "数据源链接": _join([clean_url for url in (entry.source_urls or []) if (clean_url := safe_url(url))]),
        "首次发现时间": _iso(entry.first_seen_at),
        "最近更新时间": _iso(entry.last_seen_at),
    }


def _alert_csv_row(alert: Alert) -> dict[str, Any]:
    detail = _alert_detail_response(alert)
    intelligence = detail.intelligence
    return {
        "编号": str(alert.id),
        "标题": _safe_text(alert.title),
        "关联情报编号": str(alert.threat_intelligence_id),
        "触发规则": alert.triggering_rule,
        "风险等级": _enum_value(alert.risk_level),
        "状态": _enum_value(alert.status),
        "触发时间": _iso(alert.triggered_at),
        "备注": _safe_text(alert.notes),
        "情报标题": _safe_text(intelligence.title) if intelligence else None,
        "CVE 编号": intelligence.cve_id if intelligence else None,
        "数据源名称": _join(intelligence.source_names) if intelligence else None,
    }


def _intelligence_markdown(detail: dict[str, Any]) -> str:
    lines = [
        f"# {_safe_text(detail.get('title')) or '情报条目'}",
        "",
        f"- 编号：{detail.get('id')}",
        f"- 类型：{detail.get('intelligence_type')}",
        f"- 状态：{detail.get('status')}",
        f"- CVE：{detail.get('cve_id') or '-'}",
        f"- 严重度：{detail.get('severity')}",
        f"- 风险：{detail.get('risk_level')}（{detail.get('risk_score') or '-'}）",
        f"- 厂商：{_safe_text(detail.get('affected_vendor')) or '-'}",
        f"- 产品：{_safe_text(detail.get('affected_product')) or '-'}",
        "",
        "## 摘要",
        "",
        _safe_text(detail.get("summary")) or "-",
        "",
        "## 数据源",
        "",
    ]
    sources = detail.get("sources") or []
    if sources:
        for source in sources:
            source_name = _safe_text(source.get("source_name")) or "数据源"
            source_url = safe_url(source.get("source_url")) or ""
            external_id = _safe_text(source.get("external_id"))
            suffix = f" ({external_id})" if external_id else ""
            lines.append(f"- {source_name}: {source_url}{suffix}")
    else:
        for source_name, source_url in zip(detail.get("source_names") or [], detail.get("source_urls") or []):
            lines.append(f"- {_safe_text(source_name) or '数据源'}: {safe_url(source_url) or ''}")
    lines.extend(["", "## 关联告警", ""])
    alerts = detail.get("related_alerts") or []
    if alerts:
        for alert in alerts:
            lines.append(
                f"- {_safe_text(alert.get('title')) or alert.get('id')}: {alert.get('risk_level')} / {alert.get('status')}"
            )
    else:
        lines.append("- 暂无")
    lines.append("")
    return "\n".join(lines)


def _summary_pdf(intelligence: list[ThreatIntelligence], alerts: list[Alert]) -> bytes:
    high_risk = sum(1 for entry in intelligence if _enum_value(entry.risk_level) in {"high", "critical"})
    open_alerts = sum(1 for alert in alerts if _enum_value(alert.status) == "open")
    lines = [
        "SentinelDrive 安全摘要",
        f"生成时间：{datetime.utcnow().isoformat(timespec='seconds')}Z",
        f"收录情报条数：{len(intelligence)}",
        f"高风险或严重情报：{high_risk}",
        f"收录告警数：{len(alerts)}",
        f"未关闭告警：{open_alerts}",
        "",
        "重点情报",
    ]
    for entry in intelligence[:8]:
        lines.append(
            f"- {entry.cve_id or '无 CVE'} | {_enum_value(entry.risk_level)} | {_safe_text(entry.title) or entry.id}"
        )
    lines.extend(["", "重点告警"])
    for alert in alerts[:8]:
        lines.append(f"- {_enum_value(alert.risk_level)} | {_enum_value(alert.status)} | {_safe_text(alert.title) or alert.id}")
    return _build_simple_pdf(lines)


def _build_simple_pdf(lines: list[str]) -> bytes:
    # 文本以 UTF-16BE hex 字符串写入，字体引用 PDF 阅读器内置的 STSong-Light
    # CJK 字体，避免 latin-1 编码把中文内容替换成问号。
    content_lines: list[str] = []
    y = 744
    for index, line in enumerate(_wrap_pdf_lines(lines)):
        size = 16 if index == 0 else 10
        hex_text = _pdf_hex(line)
        content_lines.append(f"BT /F1 {size} Tf 72 {y} Td <{hex_text}> Tj ET")
        y -= 18 if index == 0 else 14
        if y < 72:
            break
    stream = "\n".join(content_lines).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [6 0 R] >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 5 >> /DW 1000 >>",
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
        wrapped.extend(textwrap.wrap(line, width=46, break_on_hyphens=False) or [""])
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


def _pdf_hex(value: str) -> str:
    return value.encode("utf-16-be").hex().upper()
