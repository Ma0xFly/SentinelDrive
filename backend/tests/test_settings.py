from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_reads_existing_environment_names(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "production-secret-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@postgres:5432/app")
    monkeypatch.setenv("REDIS_URL", "redis://:redis-pass@redis:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://:redis-pass@redis:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://:redis-pass@redis:6379/2")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAIL", "admin@sentineldrive.local")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "production-admin-password")
    monkeypatch.setenv("NVD_API_KEY", "")

    settings = Settings()

    assert settings.app_env == "production"
    assert settings.app_secret_key.get_secret_value() == "production-secret-value"
    assert settings.database_url.get_secret_value().startswith("postgresql+psycopg://")
    assert settings.redis_url.get_secret_value().startswith("redis://")
    assert settings.celery_broker_url.get_secret_value().endswith("/1")
    assert settings.celery_result_backend.get_secret_value().endswith("/2")
    assert settings.nvd_api_key is None
    assert settings.source_enabled_nvd is True
    assert settings.source_sync_interval_seconds == 3600
    assert settings.source_rate_limit_per_minute == 20
    assert settings.source_retry_attempts == 3


def test_secret_values_are_redacted_in_model_dump():
    settings = Settings(
        APP_SECRET_KEY="secret-value",
        DATABASE_URL="postgresql+psycopg://user:pass@postgres:5432/app",
        REDIS_URL="redis://:redis-pass@redis:6379/0",
        CELERY_BROKER_URL="redis://:celery-pass@redis:6379/1",
        CELERY_RESULT_BACKEND="redis://:celery-pass@redis:6379/2",
        ADMIN_BOOTSTRAP_PASSWORD="admin-password",
        NVD_API_KEY="nvd-secret",
    )

    dumped = str(settings.model_dump())

    assert "secret-value" not in dumped
    assert "admin-password" not in dumped
    assert "nvd-secret" not in dumped
    assert "redis-pass" not in dumped
    assert "celery-pass" not in dumped


def test_invalid_readiness_timeout_fails_validation():
    try:
        Settings(READINESS_TIMEOUT_SECONDS="0")
    except ValidationError as exc:
        assert "timeout values must be greater than zero" in str(exc)
    else:
        raise AssertionError("Settings accepted an invalid readiness timeout")


def test_production_rejects_placeholder_secrets():
    try:
        Settings(APP_ENV="production")
    except ValidationError as exc:
        message = str(exc)
        assert "Unsafe production configuration" in message
        assert "APP_SECRET_KEY" in message
        assert "DATABASE_URL" in message
        assert "ADMIN_BOOTSTRAP_EMAIL" in message
        assert "ADMIN_BOOTSTRAP_PASSWORD" in message
        assert "change-me-development-only" not in message
    else:
        raise AssertionError("Settings accepted placeholder production secrets")


def test_source_configuration_validation():
    try:
        Settings(SOURCE_SYNC_INTERVAL_SECONDS="0")
    except ValidationError as exc:
        assert "integer configuration values must be greater than zero" in str(exc)
    else:
        raise AssertionError("Settings accepted an invalid source sync interval")
