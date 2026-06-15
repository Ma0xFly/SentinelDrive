from datetime import datetime, timezone

from sqlalchemy import Enum

from app.db.base import Base
from app.db.types import (
    AttackSurface,
    AuditAction,
    IntelligenceType,
    ProcessingStatus,
    SourceType,
    VehicleComponent,
)
from app.models.intelligence import RawIntelligence, ThreatIntelligence
from app.models.security import User
from app.security.passwords import hash_password, verify_password


def table_names() -> set[str]:
    return set(Base.metadata.tables)


def index_names(table_name: str) -> set[str]:
    return {index.name for index in Base.metadata.tables[table_name].indexes}


def unique_constraint_names(table_name: str) -> set[str]:
    return {
        constraint.name
        for constraint in Base.metadata.tables[table_name].constraints
        if constraint.name and constraint.name.startswith("uq_")
    }


def test_core_tables_are_registered():
    assert {
        "users",
        "sources",
        "sync_states",
        "job_logs",
        "raw_intelligence",
        "threat_intelligence",
        "threat_intelligence_sources",
        "alerts",
        "audit_events",
        "export_jobs",
    }.issubset(table_names())


def test_required_dedup_constraints_exist():
    assert "uq_raw_intelligence_raw_hash" in unique_constraint_names("raw_intelligence")
    assert "uq_raw_intelligence_source_external_id" in unique_constraint_names("raw_intelligence")
    assert "uq_threat_intelligence_dedup_key" in unique_constraint_names("threat_intelligence")
    assert "uq_threat_intelligence_sources_url" in unique_constraint_names("threat_intelligence_sources")


def test_expected_filter_indexes_exist():
    assert {
        "ix_threat_intelligence_cve_id",
        "ix_threat_intelligence_risk_status",
        "ix_threat_intelligence_tags",
        "ix_threat_intelligence_search",
        "ix_threat_intelligence_vendor_product",
        "ix_threat_intelligence_component",
        "ix_threat_intelligence_attack_surface",
    }.issubset(index_names("threat_intelligence"))
    assert "ix_alerts_risk_status" in index_names("alerts")
    assert "ix_raw_intelligence_status_parsing" in index_names("raw_intelligence")


def test_vehicle_domain_values_are_representable():
    assert {item.value for item in VehicleComponent} == {
        "app",
        "tbox",
        "ivi",
        "ota",
        "v2x",
        "charging",
        "cloud_api",
        "bluetooth",
        "wifi",
        "cellular",
        "can",
        "usb",
    }
    assert {item.value for item in AttackSurface} == {item.value for item in VehicleComponent}


def test_required_mvp_intelligence_types_are_representable():
    assert {item.value for item in IntelligenceType} == {
        "vulnerability",
        "exposure",
        "incident",
        "advisory",
    }


def test_auth_audit_action_values_are_representable():
    assert {
        "login_success",
        "login_failure",
        "logout",
        "manual_entry",
        "status_change",
        "user_change",
    }.issubset({item.value for item in AuditAction})


def test_enum_columns_store_database_values_not_member_names():
    source_type = RawIntelligence.__table__.c.source_type.type

    assert isinstance(source_type, Enum)
    assert "api" in source_type.enums
    assert "API" not in source_type.enums


def test_raw_intelligence_supports_metadata_only_html_pdf_retention():
    raw = RawIntelligence(
        source_name="Vendor Advisory",
        source_type=SourceType.HTML,
        source_url="https://example.test/advisory",
        fetched_at=datetime.now(timezone.utc),
        first_seen_at=datetime.now(timezone.utc),
        title="Advisory",
        summary="Short metadata summary",
        snippet="Relevant snippet",
        raw_hash="hash",
        raw_content=None,
        retained_payload_mode="metadata_only",
    )

    assert raw.raw_content is None
    assert raw.retained_payload_mode == "metadata_only"


def test_threat_intelligence_supports_cve_and_dedup_fields():
    item = ThreatIntelligence(
        title="CVE-2026-0001 in T-Box firmware",
        intelligence_type="vulnerability",
        source_names=["NVD"],
        source_urls=["https://nvd.nist.gov/vuln/detail/CVE-2026-0001"],
        cve_id="CVE-2026-0001",
        affected_vendor="ExampleAuto",
        affected_product="T-Box",
        vehicle_component=VehicleComponent.TBOX,
        attack_surface=AttackSurface.CELLULAR,
        tags=["cve", "tbox"],
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        dedup_key="cve:CVE-2026-0001",
    )

    assert item.cve_id == "CVE-2026-0001"
    assert item.dedup_key == "cve:CVE-2026-0001"
    assert item.vehicle_component == VehicleComponent.TBOX


def test_user_password_storage_uses_hash_not_plaintext():
    password_hash = hash_password("change-me-development-only")
    user = User(email="admin@example.test", password_hash=password_hash, is_admin=True)

    assert "change-me-development-only" not in user.password_hash
    assert verify_password("change-me-development-only", user.password_hash)
    assert not verify_password("wrong-password", user.password_hash)
