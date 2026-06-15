from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from sentineldrive_worker.connectors.contracts import (
    ConnectorContext,
    ConnectorError,
    ConnectorResult,
    RawIntelligencePayload,
    RetryPolicy,
    SourceConfig,
    SourceType,
)
from sentineldrive_worker.connectors.registry import ConnectorRegistry
from sentineldrive_worker.persistence.tables import metadata, raw_intelligence, threat_intelligence
from sentineldrive_worker.pipeline import run_processing_pipeline


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def source_config(name: str, *, connector: str | None = None, **overrides) -> SourceConfig:
    values = {
        "name": name,
        "source_type": SourceType.API,
        "enabled": True,
        "base_url": f"https://example.test/{name}",
        "sync_interval_seconds": 300,
        "timeout_seconds": 1.0,
        "rate_limit_per_minute": 60,
        "retry_policy": RetryPolicy(attempts=0, backoff_seconds=0),
        "metadata": {"connector": connector or name},
    }
    values.update(overrides)
    return SourceConfig(**values)


def test_processing_pipeline_collects_normalizes_scores_and_reports_alert_skip(session_factory):
    registry = ConnectorRegistry()
    registry.register("fixture-nvd", NvdFixtureConnector)
    source = source_config("nvd", connector="fixture-nvd")

    result = run_processing_pipeline(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["status"] == "completed"
    assert result["sources_seen"] == 1
    assert result["sources_succeeded"] == 1
    assert result["raw_created"] == 1
    assert result["normalized"] == 1
    assert result["scored"] == 1
    assert result["alerts_created"] == 0
    assert result["stages"]["alerts"]["status"] == "skipped"
    with session_factory() as session:
        raw = session.execute(select(raw_intelligence)).mappings().one()
        assert raw["processing_status"] == "normalized"
        intelligence = session.execute(select(threat_intelligence)).mappings().one()
        assert intelligence["dedup_key"] == "cve:CVE-2026-7001"
        assert intelligence["risk_score"] is not None
        assert intelligence["risk_level"] in {"high", "critical"}
        assert intelligence["metadata"]["scoring"]["rule_version"] == "fixed-risk-v1"


def test_processing_pipeline_repeated_run_is_idempotent(session_factory):
    registry = ConnectorRegistry()
    registry.register("fixture-nvd", NvdFixtureConnector)
    source = source_config("nvd", connector="fixture-nvd")

    first = run_processing_pipeline(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )
    second = run_processing_pipeline(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert first["raw_created"] == 1
    assert second["raw_created"] == 0
    assert second["raw_updated"] == 1
    assert second["normalized"] == 1
    assert second["scored"] == 0
    with session_factory() as session:
        assert len(session.execute(select(raw_intelligence)).mappings().all()) == 1
        assert len(session.execute(select(threat_intelligence)).mappings().all()) == 1


def test_processing_pipeline_source_failure_does_not_block_successful_source(session_factory):
    registry = ConnectorRegistry()
    registry.register("fixture-nvd", NvdFixtureConnector)
    registry.register("failing", FailingConnector)
    sources = [
        source_config("nvd", connector="fixture-nvd"),
        source_config("broken", connector="failing"),
    ]

    result = run_processing_pipeline(
        source_configs=sources,
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["status"] == "completed"
    assert result["sources_succeeded"] == 1
    assert result["sources_failed"] == 1
    assert result["raw_created"] == 1
    assert result["normalized"] == 1
    assert result["scored"] == 1
    assert any(failure["stage"] == "collection" and failure["source_name"] == "broken" for failure in result["stage_failures"])
    with session_factory() as session:
        assert len(session.execute(select(raw_intelligence)).mappings().all()) == 1
        assert len(session.execute(select(threat_intelligence)).mappings().all()) == 1


def test_processing_pipeline_no_work_case_is_observable(session_factory):
    disabled_source = source_config("disabled", connector="missing", enabled=False)

    result = run_processing_pipeline(
        source_configs=[disabled_source],
        connector_registry=ConnectorRegistry(),
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["status"] == "completed"
    assert result["sources_seen"] == 1
    assert result["sources_skipped"] == 1
    assert result["raw_created"] == 0
    assert result["normalized"] == 0
    assert result["scored"] == 0
    assert result["alert_evaluation_count"] == 0
    assert result["stage_failures"] == []
    with session_factory() as session:
        assert session.execute(select(raw_intelligence)).mappings().all() == []
        assert session.execute(select(threat_intelligence)).mappings().all() == []


def test_processing_pipeline_uses_injected_alert_evaluator_when_available(session_factory):
    registry = ConnectorRegistry()
    registry.register("fixture-nvd", NvdFixtureConnector)
    source = source_config("nvd", connector="fixture-nvd")

    result = run_processing_pipeline(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
        alert_evaluator=lambda factory, limit: {"status": "completed", "evaluated": limit, "created": 2},
        alert_limit=25,
    )

    assert result["alert_evaluation_count"] == 25
    assert result["alerts_created"] == 2
    assert result["stages"]["alerts"]["status"] == "completed"


@dataclass
class NvdFixtureConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        first_seen = datetime(2026, 5, 20, tzinfo=timezone.utc)
        payload = RawIntelligencePayload.from_source(
            self.source,
            source_url="https://nvd.nist.gov/vuln/detail/CVE-2026-7001",
            external_id="CVE-2026-7001",
            title="CVE-2026-7001 - T-Box remote overflow",
            summary="Remote unauthenticated T-Box firmware overflow.",
            raw_content={
                "cve": {
                    "id": "CVE-2026-7001",
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
            fetched_at=first_seen,
            first_seen_at=first_seen,
            metadata={
                "cvss": {
                    "base_score": 9.8,
                    "base_severity": "CRITICAL",
                    "vector_string": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                },
                "cwe": ["CWE-120"],
                "vuln_status": "Analyzed",
            },
        )
        return ConnectorResult(items=(payload,), next_cursor="fixture-cursor")


@dataclass
class FailingConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        raise ConnectorError("fixture source unavailable")
