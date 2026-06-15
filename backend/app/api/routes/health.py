from collections.abc import Sequence

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.settings import Settings, get_settings
from app.services.connectivity import DependencyProbeResult, Probe, check_postgres, check_redis

router = APIRouter(tags=["health"])


async def get_request_settings(request: Request) -> Settings:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings
    return get_settings()


async def get_readiness_probes() -> Sequence[Probe]:
    return (check_postgres, check_redis)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness(
    response: Response,
    settings: Settings = Depends(get_request_settings),
    probes: Sequence[Probe] = Depends(get_readiness_probes),
) -> dict[str, object]:
    results = [probe(settings) for probe in probes]
    ready = all(result.ready for result in results)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready else "degraded",
        "dependencies": {
            result.name: _dependency_payload(result)
            for result in results
        },
    }


def _dependency_payload(result: DependencyProbeResult) -> dict[str, str]:
    return {
        "status": "ok" if result.ready else "unavailable",
        "detail": result.detail,
    }
