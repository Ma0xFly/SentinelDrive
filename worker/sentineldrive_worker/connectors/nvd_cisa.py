from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from sentineldrive_worker.connectors.contracts import (
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    RawIntelligencePayload,
    SourceConfig,
)
from sentineldrive_worker.connectors.dates import ensure_utc, isoformat_utc, parse_datetime
from sentineldrive_worker.connectors.http import HttpClient, HttpResponse

DEFAULT_NVD_WINDOW_DAYS = 120
DEFAULT_NVD_RESULTS_PER_PAGE = 100
DEFAULT_NVD_MAX_PAGES = 2
MAX_RAW_PAYLOAD_BYTES = 256_000


@dataclass
class NvdConnector:
    source: SourceConfig
    http_client: HttpClient | None = None
    now_factory: callable | None = None

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        http = self.http_client or HttpClient()
        now = ensure_utc(self.now_factory() if self.now_factory else datetime.now(timezone.utc))
        cursor = parse_nvd_cursor(context.cursor)
        start_index = int(cursor.get("next_start_index", 0))
        if start_index > 0 and cursor.get("last_mod_start") and cursor.get("last_mod_end"):
            window_start = cursor["last_mod_start"]
            window_end = cursor["last_mod_end"]
        else:
            window_start = cursor.get("last_mod_end") or now - timedelta(days=DEFAULT_NVD_WINDOW_DAYS)
            window_end = now
        results_per_page = int(self.source.metadata.get("results_per_page", DEFAULT_NVD_RESULTS_PER_PAGE))
        max_pages = int(self.source.metadata.get("max_pages_per_run", DEFAULT_NVD_MAX_PAGES))
        headers = {"User-Agent": "SentinelDrive/0.1"}
        api_key = self.source.credentials.get("api_key")
        if api_key:
            headers["apiKey"] = api_key

        items: list[RawIntelligencePayload] = []
        pages_fetched = 0
        total_results = 0
        next_start_index = start_index

        while pages_fetched < max_pages:
            query = {
                "lastModStartDate": isoformat_utc(window_start),
                "lastModEndDate": isoformat_utc(window_end),
                "startIndex": next_start_index,
                "resultsPerPage": results_per_page,
            }
            response = http.get(
                self.source.base_url or "",
                query=query,
                headers=headers,
                timeout_seconds=self.source.timeout_seconds,
            )
            require_success(response, "NVD")
            payload = parse_json_response(response, "NVD")
            vulnerabilities = payload.get("vulnerabilities")
            if not isinstance(vulnerabilities, list):
                raise ConnectorError("NVD response missing vulnerabilities array")

            total_results = int(payload.get("totalResults") or len(vulnerabilities))
            for entry in vulnerabilities:
                if not isinstance(entry, dict):
                    raise ConnectorError("NVD vulnerability entry is not an object")
                items.append(nvd_payload(self.source, entry, response.url))

            pages_fetched += 1
            next_start_index += len(vulnerabilities)
            if len(vulnerabilities) == 0 or next_start_index >= total_results:
                break

        if next_start_index >= total_results:
            cursor_payload = {
                "last_mod_end": isoformat_utc(window_end),
                "next_start_index": 0,
            }
        else:
            cursor_payload = {
                "last_mod_start": isoformat_utc(window_start),
                "last_mod_end": isoformat_utc(window_end),
                "next_start_index": next_start_index,
            }

        return ConnectorResult(
            items=tuple(items),
            next_cursor=json.dumps(cursor_payload, sort_keys=True),
            metadata={
                "connector": "nvd",
                "pages_fetched": pages_fetched,
                "items_collected": len(items),
                "total_results": total_results,
                "api_key_configured": bool(api_key),
                "window_start": isoformat_utc(window_start),
                "window_end": isoformat_utc(window_end),
            },
        )


@dataclass
class CisaKevConnector:
    source: SourceConfig
    http_client: HttpClient | None = None

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        http = self.http_client or HttpClient()
        response = http.get(
            self.source.base_url or "",
            headers={"User-Agent": "SentinelDrive/0.1"},
            timeout_seconds=self.source.timeout_seconds,
        )
        require_success(response, "CISA KEV")
        entries = parse_kev_response(response)
        if not entries:
            raise ConnectorError("CISA KEV response did not contain vulnerabilities")

        items = [kev_payload(self.source, entry, response.url) for entry in entries]
        latest_marker = latest_kev_marker(entries)
        return ConnectorResult(
            items=tuple(items),
            next_cursor=json.dumps({"latest_date_added": latest_marker}, sort_keys=True),
            metadata={
                "connector": "cisa-kev",
                "items_collected": len(items),
                "latest_date_added": latest_marker,
                "content_type": response.headers.get("content-type") or response.headers.get("Content-Type"),
            },
        )


def parse_nvd_cursor(cursor: str | None) -> dict[str, Any]:
    if not cursor:
        return {}
    try:
        parsed = json.loads(cursor)
    except json.JSONDecodeError as exc:
        raise ConnectorError("NVD cursor is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ConnectorError("NVD cursor must be a JSON object")

    result: dict[str, Any] = {}
    if parsed.get("last_mod_end"):
        value = parse_datetime(parsed["last_mod_end"])
        if not value:
            raise ConnectorError("NVD cursor last_mod_end is not a valid datetime")
        result["last_mod_end"] = value
    if parsed.get("last_mod_start"):
        value = parse_datetime(parsed["last_mod_start"])
        if not value:
            raise ConnectorError("NVD cursor last_mod_start is not a valid datetime")
        result["last_mod_start"] = value
    if parsed.get("next_start_index") is not None:
        result["next_start_index"] = int(parsed["next_start_index"])
    return result


def require_success(response: HttpResponse, source_label: str) -> None:
    if response.status_code < 200 or response.status_code >= 300:
        raise ConnectorError(f"{source_label} returned HTTP {response.status_code}")


def parse_json_response(response: HttpResponse, source_label: str) -> dict[str, Any]:
    try:
        payload = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise ConnectorError(f"{source_label} returned malformed JSON") from exc
    if not isinstance(payload, dict):
        raise ConnectorError(f"{source_label} JSON response must be an object")
    return payload


def nvd_payload(source: SourceConfig, entry: Mapping[str, Any], response_url: str) -> RawIntelligencePayload:
    cve = entry.get("cve")
    if not isinstance(cve, dict):
        raise ConnectorError("NVD vulnerability entry missing cve object")
    cve_id = str(cve.get("id") or "").strip()
    if not cve_id:
        raise ConnectorError("NVD vulnerability entry missing CVE ID")

    published = parse_datetime(cve.get("published"))
    last_modified = parse_datetime(cve.get("lastModified"))
    descriptions = cve.get("descriptions") if isinstance(cve.get("descriptions"), list) else []
    summary = best_nvd_description(descriptions)
    source_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
    metadata = {
        "published": cve.get("published"),
        "last_modified": cve.get("lastModified"),
        "vuln_status": cve.get("vulnStatus"),
        "cvss": extract_cvss(cve),
        "cwe": extract_cwe(cve),
        "reference_count": len(cve.get("references", {}).get("referenceData", []))
        if isinstance(cve.get("references"), dict)
        else 0,
        "response_url": response_url,
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=source_url,
        external_id=cve_id,
        title=f"{cve_id} - {summary[:120]}" if summary else cve_id,
        summary=summary,
        snippet=summary[:500] if summary else None,
        raw_content=bounded_raw_content(entry),
        fetched_at=datetime.now(timezone.utc),
        first_seen_at=published or last_modified,
        metadata=metadata,
    )


def best_nvd_description(descriptions: list[Any]) -> str | None:
    for description in descriptions:
        if isinstance(description, dict) and description.get("lang") == "en" and description.get("value"):
            return str(description["value"])
    for description in descriptions:
        if isinstance(description, dict) and description.get("value"):
            return str(description["value"])
    return None


def extract_cvss(cve: Mapping[str, Any]) -> dict[str, Any]:
    metrics = cve.get("metrics")
    if not isinstance(metrics, dict):
        return {}
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        values = metrics.get(key)
        if isinstance(values, list) and values:
            first = values[0]
            if isinstance(first, dict):
                data = first.get("cvssData")
                if isinstance(data, dict):
                    return {
                        "version": data.get("version"),
                        "base_score": data.get("baseScore"),
                        "base_severity": data.get("baseSeverity") or first.get("baseSeverity"),
                        "vector_string": data.get("vectorString"),
                    }
    return {}


def extract_cwe(cve: Mapping[str, Any]) -> list[str]:
    weaknesses = cve.get("weaknesses")
    cwes: list[str] = []
    if not isinstance(weaknesses, list):
        return cwes
    for weakness in weaknesses:
        descriptions = weakness.get("description") if isinstance(weakness, dict) else None
        if not isinstance(descriptions, list):
            continue
        for description in descriptions:
            value = description.get("value") if isinstance(description, dict) else None
            if isinstance(value, str) and value.startswith("CWE-") and value not in cwes:
                cwes.append(value)
    return cwes


def parse_kev_response(response: HttpResponse) -> list[dict[str, Any]]:
    content_type = (response.headers.get("content-type") or response.headers.get("Content-Type") or "").lower()
    text = response.text
    if "csv" in content_type or response.url.lower().endswith(".csv"):
        return parse_kev_csv(text)
    payload = parse_json_response(response, "CISA KEV")
    vulnerabilities = payload.get("vulnerabilities")
    if not isinstance(vulnerabilities, list):
        raise ConnectorError("CISA KEV response missing vulnerabilities array")
    entries: list[dict[str, Any]] = []
    for entry in vulnerabilities:
        if not isinstance(entry, dict):
            raise ConnectorError("CISA KEV vulnerability entry is not an object")
        entries.append(entry)
    return entries


def parse_kev_csv(text: str) -> list[dict[str, Any]]:
    try:
        rows = list(csv.DictReader(io.StringIO(text)))
    except csv.Error as exc:
        raise ConnectorError("CISA KEV returned malformed CSV") from exc
    if not rows:
        raise ConnectorError("CISA KEV CSV did not contain rows")
    return [{str(key): value for key, value in row.items()} for row in rows]


def kev_payload(source: SourceConfig, entry: Mapping[str, Any], response_url: str) -> RawIntelligencePayload:
    cve_id = first_value(entry, "cveID", "cve_id", "CVE ID")
    if not cve_id:
        raise ConnectorError("CISA KEV entry missing CVE ID")
    vulnerability_name = first_value(entry, "vulnerabilityName", "vulnerability_name") or cve_id
    vendor = first_value(entry, "vendorProject", "vendor_project")
    product = first_value(entry, "product")
    date_added = first_value(entry, "dateAdded", "date_added")
    due_date = first_value(entry, "dueDate", "due_date")
    known_ransomware = first_value(entry, "knownRansomwareCampaignUse", "known_ransomware_campaign_use")
    notes = first_value(entry, "notes")
    cwes = normalize_cwe_values(entry.get("cwes") or entry.get("CWE"))
    summary = f"{vendor or 'Unknown vendor'} {product or 'unknown product'}: {vulnerability_name}"
    if notes:
        summary = f"{summary}. {notes}"
    date_added_dt = parse_datetime(date_added)
    metadata = {
        "vendor_project": vendor,
        "product": product,
        "vulnerability_name": vulnerability_name,
        "date_added": date_added,
        "due_date": due_date,
        "known_ransomware_campaign_use": known_ransomware,
        "notes": notes,
        "cwes": cwes,
        "response_url": response_url,
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext={cve_id}",
        external_id=cve_id,
        title=f"{cve_id} - {vulnerability_name}",
        summary=summary,
        snippet=summary[:500],
        raw_content=bounded_raw_content(dict(entry)),
        first_seen_at=date_added_dt,
        metadata=metadata,
    )


def first_value(entry: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = entry.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def normalize_cwe_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace(";", ",").split(",") if item.strip()]


def latest_kev_marker(entries: list[Mapping[str, Any]]) -> str | None:
    dates = [
        date
        for date in (first_value(entry, "dateAdded", "date_added") for entry in entries)
        if date
    ]
    return max(dates) if dates else None


def bounded_raw_content(value: Mapping[str, Any]) -> Mapping[str, Any] | None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    if len(serialized.encode("utf-8")) > MAX_RAW_PAYLOAD_BYTES:
        return None
    return dict(value)
