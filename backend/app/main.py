from fastapi import FastAPI

from app.api.routes.alerts import router as alerts_router
from app.api.routes.auth import router as auth_router
from app.api.routes.exports import router as exports_router
from app.api.routes.health import router as health_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.manual_entries import router as manual_entries_router
from app.api.routes.sources import router as sources_router
from app.api.routes.stats import router as stats_router
from app.api.routes.users import router as users_router
from app.core.errors import install_exception_handlers
from app.core.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or get_settings()
    app = FastAPI(
        title="SentinelDrive API",
        version="0.1.0",
        docs_url="/docs" if app_settings.app_env != "production" else None,
        redoc_url=None,
    )
    app.state.settings = app_settings
    install_exception_handlers(app)
    app.include_router(alerts_router)
    app.include_router(auth_router)
    app.include_router(exports_router)
    app.include_router(health_router)
    app.include_router(intelligence_router)
    app.include_router(manual_entries_router)
    app.include_router(sources_router)
    app.include_router(stats_router)
    app.include_router(users_router)
    return app


app = create_app()
