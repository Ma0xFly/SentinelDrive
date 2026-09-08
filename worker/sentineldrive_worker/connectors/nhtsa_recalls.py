from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sentineldrive_worker.connectors.config import DEFAULT_NHTSA_VEHICLES
from sentineldrive_worker.connectors.contracts import (
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    RawIntelligencePayload,
    SourceConfig,
)
from sentineldrive_worker.connectors.dates import ensure_utc, parse_datetime
from sentineldrive_worker.connectors.http import HttpClient, HttpResponse

NHTSA_RECALLS_BASE_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"
DEFAULT_MODEL_YEARS = 4

# 软件/OTA 相关召回的降噪关键词。命中 Component 或 Summary 即视为软件相关，
# 与 overTheAirUpdate 布尔位一起用于采集层过滤机械类召回。
SOFTWARE_KEYWORDS = (
    "software",
    "telematics",
    "cyber",
    "ota",
    "over the air",
    "over-the-air",
    "firmware",
    "infotainment",
    "electronic control unit",
    "ecu",
    "remote update",
    "wireless update",
    "connected services",
    "mobile app",
)

@dataclass
class NhtsaRecallsConnector:
    source: SourceConfig
    http_client: HttpClient | None = None
    now_factory: callable | None = None

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        http = self.http_client or HttpClient()
        now = ensure_utc(self.now_factory() if self.now_factory else datetime.now(timezone.utc))
        vehicles = list(self.source.metadata.get("vehicles") or DEFAULT_NHTSA_VEHICLES)
        model_years = int(self.source.metadata.get("model_years") or DEFAULT_MODEL_YEARS)
        seen = parse_seen_campaigns(context.cursor)

        items: list[RawIntelligencePayload] = []
        vehicle_errors: list[dict[str, Any]] = []
        requests_made = 0

        for vehicle in vehicles:
            if not isinstance(vehicle, Mapping):
                vehicle_errors.append({"error": "车辆条目必须是对象"})
                continue
            make = str(vehicle.get("make") or "").strip()
            model = str(vehicle.get("model") or "").strip()
            if not make or not model:
                vehicle_errors.append({"error": "车辆条目缺少 make/model"})
                continue
            for model_year in model_year_range(now.year, model_years):
                requests_made += 1
                try:
                    response = http.get(
                        self.source.base_url or NHTSA_RECALLS_BASE_URL,
                        query={"make": make, "model": model, "modelYear": model_year},
                        headers={"User-Agent": "SentinelDrive/0.1"},
                        timeout_seconds=self.source.timeout_seconds,
                    )
                    require_success(response, "NHTSA recalls")
                    for entry in parse_recalls(response):
                        payload = recall_payload(self.source, entry, make, model, model_year, response.url, seen)
                        if payload is None:
                            continue
                        items.append(payload)
                        seen.add(payload.external_id)
                except Exception as exc:
                    vehicle_errors.append(
                        {"make": make, "model": model, "modelYear": model_year, "error": sanitized_error(exc)}
                    )

        if not items and vehicle_errors:
            raise ConnectorError(f"全部 NHTSA 召回请求失败：{vehicle_errors[0]['error']}")

        return ConnectorResult(
            items=tuple(items),
            next_cursor=json.dumps({"seen_campaigns": sorted(seen)}, sort_keys=True),
            metadata={
                "connector": "nhtsa-recalls",
                "vehicles_seen": len(vehicles),
                "requests_made": requests_made,
                "items_collected": len(items),
                "vehicle_errors": vehicle_errors,
            },
        )


def model_year_range(base_year: int, count: int) -> list[int]:
    if count <= 0:
        return []
    return list(range(base_year - count + 1, base_year + 1))


def require_success(response: HttpResponse, source_label: str) -> None:
    if response.status_code < 200 or response.status_code >= 300:
        raise ConnectorError(f"{source_label} 返回 HTTP {response.status_code}")


def parse_recalls(response: HttpResponse) -> list[dict[str, Any]]:
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ConnectorError("NHTSA recalls 返回的 JSON 格式错误") from exc
    if not isinstance(payload, dict):
        raise ConnectorError("NHTSA recalls 的 JSON 响应必须是对象")
    results = payload.get("Results")
    if results is None:
        if int(payload.get("Count") or 0) == 0:
            return []
        raise ConnectorError("NHTSA recalls 响应缺少 Results 数组")
    if not isinstance(results, list):
        raise ConnectorError("NHTSA recalls 的 Results 必须是数组")
    return [entry for entry in results if isinstance(entry, dict)]


def recall_payload(
    source: SourceConfig,
    entry: Mapping[str, Any],
    make: str,
    model: str,
    model_year: int,
    response_url: str,
    seen: set[str],
) -> RawIntelligencePayload | None:
    campaign = first_value(entry, "NHTSACampaignNumber", "nhtsaCampaignNumber", "campaignNumber", "campaign_number")
    if not campaign:
        return None
    if campaign in seen:
        return None

    component = first_value(entry, "Component", "component")
    summary = first_value(entry, "Summary", "summary")
    over_the_air = bool_value(first_value(entry, "OverTheAirUpdate", "overTheAirUpdate", "over_the_air_update"))
    software_related = over_the_air or has_software_keyword(component, summary)
    if not software_related:
        return None

    report_date = parse_datetime(first_value(entry, "ReportReceivedDate", "reportReceivedDate")) or parse_datetime(
        first_value(entry, "report_received_date")
    )
    title = f"{make} {model} {model_year} 召回 {campaign}"
    metadata = {
        "make": make,
        "model": model,
        "model_year": model_year,
        "campaign_number": campaign,
        "manufacturer": first_value(entry, "Manufacturer", "manufacturer"),
        "report_received_date": first_value(entry, "ReportReceivedDate", "reportReceivedDate"),
        "component": component,
        "recall_type": first_value(entry, "Type", "RecallType"),
        "over_the_air_update": over_the_air,
        "software_related": software_related,
        "response_url": response_url,
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=f"https://www.nhtsa.gov/recalls?campaignNumber={campaign}",
        external_id=campaign,
        title=title,
        summary=summary,
        snippet=(summary or "")[:500] or None,
        raw_content=safe_recall_content(entry, campaign, make, model, model_year, over_the_air),
        first_seen_at=report_date,
        metadata=metadata,
    )


def safe_recall_content(
    entry: Mapping[str, Any],
    campaign: str,
    make: str,
    model: str,
    model_year: int,
    over_the_air: bool,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        "campaign_number": campaign,
        "make": make,
        "model": model,
        "model_year": model_year,
        "over_the_air_update": over_the_air,
    }
    for key in (
        "ReportReceivedDate",
        "Component",
        "Summary",
        "Conequence",
        "Remedy",
        "Manufacturer",
        "Type",
        "PotentialNumberofUnitsAffected",
    ):
        if key in entry and entry[key] is not None:
            content[key] = entry[key]
    return content


def parse_seen_campaigns(cursor: str | None) -> set[str]:
    if not cursor:
        return set()
    try:
        parsed = json.loads(cursor)
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, dict):
        return set()
    values = parsed.get("seen_campaigns")
    if not isinstance(values, list):
        return set()
    return {str(value).strip() for value in values if str(value).strip()}


def first_value(entry: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def bool_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def has_software_keyword(*values: object) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    return any(keyword in text for keyword in SOFTWARE_KEYWORDS)


def sanitized_error(error: BaseException) -> str:
    text = str(error) or error.__class__.__name__
    return text[:300]