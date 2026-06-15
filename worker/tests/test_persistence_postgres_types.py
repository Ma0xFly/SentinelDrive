from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import insert, update
from sqlalchemy.dialects import postgresql

from sentineldrive_worker.persistence.tables import (
    job_logs,
    raw_intelligence,
    sources,
    sync_states,
    threat_intelligence,
)


@pytest.mark.parametrize(
    ("column", "enum_name"),
    (
        (sources.c.source_type, "source_type"),
        (sources.c.status, "source_status"),
        (sync_states.c.status, "job_status"),
        (job_logs.c.status, "job_status"),
        (raw_intelligence.c.source_type, "source_type"),
        (raw_intelligence.c.parsing_status, "processing_status"),
        (raw_intelligence.c.processing_status, "processing_status"),
        (threat_intelligence.c.intelligence_type, "intelligence_type"),
        (threat_intelligence.c.severity, "severity"),
        (threat_intelligence.c.vehicle_component, "vehicle_component"),
        (threat_intelligence.c.attack_surface, "attack_surface"),
        (threat_intelligence.c.exploit_status, "exploit_status"),
        (threat_intelligence.c.confidence, "confidence_level"),
        (threat_intelligence.c.risk_level, "risk_level"),
        (threat_intelligence.c.processing_status, "processing_status"),
    ),
)
def test_postgresql_enum_columns_match_database_types(column, enum_name):
    column_type = column.type.dialect_impl(postgresql.dialect())

    assert isinstance(column_type, postgresql.ENUM)
    assert column_type.name == enum_name


def test_postgresql_enum_writes_render_bind_casts():
    dialect = postgresql.dialect(paramstyle="numeric")

    source_insert = str(
        insert(sources)
        .values(id=uuid4(), name="nvd", source_type="api", status="enabled", config={})
        .compile(dialect=dialect)
    )
    source_update = str(update(sources).values(source_type="rss", status="error").compile(dialect=dialect))
    now = datetime.now(timezone.utc)
    raw_insert = str(
        insert(raw_intelligence)
        .values(
            id=uuid4(),
            source_name="nvd",
            source_type="api",
            source_url="https://example.test",
            fetched_at=now,
            first_seen_at=now,
            raw_hash="hash",
            parsing_status="pending",
            processing_status="collected",
            metadata={},
            retained_payload_mode="raw_payload",
        )
        .compile(dialect=dialect)
    )

    assert "::source_type" in source_insert
    assert "::source_status" in source_insert
    assert "::source_type" in source_update
    assert "::source_status" in source_update
    assert "::source_type" in raw_insert
    assert "::processing_status" in raw_insert
