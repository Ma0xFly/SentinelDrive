import pytest
from httpx import ASGITransport, AsyncClient

from app.api.routes.health import get_readiness_probes
from app.core.settings import Settings
from app.main import create_app
from app.services.connectivity import DependencyProbeResult


def make_app(probes):
    app = create_app(settings=Settings())

    async def override_readiness_probes():
        return tuple(probes)

    app.dependency_overrides[get_readiness_probes] = override_readiness_probes
    return app


def passing_probe(settings):
    return DependencyProbeResult(name="postgres", ready=True, detail="ok")


def failing_probe(settings):
    return DependencyProbeResult(name="redis", ready=False, detail="unreachable")


@pytest.mark.anyio
async def test_health_reports_process_liveness_without_dependency_probes():
    app = make_app([failing_probe])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readiness_reports_ready_when_all_dependencies_pass():
    app = make_app([passing_probe])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {
            "postgres": {
                "status": "ok",
                "detail": "ok",
            },
        },
    }


@pytest.mark.anyio
async def test_readiness_reports_degraded_when_dependency_fails_without_secrets():
    app = make_app([passing_probe, failing_probe])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["dependencies"]["redis"] == {
        "status": "unavailable",
        "detail": "unreachable",
    }
    assert "change-me-development-only" not in response.text
    assert "redis://redis" not in response.text
