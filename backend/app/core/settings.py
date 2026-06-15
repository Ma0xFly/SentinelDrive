from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_ENVS = {"production", "prod", "staging"}
UNSAFE_PLACEHOLDER_MARKERS = ("change-me", "example.test")


def _secret_value(value: SecretStr) -> str:
    return value.get_secret_value().strip()


def _is_unsafe_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or any(marker in normalized for marker in UNSAFE_PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    app_secret_key: SecretStr = Field(
        default=SecretStr("change-me-development-only"),
        validation_alias="APP_SECRET_KEY",
    )
    database_url: SecretStr = Field(
        default=SecretStr(
            "postgresql+psycopg://sentineldrive:change-me-development-only@postgres:5432/sentineldrive"
        ),
        validation_alias="DATABASE_URL",
    )
    redis_url: SecretStr = Field(
        default=SecretStr("redis://redis:6379/0"),
        validation_alias="REDIS_URL",
    )
    celery_broker_url: SecretStr = Field(
        default=SecretStr("redis://redis:6379/1"),
        validation_alias="CELERY_BROKER_URL",
    )
    celery_result_backend: SecretStr = Field(
        default=SecretStr("redis://redis:6379/2"),
        validation_alias="CELERY_RESULT_BACKEND",
    )
    admin_bootstrap_email: str = Field(
        default="admin@example.test",
        validation_alias="ADMIN_BOOTSTRAP_EMAIL",
    )
    admin_bootstrap_password: SecretStr = Field(
        default=SecretStr("change-me-development-only"),
        validation_alias="ADMIN_BOOTSTRAP_PASSWORD",
    )
    nvd_api_key: SecretStr | None = Field(default=None, validation_alias="NVD_API_KEY")
    source_enabled_nvd: bool = Field(default=True, validation_alias="SOURCE_ENABLED_NVD")
    source_enabled_cisa_kev: bool = Field(default=True, validation_alias="SOURCE_ENABLED_CISA_KEV")
    source_enabled_vendor_advisories: bool = Field(
        default=False,
        validation_alias="SOURCE_ENABLED_VENDOR_ADVISORIES",
    )
    source_enabled_rss: bool = Field(default=True, validation_alias="SOURCE_ENABLED_RSS")
    source_sync_interval_seconds: int = Field(default=3600, validation_alias="SOURCE_SYNC_INTERVAL_SECONDS")
    source_timeout_seconds: float = Field(default=20.0, validation_alias="SOURCE_TIMEOUT_SECONDS")
    source_rate_limit_per_minute: int = Field(default=20, validation_alias="SOURCE_RATE_LIMIT_PER_MINUTE")
    source_retry_attempts: int = Field(default=3, validation_alias="SOURCE_RETRY_ATTEMPTS")
    readiness_timeout_seconds: float = Field(default=2.0, validation_alias="READINESS_TIMEOUT_SECONDS")
    raw_retention_days: int = Field(default=90, validation_alias="RAW_RETENTION_DAYS")
    html_retention_mode: Literal["metadata_only"] = Field(
        default="metadata_only",
        validation_alias="HTML_RETENTION_MODE",
    )
    pdf_retention_mode: Literal["metadata_only"] = Field(
        default="metadata_only",
        validation_alias="PDF_RETENTION_MODE",
    )

    @field_validator("nvd_api_key", mode="before")
    @classmethod
    def empty_secret_is_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("readiness_timeout_seconds", "source_timeout_seconds")
    @classmethod
    def timeout_must_be_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeout values must be greater than zero")
        return value

    @field_validator("raw_retention_days", "source_sync_interval_seconds", "source_rate_limit_per_minute")
    @classmethod
    def positive_integer_settings_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("integer configuration values must be greater than zero")
        return value

    @field_validator("source_retry_attempts")
    @classmethod
    def retry_attempts_must_not_be_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SOURCE_RETRY_ATTEMPTS must be zero or greater")
        return value

    @model_validator(mode="after")
    def production_secrets_must_not_use_placeholders(self) -> "Settings":
        if self.app_env.strip().lower() not in PRODUCTION_ENVS:
            return self

        unsafe_variables: list[str] = []
        secret_checks = {
            "APP_SECRET_KEY": self.app_secret_key,
            "DATABASE_URL": self.database_url,
            "ADMIN_BOOTSTRAP_PASSWORD": self.admin_bootstrap_password,
        }
        for variable_name, secret in secret_checks.items():
            if _is_unsafe_placeholder(_secret_value(secret)):
                unsafe_variables.append(variable_name)

        if _is_unsafe_placeholder(self.admin_bootstrap_email):
            unsafe_variables.append("ADMIN_BOOTSTRAP_EMAIL")

        if unsafe_variables:
            joined_names = ", ".join(sorted(unsafe_variables))
            raise ValueError(f"Unsafe production configuration: replace placeholder values for {joined_names}")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
