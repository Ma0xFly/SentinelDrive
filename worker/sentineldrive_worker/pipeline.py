from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy.orm import Session

from sentineldrive_worker.connectors.contracts import SourceConfig
from sentineldrive_worker.connectors.registry import ConnectorRegistry, registry
from sentineldrive_worker.connectors.runtime import RuntimeState
from sentineldrive_worker.normalization.registry import NormalizerRegistry
from sentineldrive_worker.normalization.registry import registry as normalizer_registry
from sentineldrive_worker.normalization.service import normalize_pending_raw_intelligence
from sentineldrive_worker.persistence.database import create_engine_from_url, create_session_factory
from sentineldrive_worker.persistence.service import run_and_persist_enabled_sources
from sentineldrive_worker.scoring.service import score_pending_threat_intelligence


AlertEvaluator = Callable[[Callable[[], Session], int], dict[str, Any]]


def run_processing_pipeline(
    *,
    source_configs: Iterable[SourceConfig] | None = None,
    connector_registry: ConnectorRegistry = registry,
    state: RuntimeState | None = None,
    sleeper=None,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
    normalizer_registry: NormalizerRegistry = normalizer_registry,
    normalization_limit: int = 500,
    scoring_limit: int = 500,
    alert_limit: int = 100,
    alert_evaluator: AlertEvaluator | None = None,
) -> dict[str, Any]:
    factory = session_factory
    if factory is None:
        engine = create_engine_from_url(database_url)
        factory = create_session_factory(engine)

    stages: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []

    collection = run_stage(
        "collection",
        lambda: run_and_persist_enabled_sources(
            source_configs=source_configs,
            connector_registry=connector_registry,
            state=state,
            sleeper=sleeper,
            session_factory=factory,
            database_url=database_url,
        ),
    )
    stages["collection"] = collection
    extend_stage_errors(errors, "collection", collection)

    normalization = run_stage(
        "normalization",
        lambda: normalize_pending_raw_intelligence(
            limit=normalization_limit,
            session_factory=factory,
            normalizer_registry=normalizer_registry,
        ),
    )
    stages["normalization"] = normalization
    extend_stage_errors(errors, "normalization", normalization)

    scoring = run_stage(
        "scoring",
        lambda: score_pending_threat_intelligence(
            limit=scoring_limit,
            session_factory=factory,
        ),
    )
    stages["scoring"] = scoring
    extend_stage_errors(errors, "scoring", scoring)

    if alert_evaluator is None:
        alerts = {
            "status": "skipped",
            "created": 0,
            "evaluated": 0,
            "reason": "backend_alert_evaluation_not_imported_by_worker",
        }
    else:
        alerts = run_stage("alerts", lambda: alert_evaluator(factory, alert_limit))
        extend_stage_errors(errors, "alerts", alerts)
    stages["alerts"] = alerts

    return {
        "status": "completed" if not fatal_stage_errors(stages) else "completed_with_errors",
        "sources_seen": int(collection.get("sources_seen", 0)),
        "sources_succeeded": int(collection.get("sources_succeeded", 0)),
        "sources_failed": int(collection.get("sources_failed", 0)),
        "sources_skipped": int(collection.get("sources_skipped", 0)),
        "raw_created": int((collection.get("persisted") or {}).get("raw_created", 0)),
        "raw_updated": int((collection.get("persisted") or {}).get("raw_updated", 0)),
        "normalization_rows_seen": int(normalization.get("raw_seen", 0)),
        "normalized": int(normalization.get("normalized", 0)),
        "normalization_failed": int(normalization.get("failed", 0)),
        "scoring_rows_seen": int(scoring.get("rows_seen", 0)),
        "scored": int(scoring.get("scored", 0)),
        "scoring_failed": int(scoring.get("failed", 0)),
        "alert_evaluation_count": int(alerts.get("evaluated", alerts.get("created", 0))),
        "alerts_created": int(alerts.get("created", 0)),
        "stage_failures": errors,
        "stages": stages,
    }


def run_stage(name: str, call: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return call()
    except Exception as exc:
        return {
            "status": "failed",
            "stage": name,
            "error_message": str(exc)[:500],
        }


def extend_stage_errors(errors: list[dict[str, Any]], stage: str, result: dict[str, Any]) -> None:
    if result.get("status") == "failed":
        errors.append({"stage": stage, "error_message": result.get("error_message", "未知阶段失败")})
        return
    if stage == "collection":
        errors.extend(
            {
                "stage": stage,
                "source_name": record.get("source_name"),
                "status": record.get("status"),
                "error_message": record.get("error_message"),
            }
            for record in result.get("records", [])
            if record.get("status") in {"failed", "persistence_failed"}
        )
        errors.extend(
            {
                "stage": "persistence",
                "source_name": record.get("source_name"),
                "status": record.get("status"),
                "error_message": record.get("error_message"),
            }
            for record in (result.get("persisted") or {}).get("records", [])
            if record.get("status") == "persistence_failed"
        )
        return
    if stage == "normalization":
        errors.extend(
            {
                "stage": stage,
                "raw_intelligence_id": record.get("raw_intelligence_id"),
                "error_message": record.get("error_message"),
            }
            for record in result.get("records", [])
            if record.get("status") == "failed"
        )
        return
    if stage == "scoring":
        errors.extend(
            {
                "stage": stage,
                "threat_intelligence_id": record.get("threat_intelligence_id"),
                "error_message": record.get("error_message"),
            }
            for record in result.get("records", [])
            if record.get("status") == "failed"
        )


def fatal_stage_errors(stages: dict[str, dict[str, Any]]) -> bool:
    return any(stage.get("status") == "failed" for stage in stages.values())
