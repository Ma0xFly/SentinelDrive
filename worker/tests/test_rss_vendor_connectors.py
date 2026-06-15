from __future__ import annotations

import json

import pytest

from sentineldrive_worker.connectors.config import SourceConfigRow, load_source_configs
from sentineldrive_worker.connectors.contracts import ConnectorContext, ConnectorError, SourceConfig, SourceType
from sentineldrive_worker.connectors.http import HttpResponse
from sentineldrive_worker.connectors.registry import ConnectorRegistry
from sentineldrive_worker.connectors.rss_vendor import RssConnector, VendorAdvisoryConnector, sanitized_error
from sentineldrive_worker.connectors.samples import register_builtin_connectors


def source_config(name: str, **overrides) -> SourceConfig:
    values = {
        "name": name,
        "source_type": SourceType.RSS,
        "enabled": True,
        "base_url": f"https://example.test/{name}",
        "sync_interval_seconds": 3600,
        "timeout_seconds": 5.0,
        "rate_limit_per_minute": 20,
        "metadata": {"connector": name},
    }
    values.update(overrides)
    return SourceConfig(**values)


def test_builtin_registry_registers_rss_and_vendor_connectors():
    registry = ConnectorRegistry()

    register_builtin_connectors(registry)

    assert "rss" in registry.available()
    assert "vendor-advisories" in registry.available()


def test_rss_feed_entries_come_from_configuration_without_core_changes():
    configs = load_source_configs(
        env={
            "SOURCE_RSS_FEEDS": json.dumps(
                [{"name": "Example Feed", "url": "https://example.test/feed.xml", "source": "example"}]
            )
        }
    )

    rss = next(config for config in configs if config.name == "rss")
    assert rss.metadata["feeds"] == [{"name": "Example Feed", "url": "https://example.test/feed.xml", "source": "example"}]


def test_invalid_rss_feed_configuration_fails_clearly():
    with pytest.raises(ValueError, match="JSON list of objects"):
        load_source_configs(env={"SOURCE_RSS_FEEDS": json.dumps(["https://example.test/feed.xml"])})


def test_database_backed_config_preserves_safe_feed_metadata():
    configs = load_source_configs(
        env={},
        db_sources=[
            SourceConfigRow(
                name="rss-db",
                source_type="rss",
                config={
                    "connector": "rss",
                    "feeds": [{"name": "DB Feed", "url": "https://example.test/db.xml"}],
                    "credentials": {"token": "secret"},
                    "headers": {"Authorization": "secret"},
                },
            )
        ],
    )

    rss = next(config for config in configs if config.name == "rss-db")
    assert rss.metadata["feeds"] == [{"name": "DB Feed", "url": "https://example.test/db.xml"}]
    assert "credentials" not in rss.metadata
    assert "headers" not in rss.metadata


def test_rss_2_feed_maps_items_to_raw_payloads():
    source = source_config(
        "rss",
        metadata={"connector": "rss", "feeds": [{"name": "Security Feed", "url": "https://example.test/rss.xml"}]},
    )
    connector = RssConnector(source, http_client=FakeHttpClient([rss_response(RSS_XML)]))

    result = connector.collect(ConnectorContext(source=source))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.source_url == "https://example.test/advisory-1"
    assert item.external_id == "advisory-1"
    assert item.title == "Vehicle advisory"
    assert item.summary == "Firmware update available."
    assert item.metadata["feed_name"] == "Security Feed"
    assert json.loads(result.next_cursor)["latest_seen"] is not None


def test_atom_feed_maps_entries_to_raw_payloads():
    source = source_config(
        "rss",
        metadata={"connector": "rss", "feeds": [{"name": "Atom Feed", "url": "https://example.test/atom.xml"}]},
    )
    connector = RssConnector(source, http_client=FakeHttpClient([rss_response(ATOM_XML)]))

    result = connector.collect(ConnectorContext(source=source))

    assert result.items[0].source_url == "https://example.test/atom-advisory"
    assert result.items[0].external_id == "urn:advisory:1"
    assert result.items[0].summary == "Atom advisory summary"


def test_namespaced_rss_feed_maps_items_to_raw_payloads():
    source = source_config(
        "rss",
        metadata={"connector": "rss", "feeds": [{"name": "Namespaced RSS", "url": "https://example.test/rss.xml"}]},
    )
    connector = RssConnector(source, http_client=FakeHttpClient([rss_response(NAMESPACED_RSS_XML)]))

    result = connector.collect(ConnectorContext(source=source))

    assert result.items[0].source_url == "https://example.test/namespaced-advisory"
    assert result.items[0].external_id == "namespaced-advisory"


def test_rss_duplicate_guid_or_url_is_idempotent():
    source = source_config(
        "rss",
        metadata={"connector": "rss", "feeds": [{"name": "Security Feed", "url": "https://example.test/rss.xml"}]},
    )
    first = RssConnector(source, http_client=FakeHttpClient([rss_response(RSS_XML)])).collect(ConnectorContext(source=source))
    second = RssConnector(source, http_client=FakeHttpClient([rss_response(RSS_XML)])).collect(ConnectorContext(source=source))

    assert first.items[0].raw_hash == second.items[0].raw_hash
    assert first.items[0].content_hash == second.items[0].content_hash


def test_malformed_rss_feed_fails_clearly():
    source = source_config(
        "rss",
        metadata={"connector": "rss", "feeds": [{"name": "Broken Feed", "url": "https://example.test/broken.xml"}]},
    )

    with pytest.raises(ConnectorError, match="all RSS feeds failed"):
        RssConnector(source, http_client=FakeHttpClient([rss_response("<rss>")])).collect(ConnectorContext(source=source))


def test_endpoint_error_metadata_redacts_token_like_values():
    error = sanitized_error(ConnectorError("HTTP request failed for https://example.test/feed.xml?token=super-secret"))

    assert "super-secret" not in error
    assert "[redacted]" in error


def test_vendor_endpoint_metadata_and_advisory_links_are_metadata_only():
    source = source_config(
        "vendor-advisories",
        source_type=SourceType.VENDOR,
        metadata={"connector": "vendor-advisories", "endpoints": [{"vendor": "Bosch", "url": "https://psirt.bosch.com/security-advisories/"}]},
    )
    connector = VendorAdvisoryConnector(source, http_client=FakeHttpClient([vendor_response(VENDOR_HTML)]))

    result = connector.collect(ConnectorContext(source=source))

    endpoint_item = result.items[0]
    link_items = result.items[1:]
    assert endpoint_item.raw_content is None
    assert endpoint_item.retained_payload_mode == "metadata_only"
    assert endpoint_item.metadata["title"] == "Bosch PSIRT"
    assert endpoint_item.metadata["canonical_url"] == "https://psirt.bosch.com/security-advisories/"
    assert {item.source_url for item in link_items} == {
        "https://psirt.bosch.com/security-advisories/bosch-2026-001",
        "https://psirt.bosch.com/security-advisories/bosch-2026-002.pdf",
    }
    assert all(item.raw_content is None for item in link_items)
    assert next(item for item in link_items if item.source_url.endswith(".pdf")).metadata["is_pdf"] is True


def test_vendor_endpoint_isolation_keeps_successful_endpoints():
    source = source_config(
        "vendor-advisories",
        source_type=SourceType.VENDOR,
        metadata={
            "connector": "vendor-advisories",
            "endpoints": [
                {"vendor": "Broken", "url": "https://example.test/down"},
                {"vendor": "NIO", "url": "https://niosrc.bugbank.cn/"},
            ],
        },
    )
    connector = VendorAdvisoryConnector(
        source,
        http_client=FakeHttpClient(
            [
                HttpResponse("https://example.test/down", 503, {}, b"down"),
                vendor_response(VENDOR_HTML, url="https://niosrc.bugbank.cn/"),
            ]
        ),
    )

    result = connector.collect(ConnectorContext(source=source))

    assert len(result.items) >= 1
    assert result.metadata["endpoint_errors"][0]["url"] == "https://example.test/down"


def test_vendor_all_endpoints_failed_raises_sanitized_error():
    source = source_config(
        "vendor-advisories",
        source_type=SourceType.VENDOR,
        metadata={"connector": "vendor-advisories", "endpoints": [{"vendor": "Broken", "url": "https://example.test/down"}]},
    )

    with pytest.raises(ConnectorError, match="all vendor advisory endpoints failed"):
        VendorAdvisoryConnector(source, http_client=FakeHttpClient([HttpResponse("https://example.test/down", 500, {}, b"")])).collect(
            ConnectorContext(source=source)
        )


def test_default_vendor_endpoint_seeds_include_required_vendors():
    vendor_config = next(config for config in load_source_configs(env={}) if config.name == "vendor-advisories")
    vendors = {endpoint["vendor"] for endpoint in vendor_config.metadata["endpoints"]}

    assert {"BYD", "NIO", "Li Auto", "Qualcomm", "Bosch"}.issubset(vendors)
    byd = next(endpoint for endpoint in vendor_config.metadata["endpoints"] if endpoint["vendor"] == "BYD")
    assert byd["verification_status"] == "needs_manual_review"


class FakeHttpClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.requests = []

    def get(self, url, *, query=None, headers=None, timeout_seconds=20.0):
        self.requests.append({"url": url, "query": query, "headers": headers, "timeout_seconds": timeout_seconds})
        return self._responses.pop(0)


def rss_response(text, url="https://example.test/rss.xml", status=200):
    return HttpResponse(url, status, {"content-type": "application/xml"}, text.encode())


def vendor_response(text, url="https://psirt.bosch.com/security-advisories/", status=200):
    return HttpResponse(url, status, {"content-type": "text/html"}, text.encode())


RSS_XML = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Security Feed</title>
    <item>
      <title>Vehicle advisory</title>
      <link>https://example.test/advisory-1</link>
      <guid>advisory-1</guid>
      <description>Firmware update available.</description>
      <pubDate>Tue, 19 May 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


ATOM_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom advisory</title>
    <id>urn:advisory:1</id>
    <link rel="alternate" href="https://example.test/atom-advisory" />
    <summary>Atom advisory summary</summary>
    <updated>2026-05-19T11:00:00Z</updated>
  </entry>
</feed>
"""


NAMESPACED_RSS_XML = """<?xml version="1.0"?>
<rss version="2.0" xmlns:sd="https://example.test/ns">
  <sd:channel>
    <sd:item>
      <sd:title>Namespaced advisory</sd:title>
      <sd:link>https://example.test/namespaced-advisory</sd:link>
      <sd:guid>namespaced-advisory</sd:guid>
      <sd:description>Namespaced feed item.</sd:description>
      <sd:pubDate>Tue, 19 May 2026 10:00:00 GMT</sd:pubDate>
    </sd:item>
  </sd:channel>
</rss>
"""


VENDOR_HTML = """
<html>
  <head>
    <title>Bosch PSIRT</title>
    <meta name="description" content="Security advisories for Bosch products">
    <link rel="canonical" href="https://psirt.bosch.com/security-advisories/">
  </head>
  <body>
    <h1>Security Advisories</h1>
    <a href="/security-advisories/bosch-2026-001">Bosch security advisory 2026-001</a>
    <a href="/security-advisories/bosch-2026-002.pdf">PDF advisory</a>
    <a href="/about">About</a>
  </body>
</html>
"""
