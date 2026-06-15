from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker

from sentineldrive_worker.persistence.tables import metadata, threat_intelligence
from sentineldrive_worker.scoring.rules import risk_level_for_score, score_threat_intelligence
from sentineldrive_worker.scoring.service import sanitize_error, score_pending_threat_intelligence


def test_risk_level_boundary_ranges():
    assert risk_level_for_score(100) == "critical"
    assert risk_level_for_score(90) == "critical"
    assert risk_level_for_score(89.99) == "high"
    assert risk_level_for_score(70) == "high"
    assert risk_level_for_score(69.99) == "medium"
    assert risk_level_for_score(40) == "medium"
    assert risk_level_for_score(39.99) == "low"
    assert risk_level_for_score(0) == "low"


def test_missing_cvss_uses_severity_and_source_confidence():
    result = score_threat_intelligence(
        base_record(
            cvss_score=None,
            severity="medium",
            confidence="low",
            tags=[],
            metadata={},
        )
    )

    assert result.risk_level == "low"
    assert result.risk_score == 24.0
    factors = {factor["key"]: factor for factor in result.explanation["factors"]}
    assert factors["severity"]["evidence"] == "medium"
    assert factors["source_confidence"]["contribution"] == -8.0


def test_kev_poc_remote_auth_and_vehicle_component_signals_reach_critical():
    result = score_threat_intelligence(
        base_record(
            title="CISA KEV CVE-2026-1001 T-Box remote unauthenticated exploit",
            summary="Public PoC exploit code targets a T-Box over the network.",
            source_names=["nvd", "cisa-kev"],
            cvss_score=9.8,
            cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            vehicle_component="tbox",
            attack_surface="cellular",
            exploit_status="exploited",
            confidence="high",
            tags=["cisa-kev", "known_exploited", "poc"],
            metadata={"date_added": "2026-05-20"},
        )
    )

    assert result.risk_score == 100.0
    assert result.risk_level == "critical"
    factor_keys = {factor["key"] for factor in result.explanation["factors"]}
    assert {
        "cvss",
        "known_exploited",
        "public_poc",
        "remote_exploitability",
        "authentication_requirement",
        "vehicle_critical_component",
        "source_confidence",
    }.issubset(factor_keys)
    assert result.explanation["signals"]["authentication"] == "none_required"
    assert result.explanation["signals"]["vehicle_component"] == "tbox"


def test_multi_vendor_common_component_materially_increases_score():
    base = base_record(
        title="OTA library vulnerability",
        summary="Authenticated OTA service flaw.",
        cvss_score=7.1,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:L/A:L",
        affected_vendor="ExampleAuto",
        affected_product="OTA updater",
        vehicle_component="ota",
    )
    common = {
        **base,
        "summary": "Multi-vendor OTA OpenSSL common component flaw with authenticated access.",
        "affected_vendor": "multiple",
        "affected_product": "OpenSSL OTA updater",
    }

    base_result = score_threat_intelligence(base)
    common_result = score_threat_intelligence(common)

    assert common_result.risk_score == base_result.risk_score + 8.0
    assert common_result.explanation["signals"]["multi_vendor_or_common_component"] is True


def test_scoring_service_updates_metadata_idempotently(session_factory):
    record_id = seed_threat_intelligence(
        session_factory,
        title="Charging API unauthenticated remote exposure",
        summary="Public PoC for remote charging API access without authentication.",
        cvss_score=8.8,
        cvss_vector="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:L",
        vehicle_component="charging",
        attack_surface="cloud_api",
        tags=["poc"],
        metadata={"normalizers": ["VendorAdvisoryNormalizer"], "owner_note": "triage"},
    )

    first = score_pending_threat_intelligence(session_factory=session_factory)
    second = score_pending_threat_intelligence(session_factory=session_factory)

    assert first["scored"] == 1
    assert second["rows_seen"] == 0
    with session_factory() as session:
        row = session.execute(select(threat_intelligence).where(threat_intelligence.c.id == record_id)).mappings().one()
        assert float(row["risk_score"]) == 100.0
        assert row["risk_level"] == "critical"
        assert row["metadata"]["normalizers"] == ["VendorAdvisoryNormalizer"]
        assert row["metadata"]["owner_note"] == "triage"
        assert row["metadata"]["scoring"]["rule_version"] == "fixed-risk-v1"

    forced = score_pending_threat_intelligence(session_factory=session_factory, force=True)

    assert forced["unchanged"] == 1
    with session_factory() as session:
        rows = session.execute(select(threat_intelligence)).mappings().all()
        assert len(rows) == 1


def test_scoring_service_scores_info_records_and_skips_non_normalized(session_factory):
    score_me = seed_threat_intelligence(session_factory, title="CAN issue", severity="high", vehicle_component="can", risk_score=50.0, risk_level="info")
    skipped = seed_threat_intelligence(
        session_factory,
        title="Pending row",
        severity="critical",
        processing_status="pending",
    )

    result = score_pending_threat_intelligence(session_factory=session_factory)

    assert result["rows_seen"] == 1
    assert result["scored"] == 1
    with session_factory() as session:
        scored = session.execute(select(threat_intelligence).where(threat_intelligence.c.id == score_me)).mappings().one()
        pending = session.execute(select(threat_intelligence).where(threat_intelligence.c.id == skipped)).mappings().one()
        assert scored["risk_level"] == "medium"
        assert "scoring" in scored["metadata"]
        assert pending["risk_score"] is None
        assert pending["risk_level"] == "info"


def test_scoring_error_sanitizer_redacts_token_like_values():
    message = sanitize_error(ValueError("failed callback https://example.test/item?api_key=super-secret&ref=public token=private"))

    assert "super-secret" not in message
    assert "private" not in message
    assert "[redacted]" in message


def base_record(**overrides):
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    record = {
        "id": uuid4(),
        "title": "Example vulnerability",
        "summary": "Example summary",
        "intelligence_type": "vulnerability",
        "source_names": ["nvd"],
        "source_urls": ["https://example.test/CVE-2026-1000"],
        "external_ids": {"cve_id": "CVE-2026-1000"},
        "cve_id": "CVE-2026-1000",
        "cwe_id": None,
        "cvss_score": 7.0,
        "cvss_vector": None,
        "severity": "high",
        "affected_vendor": "ExampleAuto",
        "affected_product": "Example Product",
        "affected_version": None,
        "vehicle_component": None,
        "attack_surface": None,
        "exploit_status": "unknown",
        "confidence": "medium",
        "risk_score": None,
        "risk_level": "info",
        "tags": [],
        "first_seen_at": now,
        "last_seen_at": now,
        "dedup_key": "cve:CVE-2026-1000",
        "normalized_text_hash": "hash",
        "processing_status": "normalized",
        "status": "active",
        "metadata": {},
    }
    record.update(overrides)
    return record


def seed_threat_intelligence(session_factory, **overrides):
    record_id = overrides.pop("id", uuid4())
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    values = {
        "id": record_id,
        "raw_intelligence_id": None,
        "title": "Example vulnerability",
        "summary": None,
        "intelligence_type": "vulnerability",
        "source_names": ["nvd"],
        "source_urls": ["https://example.test/advisory"],
        "canonical_source_url": "https://example.test/advisory",
        "external_ids": {},
        "cve_id": None,
        "cwe_id": None,
        "cvss_score": None,
        "cvss_vector": None,
        "severity": "unknown",
        "affected_vendor": None,
        "affected_product": None,
        "affected_version": None,
        "vehicle_component": None,
        "attack_surface": None,
        "exploit_status": "unknown",
        "confidence": "medium",
        "risk_score": None,
        "risk_level": "info",
        "tags": [],
        "first_seen_at": now,
        "last_seen_at": now,
        "dedup_key": f"test:{record_id}",
        "normalized_text_hash": f"hash-{record_id}",
        "processing_status": "normalized",
        "status": "active",
        "metadata": {},
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    with session_factory() as session:
        session.execute(insert(threat_intelligence).values(**values))
        session.commit()
    return record_id


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
