from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker

from app.api.schemas.intelligence import IntelligenceIngestRequest
from app.services.intelligence_ingest import _dedup_key as backend_dedup_key
from sentineldrive_worker.normalization.dedup import external_ingest_dedup_key, normalize_cve
from sentineldrive_worker.normalization.models import NormalizationError
from sentineldrive_worker.normalization.normalizers import ExternalIngestNormalizer
from sentineldrive_worker.normalization.service import normalize_pending_raw_intelligence, sanitize_error
from sentineldrive_worker.persistence.tables import metadata, raw_intelligence, sources, threat_intelligence, threat_intelligence_sources


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_nvd_and_cisa_kev_same_cve_merge_into_one_core_record(session_factory):
    nvd_source = seed_source(session_factory, "nvd", "api")
    kev_source = seed_source(session_factory, "cisa-kev", "api")
    first_seen = datetime(2026, 5, 18, tzinfo=timezone.utc)
    seed_raw(
        session_factory,
        source_id=nvd_source,
        source_name="nvd",
        source_type="api",
        source_url="https://nvd.nist.gov/vuln/detail/CVE-2026-0001",
        external_id="CVE-2026-0001",
        title="CVE-2026-0001 - T-Box firmware overflow",
        summary="Buffer overflow in ExampleAuto T-Box firmware.",
        first_seen_at=first_seen,
        metadata={
            "cvss": {"base_score": 9.8, "base_severity": "CRITICAL", "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"},
            "cwe": ["CWE-120"],
            "vuln_status": "Analyzed",
        },
        raw_content={
            "cve": {
                "id": "CVE-2026-0001",
                "configurations": [
                    {
                        "nodes": [
                            {
                                "cpeMatch": [
                                    {"criteria": "cpe:2.3:a:exampleauto:t-box_firmware:1.0:*:*:*:*:*:*:*"}
                                ]
                            }
                        ]
                    }
                ],
            }
        },
    )
    seed_raw(
        session_factory,
        source_id=kev_source,
        source_name="cisa-kev",
        source_type="api",
        source_url="https://www.cisa.gov/known-exploited-vulnerabilities-catalog?search_api_fulltext=CVE-2026-0001",
        external_id="CVE-2026-0001",
        title="CVE-2026-0001 - Known exploited vulnerability",
        summary="ExampleAuto T-Box firmware vulnerability is known exploited.",
        first_seen_at=first_seen + timedelta(days=1),
        metadata={
            "vendor_project": "ExampleAuto",
            "product": "T-Box",
            "vulnerability_name": "T-Box firmware overflow",
            "date_added": "2026-05-19",
            "due_date": "2026-06-10",
            "known_ransomware_campaign_use": "Known",
            "cwes": ["CWE-120"],
        },
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["normalized"] == 2
    with session_factory() as session:
        records = session.execute(select(threat_intelligence)).mappings().all()
        assert len(records) == 1
        record = records[0]
        assert record["dedup_key"] == "cve:CVE-2026-0001"
        assert record["cve_id"] == "CVE-2026-0001"
        assert record["cwe_id"] == "CWE-120"
        assert record["cvss_score"] == 9.8
        assert record["severity"] == "critical"
        assert record["exploit_status"] == "exploited"
        assert record["affected_vendor"] == "exampleauto"
        assert set(record["source_names"]) == {"nvd", "cisa-kev"}
        assert {"nvd", "cisa-kev", "kev", "known_exploited"}.issubset(set(record["tags"]))
        source_links = session.execute(select(threat_intelligence_sources)).mappings().all()
        assert len(source_links) == 2
        assert {link["source_name"] for link in source_links} == {"nvd", "cisa-kev"}
        raw_statuses = session.execute(select(raw_intelligence.c.processing_status, raw_intelligence.c.parsing_status)).all()
        assert raw_statuses == [("normalized", "normalized"), ("normalized", "normalized")]


def test_reprocessing_same_raw_row_is_idempotent_and_updates_source_last_seen(session_factory):
    source_id = seed_source(session_factory, "rss", "rss")
    raw_id = seed_raw(
        session_factory,
        source_id=source_id,
        source_name="rss",
        source_type="rss",
        source_url="https://example.test/advisory-1",
        external_id="advisory-1",
        title="Example advisory CVE-2026-0002",
        summary="Cloud API advisory for CVE-2026-0002.",
        first_seen_at=datetime(2026, 5, 19, tzinfo=timezone.utc),
        metadata={"feed_name": "Example Feed", "feed_url": "https://example.test/feed.xml"},
    )

    first = normalize_pending_raw_intelligence(session_factory=session_factory)
    with session_factory() as session:
        session.execute(
            raw_intelligence.update()
            .where(raw_intelligence.c.id == raw_id)
            .values(processing_status="collected", fetched_at=datetime(2026, 5, 20, tzinfo=timezone.utc))
        )
        session.commit()
    second = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert first["normalized"] == 1
    assert second["normalized"] == 1
    with session_factory() as session:
        assert len(session.execute(select(threat_intelligence)).mappings().all()) == 1
        assert len(session.execute(select(threat_intelligence_sources)).mappings().all()) == 1
        source_link = session.execute(select(threat_intelligence_sources)).mappings().one()
        assert source_link["last_seen_at"].replace(tzinfo=timezone.utc) == datetime(2026, 5, 20, tzinfo=timezone.utc)


def test_vendor_advisory_without_cve_uses_url_dedup_key_and_metadata_only_mapping(session_factory):
    source_id = seed_source(session_factory, "vendor-advisories", "vendor")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="vendor-advisories",
        source_type="vendor",
        source_url="https://psirt.bosch.com/security-advisories/bosch-2026-001",
        external_id="bosch-2026-001",
        title="Bosch security advisory 2026-001",
        summary="Bluetooth issue in vehicle head unit.",
        metadata={"vendor": "Bosch", "verification_status": "official_security_entry", "is_pdf": False},
        retained_payload_mode="metadata_only",
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["normalized"] == 1
    with session_factory() as session:
        record = session.execute(select(threat_intelligence)).mappings().one()
        assert record["intelligence_type"] == "advisory"
        assert record["dedup_key"].startswith("url:")
        assert record["affected_vendor"] == "Bosch"
        assert record["attack_surface"] == "bluetooth"
        assert record["vehicle_component"] == "ivi"
        assert "vendor_advisory" in record["tags"]


def test_manual_research_lead_raw_normalizes_like_manual_entry_behavior(session_factory):
    source_id = seed_source(session_factory, "manual-entry", "manual")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="Analyst Desk",
        source_type="manual",
        source_url="manual://analyst-desk",
        external_id="manual:lead:1",
        title="Research lead for charging exposure",
        summary="Analyst found a charging API exposure.",
        metadata={"manual_entry_category": "research_lead"},
        raw_content={"category": "research_lead", "tags": ["charging"], "attack_surface": "charging"},
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["normalized"] == 1
    with session_factory() as session:
        record = session.execute(select(threat_intelligence)).mappings().one()
        assert record["intelligence_type"] == "advisory"
        assert record["status"] == "under_review"
        assert {"manual", "research_lead", "charging"}.issubset(set(record["tags"]))
        assert record["dedup_key"].startswith("manual:research_lead:")


def test_manual_backend_normalized_raw_rows_are_skipped_by_pending_query(session_factory):
    source_id = seed_source(session_factory, "manual-entry", "manual")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="Manual Entry",
        source_type="manual",
        source_url="manual://entry",
        external_id="manual:cve:CVE-2026-9999",
        title="Already normalized manual entry",
        metadata={"entry_origin": "manual", "manual_entry_category": "vulnerability"},
        processing_status="normalized",
        parsing_status="normalized",
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["raw_seen"] == 0
    with session_factory() as session:
        assert session.execute(select(threat_intelligence)).mappings().all() == []


def test_unknown_malformed_raw_record_marks_failed_with_error(session_factory):
    source_id = seed_source(session_factory, "broken", "api")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="broken",
        source_type="api",
        source_url="",
        external_id=None,
        title=None,
        summary=None,
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["failed"] == 1
    with session_factory() as session:
        raw = session.execute(select(raw_intelligence)).mappings().one()
        assert raw["processing_status"] == "failed"
        assert raw["parsing_status"] == "failed"
        assert "missing title/source URL" in raw["error_message"]


def test_normalization_error_sanitizer_redacts_token_like_values():
    message = sanitize_error(ValueError("failed url https://example.test/item?token=super-secret"))

    assert "super-secret" not in message
    assert "[redacted]" in message


def _ingest_payload(**overrides):
    values = {
        "source_name": "AI Collector",
        "source_url": "https://intel.example.test/items/lead-1",
        "title": "Vehicle cloud API advisory",
        "summary": "AI整理的云端 API 线索。",
    }
    values.update(overrides)
    return IntelligenceIngestRequest(**values)


@pytest.mark.parametrize(
    "payload_kwargs",
    [
        {"cve_id": "CVE-2026-9001"},
        {"dedup_key": "platform-dedup-42"},
        {"external_id": "wx-42"},
        {"content_hash": "explicit-content-hash"},
        {},
    ],
)
def test_external_ingest_dedup_key_matches_backend(payload_kwargs):
    source_name = "AI Collector"
    source_url = "https://intel.example.test/items/lead-1"
    normalized_text_hash = "text-hash"
    payload = _ingest_payload(**payload_kwargs)

    expected = backend_dedup_key(payload, source_name, source_url, "derived-content", normalized_text_hash)
    actual = external_ingest_dedup_key(
        cve_id=normalize_cve(payload.cve_id),
        dedup_key=payload.dedup_key,
        external_id=payload.external_id,
        source_name=source_name,
        source_url=source_url,
        content_hash=payload.content_hash,
        normalized_text_hash=normalized_text_hash,
    )

    assert actual == expected


def test_external_ingest_dedup_key_text_branch_matches_backend():
    payload = _ingest_payload()
    expected = backend_dedup_key(payload, "AI Collector", "", "derived-content", "text-hash")
    actual = external_ingest_dedup_key(
        cve_id=None,
        dedup_key=None,
        external_id=None,
        source_name="AI Collector",
        source_url="",
        content_hash=None,
        normalized_text_hash="text-hash",
    )

    assert actual == expected == "text:text-hash"


def test_external_ingest_normalization_maps_fields_and_matches_ingest_dedup_key(session_factory):
    source_id = seed_source(session_factory, "external-collector", "api")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="AI Collector",
        source_type="api",
        source_url="https://intel.example.test/items/wx-9001",
        external_id="wx-9001",
        title="CVE-2026-9001 affects vehicle cloud API",
        summary="AI整理的车联网云端 API 漏洞线索。",
        first_seen_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        metadata={
            "entry_origin": "external_ingest",
            "platform": "weixin",
            "cnvd_id": "CNVD-2026-0001",
            "vendor_advisory_id": "VAD-1",
            "affected_vendor": "ExampleAuto",
            "affected_products": ["cloud gateway"],
            "components": ["cloud api"],
            "attack_surfaces": ["cloud_api"],
            "severity": "high",
            "external_score": 8.8,
        },
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["normalized"] == 1
    with session_factory() as session:
        record = session.execute(select(threat_intelligence)).mappings().one()
        assert record["dedup_key"] == "cve:CVE-2026-9001"
        assert record["cve_id"] == "CVE-2026-9001"
        assert record["intelligence_type"] == "vulnerability"
        assert record["severity"] == "high"
        assert record["risk_level"] == "high"
        assert float(record["risk_score"]) == 8.8
        assert record["affected_vendor"] == "ExampleAuto"
        assert record["affected_product"] == "cloud gateway"
        assert record["vehicle_component"] == "cloud_api"
        assert record["attack_surface"] == "cloud_api"
        assert {"external_ingest", "weixin", "cloud_api"}.issubset(set(record["tags"]))
        assert record["external_ids"]["external_id"] == "wx-9001"
        assert record["external_ids"]["cve_id"] == "CVE-2026-9001"
        assert record["external_ids"]["cnvd_id"] == "CNVD-2026-0001"
        assert record["external_ids"]["vendor_advisory_id"] == "VAD-1"
        source_links = session.execute(select(threat_intelligence_sources)).mappings().all()
        assert len(source_links) == 1
        assert source_links[0]["source_name"] == "AI Collector"
        assert source_links[0]["external_id"] == "wx-9001"
        raw_statuses = session.execute(select(raw_intelligence.c.processing_status, raw_intelligence.c.parsing_status)).all()
        assert raw_statuses == [("normalized", "normalized")]


def test_external_ingest_normalizer_skips_already_normalized_row():
    normalizer = ExternalIngestNormalizer()
    raw_row = {
        "source_name": "AI Collector",
        "source_type": "api",
        "source_url": "https://intel.example.test/items/already-normalized",
        "external_id": "wx-already",
        "title": "Already normalized external ingest",
        "summary": "summary",
        "snippet": "summary",
        "content_hash": "content-already",
        "processing_status": "normalized",
        "parsing_status": "normalized",
        "fetched_at": datetime(2026, 6, 15, tzinfo=timezone.utc),
        "first_seen_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "metadata": {"entry_origin": "external_ingest"},
    }

    with pytest.raises(NormalizationError):
        normalizer.normalize(raw_row)


def test_external_ingest_normalized_raw_rows_are_skipped_by_pending_query(session_factory):
    source_id = seed_source(session_factory, "external-collector", "api")
    seed_raw(
        session_factory,
        source_id=source_id,
        source_name="AI Collector",
        source_type="api",
        source_url="https://intel.example.test/items/already-normalized",
        external_id="wx-already",
        title="Already normalized external ingest",
        metadata={"entry_origin": "external_ingest"},
        processing_status="normalized",
        parsing_status="normalized",
    )

    result = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert result["raw_seen"] == 0
    with session_factory() as session:
        assert session.execute(select(threat_intelligence)).mappings().all() == []


def test_external_ingest_reprocessing_converges_on_single_core_record(session_factory):
    source_id = seed_source(session_factory, "external-collector", "api")
    raw_id = seed_raw(
        session_factory,
        source_id=source_id,
        source_name="AI Collector",
        source_type="api",
        source_url="https://intel.example.test/items/lead-no-cve",
        external_id="wx-42",
        title="Vehicle cloud API exposure lead",
        summary="No CVE, dedup by external id.",
        metadata={"entry_origin": "external_ingest", "attack_surfaces": ["cloud_api"]},
    )

    first = normalize_pending_raw_intelligence(session_factory=session_factory)
    with session_factory() as session:
        session.execute(
            raw_intelligence.update()
            .where(raw_intelligence.c.id == raw_id)
            .values(processing_status="collected")
        )
        session.commit()
    second = normalize_pending_raw_intelligence(session_factory=session_factory)

    assert first["normalized"] == 1
    assert second["normalized"] == 1
    with session_factory() as session:
        assert len(session.execute(select(threat_intelligence)).mappings().all()) == 1
        assert len(session.execute(select(threat_intelligence_sources)).mappings().all()) == 1


def seed_source(session_factory, name: str, source_type: str):
    source_id = uuid4()
    with session_factory() as session:
        session.execute(
            insert(sources).values(
                id=source_id,
                name=name,
                source_type=source_type,
                base_url=f"https://example.test/{name}",
                status="enabled",
                config={},
            )
        )
        session.commit()
    return source_id


def seed_raw(
    session_factory,
    *,
    source_id,
    source_name: str,
    source_type: str,
    source_url: str,
    external_id: str | None,
    title: str | None,
    summary: str | None = None,
    first_seen_at: datetime | None = None,
    metadata: dict | None = None,
    raw_content: dict | None = None,
    retained_payload_mode: str = "raw_payload",
    processing_status: str = "collected",
    parsing_status: str = "pending",
):
    raw_id = uuid4()
    now = first_seen_at or datetime(2026, 5, 19, tzinfo=timezone.utc)
    with session_factory() as session:
        session.execute(
            insert(raw_intelligence).values(
                id=raw_id,
                source_id=source_id,
                source_name=source_name,
                source_type=source_type,
                source_url=source_url,
                external_id=external_id,
                fetched_at=now,
                first_seen_at=now,
                title=title,
                summary=summary,
                snippet=summary[:500] if summary else None,
                raw_content=raw_content,
                raw_hash=f"raw-{raw_id}",
                content_hash=f"content-{raw_id}",
                parsing_status=parsing_status,
                processing_status=processing_status,
                error_message=None,
                metadata=metadata or {},
                retained_payload_mode=retained_payload_mode,
            )
        )
        session.commit()
    return raw_id
