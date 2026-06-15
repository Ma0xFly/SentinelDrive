from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from sentineldrive_worker.normalization.dedup import (
    canonical_url,
    dedup_key,
    find_cve,
    normalize_cve,
    normalize_cwe,
    normalize_text,
    stable_hash,
    text_hash,
)
from sentineldrive_worker.normalization.hints import infer_attack_surface, infer_vehicle_component
from sentineldrive_worker.normalization.models import NormalizationError, NormalizedRecord, SourceAttribution
from sentineldrive_worker.normalization.registry import NormalizerRegistry, registry


@dataclass
class BaseNormalizer:
    def normalize(self, raw_record: Mapping[str, Any]) -> NormalizedRecord:
        raise NotImplementedError

    def base_record(
        self,
        raw: Mapping[str, Any],
        *,
        title: str,
        summary: str | None,
        intelligence_type: str,
        cve_id: str | None = None,
        cwe_id: str | None = None,
        cvss_score: float | None = None,
        cvss_vector: str | None = None,
        severity: str = "unknown",
        affected_vendor: str | None = None,
        affected_product: str | None = None,
        affected_version: str | None = None,
        vehicle_component: str | None = None,
        attack_surface: str | None = None,
        exploit_status: str = "unknown",
        confidence: str = "medium",
        tags: list[str] | None = None,
        status: str = "active",
        metadata: dict[str, Any] | None = None,
    ) -> NormalizedRecord:
        normalized_title = clean_title(title, raw)
        normalized_summary = clean_optional(summary or raw.get("summary") or raw.get("snippet"))
        source_url = canonical_url(raw.get("source_url")) or str(raw.get("source_url") or "")
        source_name = str(raw.get("source_name") or "unknown")
        first_seen = require_datetime(raw.get("first_seen_at") or raw.get("fetched_at"), "first_seen_at")
        last_seen = require_datetime(raw.get("fetched_at") or first_seen, "fetched_at")
        normalized_hash = text_hash(" ".join(filter(None, [normalized_title, normalized_summary, cve_id, cwe_id])))
        key = dedup_key(
            cve_id=cve_id,
            source_url=source_url,
            title=normalized_title,
            source_name=source_name,
            content_hash=clean_optional(raw.get("content_hash")),
            normalized_text_hash=normalized_hash,
        )
        source_tags = sorted({tag for tag in (tags or []) if tag})
        metadata_payload = {
            "normalizer": self.__class__.__name__,
            "raw_source_type": raw.get("source_type"),
            **dict(metadata or {}),
        }
        external_ids = source_external_ids(raw, cve_id=cve_id, cwe_id=cwe_id)
        return NormalizedRecord(
            raw_intelligence_id=raw.get("id"),
            title=normalized_title,
            summary=normalized_summary,
            intelligence_type=intelligence_type,
            source_names=[source_name],
            source_urls=[source_url],
            canonical_source_url=source_url,
            external_ids=external_ids,
            cve_id=cve_id,
            cwe_id=cwe_id,
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            severity=severity,
            affected_vendor=affected_vendor,
            affected_product=affected_product,
            affected_version=affected_version,
            vehicle_component=vehicle_component,
            attack_surface=attack_surface,
            exploit_status=exploit_status,
            confidence=confidence,
            tags=source_tags,
            first_seen_at=first_seen,
            last_seen_at=last_seen,
            dedup_key=key,
            normalized_text_hash=normalized_hash,
            status=status,
            metadata=metadata_payload,
            attribution=SourceAttribution(
                source_id=raw.get("source_id"),
                raw_intelligence_id=raw.get("id"),
                source_name=source_name,
                source_url=source_url,
                external_id=clean_optional(raw.get("external_id")),
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            ),
        )


class NvdNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        metadata = dict(raw.get("metadata") or {})
        raw_content = raw.get("raw_content") if isinstance(raw.get("raw_content"), dict) else {}
        cve = raw_content.get("cve") if isinstance(raw_content.get("cve"), dict) else {}
        cve_id = find_cve(raw.get("external_id"), cve.get("id"), raw.get("title"), raw.get("summary"))
        if not cve_id:
            raise NormalizationError("NVD raw record missing CVE ID")
        cvss = metadata.get("cvss") if isinstance(metadata.get("cvss"), dict) else {}
        cwes = metadata.get("cwe")
        references = cve.get("references", {}).get("referenceData", []) if isinstance(cve.get("references"), dict) else []
        return self.base_record(
            raw,
            title=clean_title(raw.get("title") or cve_id, raw),
            summary=clean_optional(raw.get("summary")),
            intelligence_type="vulnerability",
            cve_id=cve_id,
            cwe_id=normalize_cwe(cwes),
            cvss_score=float_or_none(cvss.get("base_score")),
            cvss_vector=clean_optional(cvss.get("vector_string")),
            severity=severity_value(cvss.get("base_severity")),
            affected_vendor=first_cpe_part(cve, "vendor"),
            affected_product=first_cpe_part(cve, "product"),
            affected_version=first_cpe_part(cve, "version"),
            vehicle_component=infer_vehicle_component(raw.get("title"), raw.get("summary"), references),
            attack_surface=infer_attack_surface(raw.get("title"), raw.get("summary"), references),
            exploit_status=exploit_status_from_text(metadata.get("vuln_status"), references),
            confidence="high",
            tags=compact_tags(["nvd", "cve", cve_id, normalize_cwe(cwes), metadata.get("vuln_status")]),
            metadata={
                "published": metadata.get("published"),
                "last_modified": metadata.get("last_modified"),
                "vuln_status": metadata.get("vuln_status"),
                "reference_count": metadata.get("reference_count"),
            },
        )


class CisaKevNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        metadata = dict(raw.get("metadata") or {})
        cve_id = find_cve(raw.get("external_id"), raw.get("title"), raw.get("summary"))
        if not cve_id:
            raise NormalizationError("CISA KEV raw record missing CVE ID")
        cwe_id = normalize_cwe(metadata.get("cwes"))
        ransomware = clean_optional(metadata.get("known_ransomware_campaign_use"))
        return self.base_record(
            raw,
            title=clean_title(raw.get("title") or cve_id, raw),
            summary=clean_optional(raw.get("summary")),
            intelligence_type="vulnerability",
            cve_id=cve_id,
            cwe_id=cwe_id,
            affected_vendor=clean_optional(metadata.get("vendor_project")),
            affected_product=clean_optional(metadata.get("product")),
            vehicle_component=infer_vehicle_component(raw.get("title"), raw.get("summary"), metadata),
            attack_surface=infer_attack_surface(raw.get("title"), raw.get("summary"), metadata),
            exploit_status="exploited",
            confidence="high",
            tags=compact_tags(["cisa-kev", "kev", "known_exploited", "cve", cve_id, cwe_id, ransomware_tag(ransomware)]),
            metadata={
                "date_added": metadata.get("date_added"),
                "due_date": metadata.get("due_date"),
                "known_ransomware_campaign_use": ransomware,
                "notes": metadata.get("notes"),
                "vulnerability_name": metadata.get("vulnerability_name"),
            },
        )


class RssNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        metadata = dict(raw.get("metadata") or {})
        text = " ".join(str(raw.get(key) or "") for key in ("title", "summary", "snippet", "source_url", "external_id"))
        cve_id = find_cve(text)
        intelligence_type = "vulnerability" if cve_id else "advisory"
        return self.base_record(
            raw,
            title=clean_title(raw.get("title"), raw),
            summary=clean_optional(raw.get("summary") or raw.get("snippet")),
            intelligence_type=intelligence_type,
            cve_id=cve_id,
            cwe_id=normalize_cwe(text),
            vehicle_component=infer_vehicle_component(text),
            attack_surface=infer_attack_surface(text),
            exploit_status=exploit_status_from_text(text),
            confidence="medium",
            tags=compact_tags(["rss", "feed", metadata.get("feed_name"), cve_id]),
            metadata={
                "feed_name": metadata.get("feed_name"),
                "feed_url": metadata.get("feed_url"),
                "published": metadata.get("published"),
                "updated": metadata.get("updated"),
            },
        )


class VendorAdvisoryNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        metadata = dict(raw.get("metadata") or {})
        text = " ".join(str(value or "") for value in (raw.get("title"), raw.get("summary"), raw.get("snippet"), raw.get("source_url"), metadata))
        cve_id = find_cve(text)
        return self.base_record(
            raw,
            title=clean_title(raw.get("title"), raw),
            summary=clean_optional(raw.get("summary") or raw.get("snippet")),
            intelligence_type="vulnerability" if cve_id else "advisory",
            cve_id=cve_id,
            cwe_id=normalize_cwe(text),
            affected_vendor=clean_optional(metadata.get("vendor")),
            vehicle_component=infer_vehicle_component(text),
            attack_surface=infer_attack_surface(text),
            exploit_status=exploit_status_from_text(text),
            confidence="medium",
            tags=compact_tags(["vendor_advisory", metadata.get("vendor"), metadata.get("verification_status"), "pdf" if metadata.get("is_pdf") else None, cve_id]),
            metadata={
                "vendor": metadata.get("vendor"),
                "endpoint_url": metadata.get("endpoint_url"),
                "verification_status": metadata.get("verification_status"),
                "content_type": metadata.get("content_type"),
                "is_pdf": metadata.get("is_pdf"),
            },
        )


class ManualNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        metadata = dict(raw.get("metadata") or {})
        if metadata.get("entry_origin") == "manual" and raw.get("processing_status") == "normalized":
            raise NormalizationError("manual raw record is already normalized by backend manual-entry API")
        raw_content = raw.get("raw_content") if isinstance(raw.get("raw_content"), dict) else {}
        category = clean_optional(metadata.get("manual_entry_category") or raw_content.get("category")) or "advisory"
        intelligence_type = category_to_intelligence_type(category)
        cve_id = normalize_cve(raw.get("external_id") or raw.get("title") or raw_content.get("cve_id"))
        status = "under_review" if category == "research_lead" else "active"
        source_name = str(raw.get("source_name") or "Manual Entry")
        source_url = str(raw.get("source_url") or "manual://entry")
        record = self.base_record(
            raw,
            title=clean_title(raw.get("title") or raw_content.get("title"), raw),
            summary=clean_optional(raw.get("summary") or raw_content.get("summary")),
            intelligence_type=intelligence_type,
            cve_id=cve_id,
            cwe_id=normalize_cwe(raw_content.get("cwe_id")),
            severity=severity_value(raw_content.get("severity")),
            affected_vendor=clean_optional(raw_content.get("affected_vendor")),
            affected_product=clean_optional(raw_content.get("affected_product")),
            affected_version=clean_optional(raw_content.get("affected_version")),
            vehicle_component=clean_optional(raw_content.get("vehicle_component")),
            attack_surface=clean_optional(raw_content.get("attack_surface")),
            exploit_status=clean_optional(raw_content.get("exploit_status")) or "unknown",
            confidence=clean_optional(raw_content.get("confidence")) or "medium",
            tags=compact_tags(["manual", category, "research_lead" if category == "research_lead" else None, *(raw_content.get("tags") or [])]),
            status=status,
            metadata={"entry_origin": "manual", "manual_entry_category": category},
        )
        record.dedup_key = manual_dedup_key(category, cve_id, record.title, source_name, source_url)
        return record


class FallbackNormalizer(BaseNormalizer):
    def normalize(self, raw: Mapping[str, Any]) -> NormalizedRecord:
        text = " ".join(str(raw.get(key) or "") for key in ("title", "summary", "snippet", "source_url", "external_id"))
        cve_id = find_cve(text)
        return self.base_record(
            raw,
            title=clean_title(raw.get("title"), raw),
            summary=clean_optional(raw.get("summary") or raw.get("snippet")),
            intelligence_type="vulnerability" if cve_id else "advisory",
            cve_id=cve_id,
            cwe_id=normalize_cwe(text),
            vehicle_component=infer_vehicle_component(text),
            attack_surface=infer_attack_surface(text),
            tags=compact_tags(["raw_fallback", cve_id]),
            metadata={"fallback_reason": "source-specific normalizer unavailable"},
        )


def register_builtin_normalizers(target_registry: NormalizerRegistry = registry) -> NormalizerRegistry:
    target_registry.register_source_name("nvd", NvdNormalizer)
    target_registry.register_source_name("cisa-kev", CisaKevNormalizer)
    target_registry.register_source_name("rss", RssNormalizer)
    target_registry.register_source_name("vendor-advisories", VendorAdvisoryNormalizer)
    target_registry.register_source_type("manual", ManualNormalizer)
    target_registry.register_source_type("rss", RssNormalizer)
    target_registry.register_source_type("vendor", VendorAdvisoryNormalizer)
    target_registry.register_source_type("api", FallbackNormalizer)
    target_registry.register_source_type("html", VendorAdvisoryNormalizer)
    target_registry.register_source_type("pdf", VendorAdvisoryNormalizer)
    return target_registry


def source_external_ids(raw: Mapping[str, Any], *, cve_id: str | None, cwe_id: str | None) -> dict[str, Any]:
    source_name = str(raw.get("source_name") or "unknown")
    external_ids: dict[str, Any] = {}
    if raw.get("external_id"):
        external_ids[source_name] = raw.get("external_id")
    if cve_id:
        external_ids["cve_id"] = cve_id
    if cwe_id:
        external_ids["cwe_id"] = cwe_id
    return external_ids


def clean_title(value: object, raw: Mapping[str, Any]) -> str:
    title = clean_optional(value or raw.get("source_url") or raw.get("external_id"))
    if not title:
        raise NormalizationError("raw record missing title/source URL")
    return title[:500]


def clean_optional(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def require_datetime(value: object, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    raise NormalizationError(f"raw record missing {field_name}")


def float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def severity_value(value: object) -> str:
    normalized = normalize_text(value)
    return normalized if normalized in {"unknown", "low", "medium", "high", "critical"} else "unknown"


def exploit_status_from_text(*values: object) -> str:
    haystack = normalize_text(" ".join(str(value or "") for value in values))
    if any(term in haystack for term in ("known exploited", "exploited", "kev")):
        return "exploited"
    if any(term in haystack for term in ("proof of concept", "poc")):
        return "proof_of_concept"
    return "unknown"


def ransomware_tag(value: str | None) -> str | None:
    if normalize_text(value) in {"known", "yes", "true"}:
        return "ransomware_use"
    return None


def compact_tags(values: list[object]) -> list[str]:
    tags: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = normalize_text(value).replace(" ", "_")
        if text:
            tags.add(text[:80])
    return sorted(tags)


def category_to_intelligence_type(category: str) -> str:
    return {
        "vulnerability": "vulnerability",
        "advisory": "advisory",
        "incident": "incident",
        "exposure": "exposure",
        "research_lead": "advisory",
    }.get(category, "advisory")


def manual_dedup_key(category: str, cve_id: str | None, title: str, source_name: str, source_url: str) -> str:
    if cve_id:
        return f"manual:cve:{cve_id}"
    signature = stable_hash(
        {
            "category": category,
            "title": normalize_text(title),
            "source_name": normalize_text(source_name),
            "source_url": source_url.lower(),
        }
    )
    return f"manual:{category}:{signature[:32]}"


def first_cpe_part(cve: Mapping[str, Any], part: str) -> str | None:
    configurations = cve.get("configurations")
    if not isinstance(configurations, list):
        return None
    index = {"vendor": 3, "product": 4, "version": 5}[part]
    for configuration in configurations:
        nodes = configuration.get("nodes") if isinstance(configuration, dict) else None
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            matches = node.get("cpeMatch") if isinstance(node, dict) else None
            if not isinstance(matches, list):
                continue
            for match in matches:
                criteria = match.get("criteria") if isinstance(match, dict) else None
                if isinstance(criteria, str) and criteria.startswith("cpe:"):
                    parts = criteria.split(":")
                    if len(parts) > index and parts[index] not in {"*", "-", ""}:
                        return parts[index]
    return None
