from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from sentineldrive_worker.connectors.config import (
    DEFAULT_NHTSA_MODEL_YEARS,
    DEFAULT_NHTSA_VEHICLES,
    DEFAULT_VENDOR_ENDPOINTS,
    load_source_configs,
)
from sentineldrive_worker.connectors.contracts import ConnectorContext, ConnectorError, SourceConfig, SourceType
from sentineldrive_worker.connectors.http import HttpResponse
from sentineldrive_worker.connectors.nhtsa_recalls import (
    NhtsaRecallsConnector,
    has_software_keyword,
    model_year_range,
    parse_recalls,
    parse_seen_campaigns,
    recall_payload,
)
from sentineldrive_worker.connectors.registry import ConnectorRegistry
from sentineldrive_worker.connectors.samples import register_builtin_connectors

NHTSA_URL = "https://api.nhtsa.gov/recalls/recallsByVehicle"


def source_config(**overrides) -> SourceConfig:
    values = {
        "name": "nhtsa-recalls",
        "source_type": SourceType.API,
        "enabled": True,
        "base_url": NHTSA_URL,
        "sync_interval_seconds": 3600,
        "timeout_seconds": 5.0,
        "rate_limit_per_minute": 20,
        "metadata": {
            "connector": "nhtsa-recalls",
            "vehicles": [{"make": "TESLA", "model": "Model 3"}],
            "model_years": 1,
        },
    }
    values.update(overrides)
    return SourceConfig(**values)


def recall_entry(campaign="22V063000", **overrides):
    values = {
        "NHTSACampaignNumber": campaign,
        "ReportReceivedDate": "2026-04-01",
        "Component": "SOFTWARE UPDATE",
        "Summary": "Software defect in telematics unit.",
        "Conequence": "Loss of connectivity.",
        "Remedy": "Over-the-air update.",
        "Manufacturer": "Example Motors, LLC",
        "Make": "TESLA",
        "Model": "Model 3",
        "ModelYear": "2026",
        "OverTheAirUpdate": True,
        "Type": "L",
    }
    values.update(overrides)
    return values


def recall_response(entries=None, count=None) -> HttpResponse:
    if entries is None:
        entries = [recall_entry()]
    payload = {"Count": count if count is not None else len(entries), "Results": entries}
    return HttpResponse(NHTSA_URL, 200, {"content-type": "application/json"}, json.dumps(payload).encode())


def make_connector(responses=None, **source_overrides):
    source = source_config(**source_overrides)
    connector = NhtsaRecallsConnector(
        source,
        http_client=FakeHttpClient(responses=responses),
        now_factory=lambda: datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    return connector, source


class FakeHttpClient:
    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self._by_query: dict[tuple, HttpResponse] = {}
        self.requests: list[dict[str, object]] = []

    def add(self, make: str, model: str, model_year: int, response: HttpResponse) -> None:
        self._by_query[(make, model, model_year)] = response

    def get(self, url, *, query=None, headers=None, timeout_seconds=20.0):
        q = dict(query or {}) if query is not None else {}
        self.requests.append(
            {"url": url, "query": q, "headers": dict(headers or {}), "timeout_seconds": timeout_seconds}
        )
        key = (q.get("make"), q.get("model"), q.get("modelYear"))
        if key in self._by_query:
            return self._by_query[key]
        if self._responses:
            return self._responses.pop(0)
        return HttpResponse(url, 200, {"content-type": "application/json"}, b'{"Count":0,"Results":[]}')


def test_builtin_registry_registers_nhtsa_recalls():
    registry = ConnectorRegistry()
    register_builtin_connectors(registry)
    assert "nhtsa-recalls" in registry.available()


def test_model_year_range_returns_most_recent_years():
    assert model_year_range(2026, 4) == [2023, 2024, 2025, 2026]
    assert model_year_range(2026, 1) == [2026]
    assert model_year_range(2026, 0) == []


def test_has_software_keyword_matches_case_insensitive():
    assert has_software_keyword("component", "SOFTWARE update") is True
    assert has_software_keyword("component", "over-the-air") is True
    assert has_software_keyword("component", "mechanical") is False


def test_nhtsa_happy_path_parses_campaign_as_external_id():
    connector, source = make_connector(responses=[recall_response(entries=[recall_entry()])])

    result = connector.collect(ConnectorContext(source=source))

    item = result.items[0]
    assert item.external_id == "22V063000"
    assert item.source_url == "https://www.nhtsa.gov/recalls?campaignNumber=22V063000"
    assert item.metadata["campaign_number"] == "22V063000"
    assert item.metadata["software_related"] is True
    assert item.raw_content["campaign_number"] == "22V063000"
    assert "vin" not in json.dumps(item.raw_content).lower()
    assert json.loads(result.next_cursor)["seen_campaigns"] == ["22V063000"]


def test_nhtsa_filters_mechanical_recalls_and_keeps_software_related():
    entries = [
        recall_entry("22V100000", OverTheAirUpdate=True, Component="ENGINE"),
        recall_entry("22V200000", OverTheAirUpdate=False, Component="SOFTWARE UPDATE", Summary="Older software bug"),
        recall_entry("22V300000", OverTheAirUpdate=False, Component="AIR BAGS", Summary="Mechanical airbag defect"),
    ]
    connector, source = make_connector(responses=[recall_response(entries=entries)])

    result = connector.collect(ConnectorContext(source=source))

    assert [item.external_id for item in result.items] == ["22V100000", "22V200000"]
    assert all(item.metadata["software_related"] for item in result.items)


def test_nhtsa_all_requests_fail_raises_connector_error():
    source = source_config()
    http = FakeHttpClient()
    http.add("TESLA", "Model 3", 2026, HttpResponse(NHTSA_URL, 403, {}, b"forbidden"))
    connector = NhtsaRecallsConnector(
        source,
        http_client=http,
        now_factory=lambda: datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ConnectorError, match="全部 NHTSA 召回请求失败"):
        connector.collect(ConnectorContext(source=source))


def test_nhtsa_vehicle_isolation_keeps_other_vehicle_results():
    source = source_config(
        metadata={
            "connector": "nhtsa-recalls",
            "vehicles": [{"make": "TESLA", "model": "Model 3"}, {"make": "RIVIAN", "model": "R1T"}],
            "model_years": 1,
        }
    )
    http = FakeHttpClient()
    http.add("TESLA", "Model 3", 2026, HttpResponse(NHTSA_URL, 503, {}, b"down"))
    http.add("RIVIAN", "R1T", 2026, recall_response(entries=[recall_entry("22V777000")]))
    connector = NhtsaRecallsConnector(
        source,
        http_client=http,
        now_factory=lambda: datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    result = connector.collect(ConnectorContext(source=source))

    assert [item.external_id for item in result.items] == ["22V777000"]
    assert len(result.metadata["vehicle_errors"]) == 1


def test_nhtsa_malformed_json_reaches_connector_error():
    source = source_config()
    http = FakeHttpClient()
    http.add("TESLA", "Model 3", 2026, HttpResponse(NHTSA_URL, 200, {"content-type": "application/json"}, b"{"))
    connector = NhtsaRecallsConnector(
        source,
        http_client=http,
        now_factory=lambda: datetime(2026, 5, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ConnectorError, match="全部 NHTSA 召回请求失败"):
        connector.collect(ConnectorContext(source=source))


def test_nhtsa_count_zero_returns_empty_not_error():
    connector, source = make_connector(responses=[recall_response(entries=[], count=0)])

    result = connector.collect(ConnectorContext(source=source))

    assert result.items == ()
    assert result.metadata["items_collected"] == 0


def test_nhtsa_cursor_skips_seen_campaigns_across_rounds():
    entries = [recall_entry("22V063000")]
    connector, source = make_connector(responses=[recall_response(entries=entries)])

    first = connector.collect(ConnectorContext(source=source))
    second_connector, _ = make_connector(responses=[recall_response(entries=entries)])
    second = second_connector.collect(ConnectorContext(source=source, cursor=first.next_cursor))

    assert [item.external_id for item in first.items] == ["22V063000"]
    assert second.items == ()
    assert json.loads(second.next_cursor)["seen_campaigns"] == ["22V063000"]


def test_parse_recalls_malformed_json_raises():
    with pytest.raises(ConnectorError, match="JSON 格式错误"):
        parse_recalls(HttpResponse(NHTSA_URL, 200, {}, b"{"))


def test_parse_seen_campaigns_handles_missing_and_invalid_cursor():
    assert parse_seen_campaigns(None) == set()
    assert parse_seen_campaigns("not-json") == set()
    assert parse_seen_campaigns(json.dumps({"seen_campaigns": ["22V1", "22V2"]})) == {"22V1", "22V2"}


def test_recall_payload_skips_missing_campaign_and_seen_campaign():
    source = source_config()
    assert recall_payload(source, {}, "TESLA", "Model 3", 2026, NHTSA_URL, set()) is None
    entry = recall_entry()
    assert recall_payload(source, entry, "TESLA", "Model 3", 2026, NHTSA_URL, {"22V063000"}) is None


def test_default_vendor_endpoints_include_new_vendors_and_parse():
    vendors = [entry["vendor"] for entry in DEFAULT_VENDOR_ENDPOINTS]
    assert {"Vector Informatik", "Wind River", "Geely GSRC", "Xiaomi SRC"}.issubset(set(vendors))
    assert all(isinstance(entry, dict) and entry.get("url") for entry in DEFAULT_VENDOR_ENDPOINTS)
    json.dumps(DEFAULT_VENDOR_ENDPOINTS)


def test_config_loads_nhtsa_source_and_expanded_vendor_endpoints():
    configs = load_source_configs({"SOURCE_ENABLED_NHTSA_RECALLS": "true", "SOURCE_ENABLED_VENDOR_ADVISORIES": "true"})

    nhtsa = next(cfg for cfg in configs if cfg.name == "nhtsa-recalls")
    assert nhtsa.enabled is True
    assert nhtsa.base_url == NHTSA_URL
    assert nhtsa.metadata["vehicles"] == DEFAULT_NHTSA_VEHICLES
    assert nhtsa.metadata["model_years"] == DEFAULT_NHTSA_MODEL_YEARS
    assert len(DEFAULT_NHTSA_VEHICLES) == 9

    vendor = next(cfg for cfg in configs if cfg.name == "vendor-advisories")
    vendors = {entry["vendor"] for entry in vendor.metadata["endpoints"]}
    assert {"Vector Informatik", "Wind River", "Geely GSRC", "Xiaomi SRC"}.issubset(vendors)


def test_config_disables_nhtsa_source_by_default():
    configs = load_source_configs({})
    nhtsa = next(cfg for cfg in configs if cfg.name == "nhtsa-recalls")
    assert nhtsa.enabled is False