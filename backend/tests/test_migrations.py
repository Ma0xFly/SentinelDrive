from pathlib import Path


MIGRATION = Path("migrations/versions/20260519_0001_create_core_tables.py")
AUTH_AUDIT_MIGRATION = Path("migrations/versions/20260519_0002_add_auth_audit_actions.py")


def migration_text() -> str:
    return MIGRATION.read_text()


def test_initial_migration_exists_and_creates_core_tables():
    text = migration_text()

    for table_name in (
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
    ):
        assert f'"{table_name}"' in text


def test_migration_contains_dedup_and_filter_indexes():
    text = migration_text()

    for name in (
        "uq_raw_intelligence_raw_hash",
        "uq_raw_intelligence_source_external_id",
        "uq_threat_intelligence_dedup_key",
        "ix_threat_intelligence_cve_id",
        "ix_threat_intelligence_risk_status",
        "ix_threat_intelligence_tags",
        "ix_threat_intelligence_search",
        "ix_alerts_risk_status",
    ):
        assert name in text


def test_migration_uses_postgresql_full_text_and_json_support():
    text = migration_text()

    assert "postgresql.JSONB" in text
    assert "postgresql.TSVECTOR" in text
    assert 'postgresql_using="gin"' in text


def test_migration_contains_required_mvp_intelligence_types():
    text = migration_text()

    for intelligence_type in ("vulnerability", "exposure", "incident", "advisory"):
        assert f'"{intelligence_type}"' in text

    for out_of_scope_type in ("campaign", "threat_actor", "malware"):
        assert f'"{out_of_scope_type}"' not in text


def test_migration_reuses_explicitly_created_enum_types():
    text = migration_text()

    assert text.count('name="source_type"') == 1
    assert text.count('name="processing_status"') == 1
    assert text.count('name="risk_level"') == 1
    assert "create_type=False" in text


def test_auth_audit_action_migration_extends_existing_enum():
    text = AUTH_AUDIT_MIGRATION.read_text()

    assert 'down_revision: str | Sequence[str] | None = "20260519_0001"' in text
    for action in ("login_success", "login_failure", "logout"):
        assert f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'" in text
