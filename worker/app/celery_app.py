import os

from celery import Celery

from sentineldrive_worker.connectors.config import load_source_configs

celery_app = Celery(
    "sentineldrive",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/1"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/2"),
    include=["app.tasks"],
)

celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "process-enabled-sources": {
            "task": "sentineldrive.process_pipeline",
            "schedule": load_source_configs()[0].sync_interval_seconds,
        },
    },
)
