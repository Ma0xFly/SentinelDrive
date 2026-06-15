from __future__ import annotations

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

try:
    from sqlalchemy import Uuid
except ImportError:  # pragma: no cover - SQLAlchemy 2.x provides Uuid in supported envs.
    from sqlalchemy import String as Uuid


metadata = MetaData()

string_array = postgresql.ARRAY(String(160)).with_variant(JSON, "sqlite")
text_array = postgresql.ARRAY(Text()).with_variant(JSON, "sqlite")
tag_array = postgresql.ARRAY(String(80)).with_variant(JSON, "sqlite")
search_vector_type = postgresql.TSVECTOR().with_variant(Text(), "sqlite")


class CastingPostgresEnum(postgresql.ENUM):
    render_bind_cast = True


def postgres_enum(name: str, *values: str):
    return CastingPostgresEnum(*values, name=name, create_type=False).with_variant(String(40), "sqlite")


alert_status_type = postgres_enum("alert_status", "open", "acknowledged", "closed")
attack_surface_type = postgres_enum(
    "attack_surface",
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
)
confidence_level_type = postgres_enum("confidence_level", "low", "medium", "high")
exploit_status_type = postgres_enum("exploit_status", "unknown", "none_known", "proof_of_concept", "exploited")
intelligence_type_type = postgres_enum("intelligence_type", "vulnerability", "exposure", "incident", "advisory")
job_status_type = postgres_enum("job_status", "queued", "running", "success", "failed")
processing_status_type = postgres_enum("processing_status", "pending", "collected", "processing", "normalized", "failed", "skipped")
risk_level_type = postgres_enum("risk_level", "info", "low", "medium", "high", "critical")
severity_type = postgres_enum("severity", "unknown", "low", "medium", "high", "critical")
source_status_type = postgres_enum("source_status", "enabled", "disabled", "error")
source_type_type = postgres_enum("source_type", "api", "rss", "html", "pdf", "manual", "vendor")
vehicle_component_type = postgres_enum(
    "vehicle_component",
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
)

sources = Table(
    "sources",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(120), nullable=False),
    Column("source_type", source_type_type, nullable=False),
    Column("base_url", Text),
    Column("status", source_status_type, nullable=False),
    Column("config", JSON, nullable=False, default=dict),
    Column("last_success_at", DateTime(timezone=True)),
    Column("last_error_at", DateTime(timezone=True)),
    Column("last_error_message", Text),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("name", name="uq_sources_name"),
)

sync_states = Table(
    "sync_states",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("source_id", Uuid(as_uuid=True), nullable=False),
    Column("cursor", Text),
    Column("status", job_status_type, nullable=False),
    Column("last_run_at", DateTime(timezone=True)),
    Column("next_run_at", DateTime(timezone=True)),
    Column("consecutive_failures", Integer, nullable=False, default=0),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("source_id", name="uq_sync_states_source_id"),
)

job_logs = Table(
    "job_logs",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("job_name", String(160), nullable=False),
    Column("source_id", Uuid(as_uuid=True)),
    Column("status", job_status_type, nullable=False),
    Column("started_at", DateTime(timezone=True)),
    Column("finished_at", DateTime(timezone=True)),
    Column("items_seen", Integer, nullable=False, default=0),
    Column("items_created", Integer, nullable=False, default=0),
    Column("items_updated", Integer, nullable=False, default=0),
    Column("error_message", Text),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)

raw_intelligence = Table(
    "raw_intelligence",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("source_id", Uuid(as_uuid=True)),
    Column("source_name", String(160), nullable=False),
    Column("source_type", source_type_type, nullable=False),
    Column("source_url", Text, nullable=False),
    Column("external_id", String(240)),
    Column("fetched_at", DateTime(timezone=True), nullable=False),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("title", String(500)),
    Column("summary", Text),
    Column("snippet", Text),
    Column("raw_content", JSON),
    Column("raw_hash", String(128), nullable=False),
    Column("content_hash", String(128)),
    Column("parsing_status", processing_status_type, nullable=False),
    Column("processing_status", processing_status_type, nullable=False),
    Column("error_message", Text),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("retained_payload_mode", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("raw_hash", name="uq_raw_intelligence_raw_hash"),
    UniqueConstraint("source_id", "external_id", name="uq_raw_intelligence_source_external_id"),
)

threat_intelligence = Table(
    "threat_intelligence",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("raw_intelligence_id", Uuid(as_uuid=True)),
    Column("title", String(500), nullable=False),
    Column("summary", Text),
    Column("intelligence_type", intelligence_type_type, nullable=False),
    Column("source_names", string_array, nullable=False, default=list),
    Column("source_urls", text_array, nullable=False, default=list),
    Column("canonical_source_url", Text),
    Column("external_ids", JSON, nullable=False, default=dict),
    Column("cve_id", String(32)),
    Column("cwe_id", String(32)),
    Column("cvss_score", Float),
    Column("cvss_vector", String(160)),
    Column("severity", severity_type, nullable=False, default="unknown"),
    Column("affected_vendor", String(160)),
    Column("affected_product", String(200)),
    Column("affected_version", String(200)),
    Column("vehicle_component", vehicle_component_type),
    Column("attack_surface", attack_surface_type),
    Column("exploit_status", exploit_status_type, nullable=False, default="unknown"),
    Column("confidence", confidence_level_type, nullable=False, default="medium"),
    Column("risk_score", Numeric(5, 2)),
    Column("risk_level", risk_level_type, nullable=False, default="info"),
    Column("tags", tag_array, nullable=False, default=list),
    Column("first_seen_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("dedup_key", String(320), nullable=False),
    Column("normalized_text_hash", String(128)),
    Column("processing_status", processing_status_type, nullable=False, default="normalized"),
    Column("status", String(40), nullable=False, default="active"),
    Column("search_vector", search_vector_type),
    Column("metadata", JSON, nullable=False, default=dict),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("dedup_key", name="uq_threat_intelligence_dedup_key"),
)

threat_intelligence_sources = Table(
    "threat_intelligence_sources",
    metadata,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("threat_intelligence_id", Uuid(as_uuid=True), nullable=False),
    Column("source_id", Uuid(as_uuid=True)),
    Column("raw_intelligence_id", Uuid(as_uuid=True)),
    Column("source_name", String(160), nullable=False),
    Column("source_url", Text, nullable=False),
    Column("external_id", String(240)),
    Column("first_seen_at", DateTime(timezone=True)),
    Column("last_seen_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
    UniqueConstraint("threat_intelligence_id", "source_url", name="uq_threat_intelligence_sources_url"),
)
