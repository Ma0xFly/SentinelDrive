"""create core persistence tables

Revision ID: 20260519_0001
Revises:
Create Date: 2026-05-19
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260519_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    alert_status = postgresql.ENUM("open", "acknowledged", "closed", name="alert_status", create_type=False)
    attack_surface = postgresql.ENUM(
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
        name="attack_surface",
        create_type=False,
    )
    audit_action = postgresql.ENUM(
        "manual_entry",
        "status_change",
        "user_change",
        "alert_closure",
        name="audit_action",
        create_type=False,
    )
    confidence_level = postgresql.ENUM("low", "medium", "high", name="confidence_level", create_type=False)
    export_format = postgresql.ENUM("csv", "markdown", "pdf", name="export_format", create_type=False)
    export_status = postgresql.ENUM("pending", "running", "completed", "failed", name="export_status", create_type=False)
    exploit_status = postgresql.ENUM(
        "unknown",
        "none_known",
        "proof_of_concept",
        "exploited",
        name="exploit_status",
        create_type=False,
    )
    intelligence_type = postgresql.ENUM(
        "vulnerability",
        "exposure",
        "incident",
        "advisory",
        name="intelligence_type",
        create_type=False,
    )
    job_status = postgresql.ENUM("queued", "running", "success", "failed", name="job_status", create_type=False)
    processing_status = postgresql.ENUM(
        "pending",
        "collected",
        "processing",
        "normalized",
        "failed",
        "skipped",
        name="processing_status",
        create_type=False,
    )
    risk_level = postgresql.ENUM("info", "low", "medium", "high", "critical", name="risk_level", create_type=False)
    severity = postgresql.ENUM("unknown", "low", "medium", "high", "critical", name="severity", create_type=False)
    source_status = postgresql.ENUM("enabled", "disabled", "error", name="source_status", create_type=False)
    source_type = postgresql.ENUM("api", "rss", "html", "pdf", "manual", "vendor", name="source_type", create_type=False)
    vehicle_component = postgresql.ENUM(
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
        name="vehicle_component",
        create_type=False,
    )

    for enum in (
        alert_status,
        attack_surface,
        audit_action,
        confidence_level,
        export_format,
        export_status,
        exploit_status,
        intelligence_type,
        job_status,
        processing_status,
        risk_level,
        severity,
        source_status,
        source_type,
        vehicle_component,
    ):
        enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sources",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("status", source_status, nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )
    op.create_index("ix_sources_type_status", "sources", ["source_type", "status"])

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_is_active", "users", ["is_active"])

    op.create_table(
        "job_logs",
        sa.Column("job_name", sa.String(length=160), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_seen", sa.Integer(), nullable=False),
        sa.Column("items_created", sa.Integer(), nullable=False),
        sa.Column("items_updated", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_job_logs_source_id_sources"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_logs")),
    )
    op.create_index("ix_job_logs_job_name_status", "job_logs", ["job_name", "status"])
    op.create_index("ix_job_logs_source_status_started", "job_logs", ["source_id", "status", "started_at"])

    op.create_table(
        "raw_intelligence",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_type", source_type, nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("raw_content", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_hash", sa.String(length=128), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("parsing_status", processing_status, nullable=False),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retained_payload_mode", sa.String(length=40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_raw_intelligence_source_id_sources"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_intelligence")),
        sa.UniqueConstraint("raw_hash", name="uq_raw_intelligence_raw_hash"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_raw_intelligence_source_external_id"),
    )
    op.create_index("ix_raw_intelligence_source_fetch", "raw_intelligence", ["source_id", "fetched_at"])
    op.create_index("ix_raw_intelligence_source_url", "raw_intelligence", ["source_url"])
    op.create_index("ix_raw_intelligence_status_parsing", "raw_intelligence", ["processing_status", "parsing_status"])

    op.create_table(
        "sync_states",
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("status", job_status, nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], name=op.f("fk_sync_states_source_id_sources"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_states")),
        sa.UniqueConstraint("source_id", name="uq_sync_states_source_id"),
    )
    op.create_index("ix_sync_states_status_next", "sync_states", ["status", "next_run_at"])

    op.create_table(
        "threat_intelligence",
        sa.Column("raw_intelligence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("intelligence_type", intelligence_type, nullable=False),
        sa.Column("source_names", postgresql.ARRAY(sa.String(length=160)), nullable=False),
        sa.Column("source_urls", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("canonical_source_url", sa.Text(), nullable=True),
        sa.Column("external_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cve_id", sa.String(length=32), nullable=True),
        sa.Column("cwe_id", sa.String(length=32), nullable=True),
        sa.Column("cvss_score", sa.Float(), nullable=True),
        sa.Column("cvss_vector", sa.String(length=160), nullable=True),
        sa.Column("severity", severity, nullable=False),
        sa.Column("affected_vendor", sa.String(length=160), nullable=True),
        sa.Column("affected_product", sa.String(length=200), nullable=True),
        sa.Column("affected_version", sa.String(length=200), nullable=True),
        sa.Column("vehicle_component", vehicle_component, nullable=True),
        sa.Column("attack_surface", attack_surface, nullable=True),
        sa.Column("exploit_status", exploit_status, nullable=False),
        sa.Column("confidence", confidence_level, nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=80)), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedup_key", sa.String(length=320), nullable=False),
        sa.Column("normalized_text_hash", sa.String(length=128), nullable=True),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["raw_intelligence_id"],
            ["raw_intelligence.id"],
            name=op.f("fk_threat_intelligence_raw_intelligence_id_raw_intelligence"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_threat_intelligence")),
        sa.UniqueConstraint("dedup_key", name="uq_threat_intelligence_dedup_key"),
    )
    op.create_index("ix_threat_intelligence_attack_surface", "threat_intelligence", ["attack_surface"])
    op.create_index("ix_threat_intelligence_component", "threat_intelligence", ["vehicle_component"])
    op.create_index("ix_threat_intelligence_cve_id", "threat_intelligence", ["cve_id"])
    op.create_index("ix_threat_intelligence_cwe_id", "threat_intelligence", ["cwe_id"])
    op.create_index("ix_threat_intelligence_risk_status", "threat_intelligence", ["risk_level", "processing_status"])
    op.create_index("ix_threat_intelligence_search", "threat_intelligence", ["search_vector"], postgresql_using="gin")
    op.create_index("ix_threat_intelligence_seen", "threat_intelligence", ["first_seen_at", "last_seen_at"])
    op.create_index("ix_threat_intelligence_tags", "threat_intelligence", ["tags"], postgresql_using="gin")
    op.create_index(
        "ix_threat_intelligence_vendor_product",
        "threat_intelligence",
        ["affected_vendor", "affected_product"],
    )

    op.create_table(
        "audit_events",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name=op.f("fk_audit_events_actor_user_id_users"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_action_created", "audit_events", ["action", "created_at"])
    op.create_index("ix_audit_events_actor_created", "audit_events", ["actor_user_id", "created_at"])
    op.create_index("ix_audit_events_entity", "audit_events", ["entity_type", "entity_id"])

    op.create_table(
        "export_jobs",
        sa.Column("requested_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("export_format", export_format, nullable=False),
        sa.Column("status", export_status, nullable=False),
        sa.Column("filter_spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("artifact_hash", sa.String(length=128), nullable=True),
        sa.Column("redaction_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_export_jobs_requested_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_export_jobs")),
    )
    op.create_index("ix_export_jobs_created_at", "export_jobs", ["created_at"])
    op.create_index("ix_export_jobs_format_status", "export_jobs", ["export_format", "status"])
    op.create_index("ix_export_jobs_requested_by_status", "export_jobs", ["requested_by_user_id", "status"])

    op.create_table(
        "alerts",
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("threat_intelligence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggering_rule", sa.String(length=240), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", alert_status, nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["threat_intelligence_id"],
            ["threat_intelligence.id"],
            name=op.f("fk_alerts_threat_intelligence_id_threat_intelligence"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_alerts")),
    )
    op.create_index("ix_alerts_intelligence_id", "alerts", ["threat_intelligence_id"])
    op.create_index("ix_alerts_risk_status", "alerts", ["risk_level", "status"])
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"])

    op.create_table(
        "threat_intelligence_sources",
        sa.Column("threat_intelligence_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("raw_intelligence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("external_id", sa.String(length=240), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["raw_intelligence_id"],
            ["raw_intelligence.id"],
            name=op.f("fk_threat_intelligence_sources_raw_intelligence_id_raw_intelligence"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_threat_intelligence_sources_source_id_sources"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["threat_intelligence_id"],
            ["threat_intelligence.id"],
            name=op.f("fk_threat_intelligence_sources_threat_intelligence_id_threat_intelligence"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_threat_intelligence_sources")),
        sa.UniqueConstraint("threat_intelligence_id", "source_url", name="uq_threat_intelligence_sources_url"),
    )
    op.create_index("ix_threat_intelligence_sources_external_id", "threat_intelligence_sources", ["external_id"])
    op.create_index("ix_threat_intelligence_sources_source_name", "threat_intelligence_sources", ["source_name"])


def downgrade() -> None:
    op.drop_index("ix_threat_intelligence_sources_source_name", table_name="threat_intelligence_sources")
    op.drop_index("ix_threat_intelligence_sources_external_id", table_name="threat_intelligence_sources")
    op.drop_table("threat_intelligence_sources")
    op.drop_index("ix_alerts_triggered_at", table_name="alerts")
    op.drop_index("ix_alerts_risk_status", table_name="alerts")
    op.drop_index("ix_alerts_intelligence_id", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index("ix_export_jobs_requested_by_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_format_status", table_name="export_jobs")
    op.drop_index("ix_export_jobs_created_at", table_name="export_jobs")
    op.drop_table("export_jobs")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_created", table_name="audit_events")
    op.drop_index("ix_audit_events_action_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_threat_intelligence_vendor_product", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_tags", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_seen", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_search", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_risk_status", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_cwe_id", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_cve_id", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_component", table_name="threat_intelligence")
    op.drop_index("ix_threat_intelligence_attack_surface", table_name="threat_intelligence")
    op.drop_table("threat_intelligence")
    op.drop_index("ix_sync_states_status_next", table_name="sync_states")
    op.drop_table("sync_states")
    op.drop_index("ix_raw_intelligence_status_parsing", table_name="raw_intelligence")
    op.drop_index("ix_raw_intelligence_source_url", table_name="raw_intelligence")
    op.drop_index("ix_raw_intelligence_source_fetch", table_name="raw_intelligence")
    op.drop_table("raw_intelligence")
    op.drop_index("ix_job_logs_source_status_started", table_name="job_logs")
    op.drop_index("ix_job_logs_job_name_status", table_name="job_logs")
    op.drop_table("job_logs")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_sources_type_status", table_name="sources")
    op.drop_table("sources")

    for enum_name in (
        "vehicle_component",
        "source_type",
        "source_status",
        "severity",
        "risk_level",
        "processing_status",
        "job_status",
        "intelligence_type",
        "exploit_status",
        "export_status",
        "export_format",
        "confidence_level",
        "audit_action",
        "attack_surface",
        "alert_status",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
