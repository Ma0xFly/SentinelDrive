from __future__ import annotations

import time
from dataclasses import dataclass

from sentineldrive_worker.connectors.config import SourceConfigRow, load_source_configs
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
from sentineldrive_worker.connectors.runtime import RuntimeState, run_connector, run_enabled_sources
from sentineldrive_worker.connectors.runtime import assert_json_serializable
from sentineldrive_worker.connectors.samples import SampleConnector


def source_config(name: str = "sample", **overrides) -> SourceConfig:
    values = {
        "name": name,
        "source_type": SourceType.API,
        "enabled": True,
        "base_url": f"sentineldrive://{name}",
        "sync_interval_seconds": 3600,
        "timeout_seconds": 1.0,
        "rate_limit_per_minute": 60,
        "retry_policy": RetryPolicy(attempts=0, backoff_seconds=0),
        "metadata": {"connector": name},
    }
    values.update(overrides)
    return SourceConfig(**values)


def test_sample_connector_runs_through_worker_path_and_emits_raw_shape():
    registry = ConnectorRegistry()
    state = RuntimeState()
    result = run_enabled_sources(
        source_configs=[source_config(metadata={"connector": "sample"})],
        connector_registry=registry,
        state=state,
        sleeper=lambda seconds: None,
    )

    assert result["status"] == "completed"
    assert result["sources_succeeded"] == 1
    assert result["items_seen"] == 1
    record = result["records"][0]
    raw_item = record["raw_items"][0]
    assert raw_item["source_name"] == "sample"
    assert raw_item["source_type"] == "api"
    assert raw_item["source_url"] == "sentineldrive://sample"
    assert raw_item["raw_hash"]
    assert raw_item["processing_status"] == "collected"
    assert_json_serializable(result)
    assert state.cursors["sample"] == "1"


def test_disabled_sources_are_skipped():
    registry = ConnectorRegistry()
    result = run_enabled_sources(
        source_configs=[source_config(enabled=False)],
        connector_registry=registry,
        sleeper=lambda seconds: None,
    )

    assert result["sources_skipped"] == 1
    assert result["items_seen"] == 0
    assert result["records"][0]["status"] == "skipped"
    assert result["records"][0]["metadata"]["reason"] == "disabled"


def test_configured_sources_without_implemented_connectors_are_skipped_not_failed():
    registry = ConnectorRegistry()
    result = run_enabled_sources(
        source_configs=[
            source_config(
                "unimplemented",
                source_type=SourceType.RSS,
                metadata={"connector": "missing-source"},
            )
        ],
        connector_registry=registry,
        sleeper=lambda seconds: None,
    )

    assert result["sources_failed"] == 0
    assert result["sources_skipped"] == 1
    assert result["records"][0]["metadata"] == {
        "reason": "connector_not_registered",
        "connector": "missing-source",
    }


def test_incremental_cursor_is_passed_to_connector_and_updated():
    state = RuntimeState(cursors={"sample": "4"})
    record = run_connector(SampleConnector(source_config()), state=state, sleeper=lambda seconds: None)

    assert record.status == "success"
    assert record.next_cursor == "5"
    assert state.cursors["sample"] == "5"
    assert record.raw_items[0]["external_id"] == "sample-5"


def test_retry_records_attempt_count_and_eventual_success():
    connector = FlakyConnector(source_config("flaky", retry_policy=RetryPolicy(attempts=2, backoff_seconds=0)))
    state = RuntimeState()

    record = run_connector(connector, state=state, sleeper=lambda seconds: None)

    assert record.status == "success"
    assert record.attempts == 2
    assert state.errors == {}


def test_retry_exhaustion_records_error_state_without_raising():
    connector = AlwaysFailConnector(source_config("failing", retry_policy=RetryPolicy(attempts=1, backoff_seconds=0)))
    state = RuntimeState()

    record = run_connector(connector, state=state, sleeper=lambda seconds: None)

    assert record.status == "failed"
    assert record.attempts == 2
    assert "temporary source failure" in record.error_message
    assert "temporary source failure" in state.errors["failing"]


def test_timeout_records_error_state_without_blocking_platform():
    connector = SlowConnector(source_config("slow", timeout_seconds=0.01))
    state = RuntimeState()

    record = run_connector(connector, state=state, sleeper=lambda seconds: None)

    assert record.status == "failed"
    assert "timed out" in record.error_message
    assert "timed out" in state.errors["slow"]


def test_rate_limit_wait_is_applied_before_collection():
    waits: list[float] = []
    state = RuntimeState(next_allowed_at={"sample": time.monotonic() + 10})

    record = run_connector(SampleConnector(source_config()), state=state, sleeper=waits.append)

    assert record.status == "success"
    assert waits
    assert waits[0] > 0


def test_database_backed_source_configuration_can_override_defaults():
    configs = load_source_configs(
        env={
            "SOURCE_SYNC_INTERVAL_SECONDS": "900",
            "SOURCE_TIMEOUT_SECONDS": "10",
            "SOURCE_RATE_LIMIT_PER_MINUTE": "12",
            "SOURCE_RETRY_ATTEMPTS": "1",
        },
        db_sources=[
            SourceConfigRow(
                name="vendor-feed",
                source_type="rss",
                base_url="https://example.test/feed.xml",
                status="enabled",
                cursor="abc",
                config={
                    "connector": "rss",
                    "sync_interval_seconds": 1800,
                    "timeout_seconds": 5,
                    "rate_limit_per_minute": 3,
                    "retry_attempts": 2,
                    "headers": {"User-Agent": "SentinelDrive"},
                },
            )
        ],
    )

    db_config = next(config for config in configs if config.name == "vendor-feed")
    assert db_config.enabled is True
    assert db_config.source_type == SourceType.RSS
    assert db_config.cursor == "abc"
    assert db_config.sync_interval_seconds == 1800
    assert db_config.timeout_seconds == 5
    assert db_config.rate_limit_per_minute == 3
    assert db_config.retry_policy.attempts == 2
    assert db_config.headers["User-Agent"] == "SentinelDrive"


def test_database_backed_source_configuration_parses_disabled_string():
    configs = load_source_configs(
        env={},
        db_sources=[
            SourceConfigRow(
                name="vendor-feed",
                source_type="rss",
                status="enabled",
                config={"enabled": "false"},
            )
        ],
    )

    db_config = next(config for config in configs if config.name == "vendor-feed")
    assert db_config.enabled is False


@dataclass
class FlakyConnector:
    source: SourceConfig
    calls: int = 0

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        self.calls += 1
        if self.calls == 1:
            raise ConnectorError("temporary source failure")
        return ConnectorResult(
            items=(
                RawIntelligencePayload.from_source(
                    context.source,
                    external_id="flaky-ok",
                    title="Recovered item",
                ),
            ),
            next_cursor="ok",
        )


@dataclass
class AlwaysFailConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        raise ConnectorError("temporary source failure")


@dataclass
class SlowConnector:
    source: SourceConfig

    def collect(self, context: ConnectorContext) -> ConnectorResult:
        time.sleep(0.05)
        return ConnectorResult()
