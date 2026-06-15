from app.celery_app import celery_app
from sentineldrive_worker.connectors.runtime import run_enabled_sources
from sentineldrive_worker.normalization.service import normalize_pending_raw_intelligence
from sentineldrive_worker.pipeline import run_processing_pipeline
from sentineldrive_worker.persistence.service import persistence_enabled, run_and_persist_enabled_sources
from sentineldrive_worker.scoring.service import score_pending_threat_intelligence


@celery_app.task(name="sentineldrive.sync_sources")
def sync_sources() -> dict[str, object]:
    if persistence_enabled():
        return run_and_persist_enabled_sources()
    return run_enabled_sources()


@celery_app.task(name="sentineldrive.normalize_raw_intelligence")
def normalize_raw_intelligence(limit: int = 100) -> dict[str, object]:
    return normalize_pending_raw_intelligence(limit=limit)


@celery_app.task(name="sentineldrive.score_threat_intelligence")
def score_threat_intelligence(limit: int = 100, force: bool = False) -> dict[str, object]:
    return score_pending_threat_intelligence(limit=limit, force=force)


@celery_app.task(name="sentineldrive.process_pipeline")
def process_pipeline(
    normalization_limit: int = 100,
    scoring_limit: int = 100,
    alert_limit: int = 100,
) -> dict[str, object]:
    return run_processing_pipeline(
        normalization_limit=normalization_limit,
        scoring_limit=scoring_limit,
        alert_limit=alert_limit,
    )
