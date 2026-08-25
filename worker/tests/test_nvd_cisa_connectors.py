from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from sentineldrive_worker.connectors.contracts import ConnectorContext, ConnectorError, SourceConfig, SourceType
from sentineldrive_worker.connectors.http import HttpResponse
from sentineldrive_worker.connectors.nvd_cisa import CisaKevConnector, NvdConnector
from sentineldrive_worker.connectors.registry import ConnectorRegistry
from sentineldrive_worker.connectors.samples import register_builtin_connectors


def source_config(name: str, **overrides) -> SourceConfig:
    values = {
        "name": name,
        "source_type": SourceType.API,
        "enabled": True,
        "base_url": f"https://example.test/{name}",
        "sync_interval_seconds": 3600,
        "timeout_seconds": 5.0,
        "rate_limit_per_minute": 20,
        "metadata": {"connector": name},
    }
    values.update(overrides)
    return SourceConfig(**values)


def test_builtin_registry_registers_nvd_and_cisa():
    registry = ConnectorRegistry()

    register_builtin_connectors(registry)

    assert "nvd" in registry.available()
    assert "cisa-kev" in registry.available()


def test_nvd_uses_supported_default_window_and_api_key_header():
    now = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)
    http = FakeHttpClient([nvd_response(total_results=1, cve_id="CVE-2026-0001")])
    source = source_config(
        "nvd",
        base_url="https://services.nvd.nist.gov/rest/json/cves/2.0",
        credentials={"api_key": "secret-key"},
    )
    connector = NvdConnector(source, http_client=http, now_factory=lambda: now)

    result = connector.collect(ConnectorContext(source=source))

    request = http.requests[0]
    assert request["headers"]["apiKey"] == "secret-key"
    assert request["query"]["lastModStartDate"] == "2026-01-19T12:00:00Z"
    assert request["query"]["lastModEndDate"] == "2026-05-19T12:00:00Z"
    assert request["query"]["startIndex"] == 0
    assert request["query"]["resultsPerPage"] == 100
    assert result.items[0].external_id == "CVE-2026-0001"
    assert result.items[0].source_url == "https://nvd.nist.gov/vuln/detail/CVE-2026-0001"
    assert result.items[0].metadata["cvss"]["base_score"] == 9.8
    assert result.items[0].metadata["cwe"] == ["CWE-787"]
    assert json.loads(result.next_cursor)["last_mod_end"] == "2026-05-19T12:00:00Z"


def test_nvd_without_api_key_omits_header():
    http = FakeHttpClient([nvd_response(total_results=0, vulnerabilities=[])])
    source = source_config("nvd", base_url="https://services.nvd.nist.gov/rest/json/cves/2.0")
    connector = NvdConnector(source, http_client=http, now_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))

    connector.collect(ConnectorContext(source=source))

    assert "apiKey" not in http.requests[0]["headers"]


def test_nvd_paginates_with_conservative_per_run_limit():
    http = FakeHttpClient(
        [
            nvd_response(total_results=3, cve_id="CVE-2026-0001"),
            nvd_response(total_results=3, cve_id="CVE-2026-0002"),
        ]
    )
    source = source_config(
        "nvd",
        base_url="https://services.nvd.nist.gov/rest/json/cves/2.0",
        metadata={"connector": "nvd", "results_per_page": 1, "max_pages_per_run": 2},
    )

    result = NvdConnector(source, http_client=http, now_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)).collect(
        ConnectorContext(source=source)
    )

    assert len(http.requests) == 2
    assert [request["query"]["startIndex"] for request in http.requests] == [0, 1]
    assert [item.external_id for item in result.items] == ["CVE-2026-0001", "CVE-2026-0002"]
    assert json.loads(result.next_cursor)["next_start_index"] == 2


def test_nvd_cursor_resumes_from_last_window_page():
    http = FakeHttpClient([nvd_response(total_results=3, cve_id="CVE-2026-0003")])
    source = source_config(
        "nvd",
        base_url="https://services.nvd.nist.gov/rest/json/cves/2.0",
        metadata={"connector": "nvd", "results_per_page": 1, "max_pages_per_run": 1},
    )
    cursor = json.dumps(
        {
            "last_mod_start": "2025-01-01T00:00:00Z",
            "last_mod_end": "2025-01-02T00:00:00Z",
            "next_start_index": 2,
        }
    )

    NvdConnector(source, http_client=http, now_factory=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)).collect(
        ConnectorContext(source=source, cursor=cursor)
    )

    assert http.requests[0]["query"]["lastModStartDate"] == "2025-01-01T00:00:00Z"
    assert http.requests[0]["query"]["lastModEndDate"] == "2025-01-02T00:00:00Z"
    assert http.requests[0]["query"]["startIndex"] == 2


def test_nvd_non_2xx_and_malformed_payloads_raise_clear_errors():
    source = source_config("nvd", base_url="https://services.nvd.nist.gov/rest/json/cves/2.0")
    with pytest.raises(ConnectorError, match="NVD 返回 HTTP 503"):
        NvdConnector(source, http_client=FakeHttpClient([HttpResponse(source.base_url, 503, {}, b"down")])).collect(
            ConnectorContext(source=source)
        )
    with pytest.raises(ConnectorError, match="NVD 返回的 JSON 格式错误"):
        NvdConnector(source, http_client=FakeHttpClient([HttpResponse(source.base_url, 200, {}, b"{")])).collect(
            ConnectorContext(source=source)
        )


def test_nvd_output_is_idempotent_for_same_input():
    source = source_config("nvd", base_url="https://services.nvd.nist.gov/rest/json/cves/2.0")
    first = NvdConnector(source, http_client=FakeHttpClient([nvd_response(total_results=1)])).collect(ConnectorContext(source=source))
    second = NvdConnector(source, http_client=FakeHttpClient([nvd_response(total_results=1)])).collect(ConnectorContext(source=source))

    assert first.items[0].raw_hash == second.items[0].raw_hash
    assert first.items[0].content_hash == second.items[0].content_hash


def test_cisa_kev_parses_official_json_shape():
    source = source_config("cisa-kev", base_url="https://www.cisa.gov/feed.json")
    response = HttpResponse(
        source.base_url,
        200,
        {"content-type": "application/json"},
        json.dumps({"vulnerabilities": [kev_entry("CVE-2025-1111")]}).encode(),
    )

    result = CisaKevConnector(source, http_client=FakeHttpClient([response])).collect(ConnectorContext(source=source))

    item = result.items[0]
    assert item.external_id == "CVE-2025-1111"
    assert item.title == "CVE-2025-1111 - Test KEV vulnerability"
    assert item.metadata["vendor_project"] == "ExampleVendor"
    assert item.metadata["cwes"] == ["CWE-79", "CWE-89"]
    assert json.loads(result.next_cursor)["latest_date_added"] == "2025-03-01"


def test_cisa_kev_parses_csv_shape():
    source = source_config("cisa-kev", base_url="https://www.cisa.gov/feed.csv")
    csv_body = (
        "cveID,vendorProject,product,vulnerabilityName,dateAdded,dueDate,knownRansomwareCampaignUse,notes,cwes\n"
        "CVE-2025-2222,Vendor,Product,CSV vulnerability,2025-04-01,2025-04-21,Known,CSV notes,CWE-787\n"
    )

    result = CisaKevConnector(
        source,
        http_client=FakeHttpClient([HttpResponse(source.base_url, 200, {"content-type": "text/csv"}, csv_body.encode())]),
    ).collect(ConnectorContext(source=source))

    assert result.items[0].external_id == "CVE-2025-2222"
    assert result.items[0].metadata["known_ransomware_campaign_use"] == "Known"


def test_cisa_kev_malformed_payloads_raise_clear_errors():
    source = source_config("cisa-kev", base_url="https://www.cisa.gov/feed.json")

    with pytest.raises(ConnectorError, match="CISA KEV 响应缺少 vulnerabilities 数组"):
        CisaKevConnector(
            source,
            http_client=FakeHttpClient([HttpResponse(source.base_url, 200, {"content-type": "application/json"}, b"{}")]),
        ).collect(ConnectorContext(source=source))
    with pytest.raises(ConnectorError, match="CISA KEV 条目缺少 CVE 编号"):
        CisaKevConnector(
            source,
            http_client=FakeHttpClient(
                [HttpResponse(source.base_url, 200, {"content-type": "application/json"}, b'{"vulnerabilities":[{}]}')]
            ),
        ).collect(ConnectorContext(source=source))


class FakeHttpClient:
    def __init__(self, responses: list[HttpResponse]):
        self._responses = responses
        self.requests: list[dict[str, object]] = []

    def get(self, url, *, query=None, headers=None, timeout_seconds=20.0):
        self.requests.append(
            {
                "url": url,
                "query": dict(query or {}),
                "headers": dict(headers or {}),
                "timeout_seconds": timeout_seconds,
            }
        )
        return self._responses.pop(0)


def nvd_response(total_results=1, cve_id="CVE-2026-0001", vulnerabilities=None):
    if vulnerabilities is None:
        vulnerabilities = [nvd_entry(cve_id)]
    payload = {
        "resultsPerPage": len(vulnerabilities),
        "startIndex": 0,
        "totalResults": total_results,
        "vulnerabilities": vulnerabilities,
    }
    return HttpResponse("https://services.nvd.nist.gov/rest/json/cves/2.0", 200, {"content-type": "application/json"}, json.dumps(payload).encode())


def nvd_entry(cve_id):
    return {
        "cve": {
            "id": cve_id,
            "published": "2026-01-01T00:00:00.000",
            "lastModified": "2026-01-02T00:00:00.000",
            "vulnStatus": "Analyzed",
            "descriptions": [{"lang": "en", "value": "Buffer overflow in vehicle telematics firmware."}],
            "metrics": {
                "cvssMetricV31": [
                    {
                        "cvssData": {
                            "version": "3.1",
                            "baseScore": 9.8,
                            "baseSeverity": "CRITICAL",
                            "vectorString": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                        }
                    }
                ]
            },
            "weaknesses": [{"description": [{"lang": "en", "value": "CWE-787"}]}],
            "references": {"referenceData": [{"url": "https://example.test/advisory"}]},
        }
    }


def kev_entry(cve_id):
    return {
        "cveID": cve_id,
        "vendorProject": "ExampleVendor",
        "product": "ExampleProduct",
        "vulnerabilityName": "Test KEV vulnerability",
        "dateAdded": "2025-03-01",
        "dueDate": "2025-03-21",
        "knownRansomwareCampaignUse": "Unknown",
        "notes": "Apply vendor mitigation.",
        "cwes": ["CWE-79", "CWE-89"],
    }
