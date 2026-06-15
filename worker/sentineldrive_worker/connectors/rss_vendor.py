from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from sentineldrive_worker.connectors.contracts import (
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    ProcessingStatus,
    RawIntelligencePayload,
    SourceConfig,
    SourceType,
    stable_hash,
)
from sentineldrive_worker.connectors.dates import parse_datetime
from sentineldrive_worker.connectors.http import HttpClient, HttpResponse


@dataclass
class RssConnector:
    source: SourceConfig
    http_client: HttpClient | None = None

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        feeds = list(self.source.metadata.get("feeds") or [])
        if not feeds and self.source.base_url:
            feeds = [{"name": self.source.name, "url": self.source.base_url}]
        if not feeds:
            return ConnectorResult(items=tuple(), next_cursor=context.cursor, metadata={"connector": "rss", "feeds_seen": 0})

        http = self.http_client or HttpClient()
        items: list[RawIntelligencePayload] = []
        feed_errors: list[dict[str, str]] = []
        latest_seen = parse_datetime_from_cursor(context.cursor)

        for feed in feeds:
            if not isinstance(feed, Mapping):
                feed_errors.append({"url": "", "error": "RSS feed entry must be an object"})
                continue
            feed_url = str(feed.get("url") or "").strip()
            if not feed_url:
                continue
            try:
                response = http.get(feed_url, headers={"User-Agent": "SentinelDrive/0.1"}, timeout_seconds=self.source.timeout_seconds)
                require_success(response, f"RSS feed {feed_url}")
                parsed_items = parse_feed(response.text)
                for parsed in parsed_items:
                    payload = rss_payload(self.source, feed, parsed, response.url)
                    items.append(payload)
                    item_time = payload.first_seen_at or payload.fetched_at
                    if latest_seen is None or item_time > latest_seen:
                        latest_seen = item_time
            except Exception as exc:
                feed_errors.append({"url": feed_url, "error": sanitized_error(exc)})

        if not items and feed_errors:
            raise ConnectorError(f"all RSS feeds failed: {feed_errors[0]['error']}")

        cursor = json.dumps({"latest_seen": latest_seen.isoformat() if latest_seen else None}, sort_keys=True)
        return ConnectorResult(
            items=tuple(items),
            next_cursor=cursor,
            metadata={
                "connector": "rss",
                "feeds_seen": len(feeds),
                "items_collected": len(items),
                "feed_errors": feed_errors,
            },
        )


@dataclass
class VendorAdvisoryConnector:
    source: SourceConfig
    http_client: HttpClient | None = None

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        endpoints = list(self.source.metadata.get("endpoints") or [])
        if not endpoints and self.source.base_url:
            endpoints = [{"vendor": self.source.name, "url": self.source.base_url}]
        if not endpoints:
            return ConnectorResult(items=tuple(), next_cursor=context.cursor, metadata={"connector": "vendor-advisories", "endpoints_seen": 0})

        http = self.http_client or HttpClient()
        items: list[RawIntelligencePayload] = []
        endpoint_errors: list[dict[str, str]] = []
        latest_hashes: list[str] = []

        for endpoint in endpoints:
            if not isinstance(endpoint, Mapping):
                endpoint_errors.append({"url": "", "error": "vendor endpoint entry must be an object"})
                continue
            endpoint_url = str(endpoint.get("url") or "").strip()
            if not endpoint_url:
                continue
            try:
                response = http.get(endpoint_url, headers={"User-Agent": "SentinelDrive/0.1"}, timeout_seconds=self.source.timeout_seconds)
                require_success(response, f"vendor endpoint {endpoint_url}")
                payload = vendor_payload(self.source, endpoint, response)
                items.append(payload)
                latest_hashes.append(payload.content_hash or payload.raw_hash)
                for link in advisory_links(endpoint, response):
                    items.append(link_payload(self.source, endpoint, response, link))
            except Exception as exc:
                endpoint_errors.append({"url": endpoint_url, "error": sanitized_error(exc)})

        if not items and endpoint_errors:
            raise ConnectorError(f"all vendor advisory endpoints failed: {endpoint_errors[0]['error']}")

        cursor = json.dumps({"content_hashes": sorted(latest_hashes)}, sort_keys=True)
        return ConnectorResult(
            items=tuple(items),
            next_cursor=cursor,
            metadata={
                "connector": "vendor-advisories",
                "endpoints_seen": len(endpoints),
                "items_collected": len(items),
                "endpoint_errors": endpoint_errors,
            },
        )


def parse_feed(text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ConnectorError("RSS/Atom feed is malformed XML") from exc

    tag = strip_namespace(root.tag).lower()
    if tag == "rss":
        channel = find_child(root, "channel")
        if channel is None:
            raise ConnectorError("RSS feed missing channel")
        return [parse_rss_item(item) for item in find_children(channel, "item")]
    if tag == "feed":
        return [parse_atom_entry(entry) for entry in root.findall("{*}entry")]
    raise ConnectorError("unsupported feed format")


def parse_rss_item(item: ET.Element) -> dict[str, Any]:
    return {
        "title": child_text(item, "title"),
        "link": child_text(item, "link"),
        "guid": child_text(item, "guid"),
        "summary": child_text(item, "description"),
        "published": child_text(item, "pubDate"),
        "updated": child_text(item, "updated"),
    }


def parse_atom_entry(entry: ET.Element) -> dict[str, Any]:
    link = None
    for link_node in entry.findall("{*}link"):
        href = link_node.attrib.get("href")
        if href and (link_node.attrib.get("rel") in (None, "alternate")):
            link = href
            break
    return {
        "title": child_text(entry, "title"),
        "link": link,
        "guid": child_text(entry, "id"),
        "summary": child_text(entry, "summary") or child_text(entry, "content"),
        "published": child_text(entry, "published"),
        "updated": child_text(entry, "updated"),
    }


def rss_payload(source: SourceConfig, feed: Mapping[str, Any], item: Mapping[str, Any], response_url: str) -> RawIntelligencePayload:
    url = str(item.get("link") or item.get("guid") or response_url)
    external_id = str(item.get("guid") or url)
    summary = clean_text(str(item.get("summary") or ""))
    published = parse_datetime(item.get("published")) or parse_datetime(item.get("updated"))
    metadata = {
        "feed_name": feed.get("name"),
        "feed_url": feed.get("url"),
        "published": item.get("published"),
        "updated": item.get("updated"),
        "response_url": response_url,
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=url,
        external_id=external_id,
        title=clean_text(str(item.get("title") or url)),
        summary=summary or None,
        snippet=(summary or "")[:500] or None,
        raw_content=dict(item),
        first_seen_at=published,
        metadata=metadata,
    )


def vendor_payload(source: SourceConfig, endpoint: Mapping[str, Any], response: HttpResponse) -> RawIntelligencePayload:
    metadata = extract_html_metadata(response.text, response.url)
    content_type = response.headers.get("content-type") or response.headers.get("Content-Type")
    snippet = metadata.get("description") or metadata.get("heading") or metadata.get("title")
    endpoint_metadata = {
        "vendor": endpoint.get("vendor"),
        "endpoint_url": endpoint.get("url"),
        "verification_status": endpoint.get("verification_status"),
        "endpoint_type": endpoint.get("endpoint_type"),
        "final_url": response.url,
        "http_status": response.status_code,
        "content_type": content_type,
        "title": metadata.get("title"),
        "description": metadata.get("description"),
        "heading": metadata.get("heading"),
        "canonical_url": metadata.get("canonical_url"),
        "content_hash": metadata.get("content_hash"),
        "discovered_links": metadata.get("links", [])[:20],
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=metadata.get("canonical_url") or response.url,
        external_id=stable_hash({"url": response.url, "content_hash": metadata.get("content_hash")}),
        title=metadata.get("title") or f"{endpoint.get('vendor', 'Vendor')} advisory endpoint",
        summary=snippet,
        snippet=snippet[:500] if snippet else None,
        raw_content=None,
        metadata=endpoint_metadata,
        retained_payload_mode="metadata_only",
    )


def advisory_links(endpoint: Mapping[str, Any], response: HttpResponse) -> list[dict[str, str]]:
    metadata = extract_html_metadata(response.text, response.url)
    links = []
    for link in metadata.get("links", []):
        href = link["url"]
        text = link.get("text") or href
        if looks_like_advisory_link(href, text):
            links.append({"url": href, "text": text})
    return links[:20]


def link_payload(source: SourceConfig, endpoint: Mapping[str, Any], response: HttpResponse, link: Mapping[str, str]) -> RawIntelligencePayload:
    is_pdf = link["url"].lower().split("?", 1)[0].endswith(".pdf")
    metadata = {
        "vendor": endpoint.get("vendor"),
        "endpoint_url": endpoint.get("url"),
        "verification_status": endpoint.get("verification_status"),
        "parent_url": response.url,
        "link_text": link.get("text"),
        "is_pdf": is_pdf,
    }
    return RawIntelligencePayload.from_source(
        source,
        source_url=link["url"],
        external_id=stable_hash({"vendor": endpoint.get("vendor"), "url": link["url"]}),
        title=clean_text(link.get("text") or link["url"]),
        summary=None,
        snippet=None,
        raw_content=None,
        metadata=metadata,
        retained_payload_mode="metadata_only",
    )


def extract_html_metadata(text: str, base_url: str) -> dict[str, Any]:
    title = first_match(text, r"<title[^>]*>(.*?)</title>")
    description = first_match(text, r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']')
    if not description:
        description = first_match(text, r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']')
    heading = first_match(text, r"<h1[^>]*>(.*?)</h1>")
    canonical = first_match(text, r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']')
    links = []
    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, flags=re.IGNORECASE | re.DOTALL):
        href = urljoin(base_url, html.unescape(match.group(1)))
        label = clean_text(match.group(2))
        links.append({"url": href, "text": label})
    return {
        "title": clean_text(title) if title else None,
        "description": clean_text(description) if description else None,
        "heading": clean_text(heading) if heading else None,
        "canonical_url": urljoin(base_url, html.unescape(canonical)) if canonical else None,
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "links": links,
    }


def looks_like_advisory_link(url: str, text: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    label = text.lower()
    if path.endswith(".pdf") and any(term in label for term in ("advisory", "security", "bulletin", "vulnerability", "cve-", "psirt")):
        return True
    haystack = f"{path} {parsed.query.lower()} {label}"
    return any(term in haystack for term in ("advisory", "advisories", "security", "bulletin", "vulnerability", "cve-"))


def require_success(response: HttpResponse, source_label: str) -> None:
    if response.status_code < 200 or response.status_code >= 300:
        raise ConnectorError(f"{source_label} returned HTTP {response.status_code}")


def child_text(parent: ET.Element, child_name: str) -> str | None:
    node = find_child(parent, child_name)
    if node is None or node.text is None:
        return None
    return clean_text(node.text)


def find_child(parent: ET.Element, child_name: str) -> ET.Element | None:
    node = parent.find(child_name)
    if node is not None:
        return node
    return parent.find(f"{{*}}{child_name}")


def find_children(parent: ET.Element, child_name: str) -> list[ET.Element]:
    children = list(parent.findall(child_name))
    if children:
        return children
    return list(parent.findall(f"{{*}}{child_name}"))


def first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return match.group(1)


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_datetime_from_cursor(cursor: str | None) -> datetime | None:
    if not cursor:
        return None
    try:
        parsed = json.loads(cursor)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parse_datetime(parsed.get("latest_seen"))


def sanitized_error(error: BaseException) -> str:
    text = str(error) or error.__class__.__name__
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*[^&\s]+",
        "[redacted]=[redacted]",
        text,
    )
    text = re.sub(r"(?i)api[_-]?key|authorization|password|secret|token", "[redacted]", text)
    return text[:300]
