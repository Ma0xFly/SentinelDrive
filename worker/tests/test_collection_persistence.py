from __future__ import annotations

from dataclasses import dataclass

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
from sentineldrive_worker.persistence.service import run_and_persist_enabled_sources
from sentineldrive_worker.persistence.tables import job_logs, metadata, raw_intelligence, sources, sync_states


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


def test_successful_connector_run_creates_raw_record_job_log_source_and_cursor(session_factory):
    registry = ConnectorRegistry()
    registry.register("successful", SuccessfulConnector)
    source = source_config("successful", connector="successful")

    result = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["persisted"]["raw_created"] == 1
    with session_factory() as session:
        raw = session.execute(select(raw_intelligence)).mappings().one()
        assert raw["source_name"] == "successful"
        assert raw["source_type"] == "api"
        assert raw["source_url"] == "https://example.test/successful/item"
        assert raw["external_id"] == "successful-1"
        assert raw["title"] == "Successful item"
        assert raw["processing_status"] == "collected"
        assert raw["retained_payload_mode"] == "raw_payload"
        assert raw["raw_content"] == {"kind": "test", "source": "successful"}

        job = session.execute(select(job_logs)).mappings().one()
        assert job["status"] == "success"
        assert job["items_seen"] == 1
        assert job["items_created"] == 1
        assert job["items_updated"] == 0

        source_row = session.execute(select(sources)).mappings().one()
        assert source_row["status"] == "enabled"
        assert source_row["last_success_at"] is not None

        sync_state = session.execute(select(sync_states)).mappings().one()
        assert sync_state["cursor"] == "cursor-1"
        assert sync_state["status"] == "success"
        assert sync_state["consecutive_failures"] == 0


def test_failed_connector_run_creates_failure_log_status_and_keeps_cursor(session_factory):
    registry = ConnectorRegistry()
    registry.register("failing", FailingConnector)
    source = source_config("failing", connector="failing", cursor="old-cursor")

    result = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["sources_failed"] == 1
    with session_factory() as session:
        assert session.execute(select(raw_intelligence)).mappings().all() == []
        job = session.execute(select(job_logs)).mappings().one()
        assert job["status"] == "failed"
        assert "source unavailable" in job["error_message"]

        source_row = session.execute(select(sources)).mappings().one()
        assert source_row["status"] == "error"
        assert "source unavailable" in source_row["last_error_message"]

        sync_state = session.execute(select(sync_states)).mappings().one()
        assert sync_state["cursor"] is None
        assert sync_state["status"] == "failed"
        assert sync_state["consecutive_failures"] == 1


def test_existing_failed_cursor_is_not_overwritten_by_failure(session_factory):
    registry = ConnectorRegistry()
    registry.register("successful", SuccessfulConnector)
    registry.register("failing", FailingConnector)
    source = source_config("successful", connector="successful")
    failing_source = source_config("successful", connector="failing")

    run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )
    run_and_persist_enabled_sources(
        source_configs=[failing_source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    with session_factory() as session:
        sync_state = session.execute(select(sync_states)).mappings().one()
        assert sync_state["cursor"] == "cursor-1"
        assert sync_state["status"] == "failed"


def test_skipped_disabled_connector_creates_success_log_without_raw_items(session_factory):
    source = source_config("disabled", enabled=False)

    result = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=ConnectorRegistry(),
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["sources_skipped"] == 1
    with session_factory() as session:
        assert session.execute(select(raw_intelligence)).mappings().all() == []
        source_row = session.execute(select(sources)).mappings().one()
        assert source_row["status"] == "disabled"
        job = session.execute(select(job_logs)).mappings().one()
        assert job["status"] == "success"
        assert job["metadata"]["run_status"] == "skipped"
        assert job["metadata"]["skipped"] is True


def test_retry_metadata_is_recorded_when_connector_eventually_succeeds(session_factory):
    registry = ConnectorRegistry()
    registry.register("flaky", FlakyConnector)
    source = source_config("flaky", connector="flaky", retry_policy=RetryPolicy(attempts=1, backoff_seconds=0))

    result = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["sources_succeeded"] == 1
    with session_factory() as session:
        job = session.execute(select(job_logs)).mappings().one()
        assert job["status"] == "success"
        assert job["metadata"]["attempts"] == 2
        assert job["metadata"]["retried"] is True


def test_one_source_failure_does_not_block_unrelated_success(session_factory):
    registry = ConnectorRegistry()
    registry.register("successful", SuccessfulConnector)
    registry.register("failing", FailingConnector)
    sources_to_run = [
        source_config("ok", connector="successful"),
        source_config("bad", connector="failing"),
    ]

    result = run_and_persist_enabled_sources(
        source_configs=sources_to_run,
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["sources_succeeded"] == 1
    assert result["sources_failed"] == 1
    with session_factory() as session:
        assert len(session.execute(select(job_logs)).mappings().all()) == 2
        assert len(session.execute(select(raw_intelligence)).mappings().all()) == 1
        source_statuses = {
            row["name"]: row["status"]
            for row in session.execute(select(sources.c.name, sources.c.status)).mappings().all()
        }
        assert source_statuses == {"ok": "enabled", "bad": "error"}


def test_one_source_persistence_failure_does_not_hide_unrelated_persisted_source(session_factory):
    registry = ConnectorRegistry()
    registry.register("successful", SuccessfulConnector)
    sources_to_run = [
        source_config("ok", connector="successful"),
        source_config("broken", connector="successful", metadata={"connector": "successful", "bad": object()}),
    ]

    result = run_and_persist_enabled_sources(
        source_configs=sources_to_run,
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert result["sources_succeeded"] == 2
    assert result["persisted"]["raw_created"] == 1
    assert result["persisted"]["failed"] == 1
    failed_record = next(record for record in result["persisted"]["records"] if record["source_name"] == "broken")
    assert failed_record["status"] == "persistence_failed"
    with session_factory() as session:
        assert len(session.execute(select(raw_intelligence)).mappings().all()) == 1
        assert session.execute(select(sources.c.name)).scalars().all() == ["ok"]


def test_html_and_pdf_sources_force_metadata_only_retention(session_factory):
    registry = ConnectorRegistry()
    registry.register("retention", SuccessfulConnector)
    html_source = source_config("html-feed", connector="retention", source_type=SourceType.HTML)
    pdf_source = source_config("pdf-feed", connector="retention", source_type=SourceType.PDF)

    run_and_persist_enabled_sources(
        source_configs=[html_source, pdf_source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    with session_factory() as session:
        rows = session.execute(select(raw_intelligence.c.source_name, raw_intelligence.c.raw_content, raw_intelligence.c.retained_payload_mode, raw_intelligence.c.metadata)).mappings().all()
        assert {row["source_name"] for row in rows} == {"html-feed", "pdf-feed"}
        for row in rows:
            assert row["raw_content"] is None
            assert row["retained_payload_mode"] == "metadata_only"
            assert row["metadata"]["retention_enforced"] == "metadata_only"


def test_reprocessing_same_raw_item_updates_instead_of_creating_duplicate(session_factory):
    registry = ConnectorRegistry()
    registry.register("successful", SuccessfulConnector)
    source = source_config("successful", connector="successful")

    first = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )
    second = run_and_persist_enabled_sources(
        source_configs=[source],
        connector_registry=registry,
        session_factory=session_factory,
        sleeper=lambda seconds: None,
    )

    assert first["persisted"]["raw_created"] == 1
    assert second["persisted"]["raw_updated"] == 1
    with session_factory() as session:
        assert len(session.execute(select(raw_intelligence)).mappings().all()) == 1


@dataclass
class SuccessfulConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        payload = RawIntelligencePayload.from_source(
            self.source,
            source_url=f"{self.source.base_url}/item",
            external_id=f"{self.source.name}-1",
            title="Successful item",
            summary="Collected by a persistence test connector.",
            snippet="test snippet",
            raw_content={"kind": "test", "source": self.source.name},
            metadata={"connector": "successful"},
        )
        return ConnectorResult(items=(payload,), next_cursor="cursor-1", metadata={"batch": "test"})


@dataclass
class FailingConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        raise ConnectorError("source unavailable")


@dataclass
class FlakyConnector:
    source: SourceConfig
    calls: int = 0

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        self.calls += 1
        if self.calls == 1:
            raise ConnectorError("temporary source unavailable")
        payload = RawIntelligencePayload.from_source(
            self.source,
            external_id="flaky-1",
            title="Recovered item",
        )
        return ConnectorResult(items=(payload,), next_cursor="flaky-cursor")
