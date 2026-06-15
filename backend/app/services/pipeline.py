from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.settings import Settings

PROCESS_PIPELINE_TASK = "sentineldrive.process_pipeline"


@dataclass(frozen=True)
class EnqueuedPipelineTask:
    task_id: str
    task_name: str
    status: str


class PipelineTaskClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    def enqueue_process_pipeline(self, *, normalization_limit: int, scoring_limit: int, alert_limit: int) -> EnqueuedPipelineTask:
        celery = self._celery()
        result = celery.send_task(
            PROCESS_PIPELINE_TASK,
            kwargs={
                "normalization_limit": normalization_limit,
                "scoring_limit": scoring_limit,
                "alert_limit": alert_limit,
            },
        )
        return EnqueuedPipelineTask(task_id=str(result.id), task_name=PROCESS_PIPELINE_TASK, status=_task_status(result))

    def task_status(self, task_id: str) -> str | None:
        if not task_id:
            return None
        result = self._celery().AsyncResult(task_id)
        return _task_status(result)

    def _celery(self):
        try:
            from celery import Celery
        except ImportError as exc:
            raise RuntimeError("Celery client support is not installed for backend") from exc

        return Celery(
            "sentineldrive-backend",
            broker=self._settings.celery_broker_url.get_secret_value(),
            backend=self._settings.celery_result_backend.get_secret_value(),
        )


def _task_status(result: Any) -> str:
    status = getattr(result, "status", None) or getattr(result, "state", None)
    return str(status or "queued").lower()
