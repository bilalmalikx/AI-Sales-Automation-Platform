import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("SETTINGS_ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "AI Sales Automation Platform"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ── Server ───────────────────────────────────────────────────────────────
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ── Security ─────────────────────────────────────────────────────────────
    # MUST be overridden in staging/production with a 64-char random string.
    SECRET_KEY: str = "change-me-in-production-use-a-64-char-random-secret-key!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # ── CORS ─────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:4200", "http://localhost:4202"]

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/salesautomation"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_MAX_RETRIES: int = 3

    # ── LLM ─────────────────────────────────────────────────────────────────
    OPENAI_API_KEY: str = Field("", validation_alias=AliasChoices("OPENAI_API_KEY", "GROQ_API_KEY"))
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = Field("gpt-4o", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"))
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_RETRIES: int = 3

    # ── Email Providers ──────────────────────────────────────────────────────
    EMAIL_PROVIDER: Literal["local", "smtp"] = "local"
    SENDGRID_API_KEY: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    DEFAULT_FROM_EMAIL: str = Field(
        "", validation_alias=AliasChoices("DEFAULT_FROM_EMAIL", "SMTP_FROM")
    )
    DEFAULT_FROM_NAME: str = ""

    # ── Agent Settings ───────────────────────────────────────────────────────
    AGENT_DEFAULT_TIMEOUT_SECONDS: int = 120
    AGENT_MAX_RETRIES: int = 3
    AGENT_CONFIDENCE_THRESHOLD: float = 0.7

    # ── Observability ────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "console"

    LOCAL_MAIL_DIR: str = "var/mailbox"
    API_TOKEN: str = ""
    AI_PROVIDER: Literal["local", "openai"] = "local"
    CALENDAR_PROVIDER: Literal["local", "google"] = "local"
    LIVE_DELIVERY_ENABLED: bool = False
    SMTP_TLS: Literal["starttls", "ssl", "none"] = Field(
        "starttls", validation_alias=AliasChoices("SMTP_TLS", "SMTP_SECURITY")
    )
    SMTP_TIMEOUT_SECONDS: int = 30
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REFRESH_TOKEN: str = ""
    GOOGLE_CALENDAR_ID: str = "primary"
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    WEBHOOK_SECRET: str = ""
    WORKER_MODE: Literal["inline", "celery", "manual"] = "inline"
    WORKER_POLL_SECONDS: float = Field(2.0, ge=0.1)
    WORKER_MAX_ATTEMPTS: int = Field(3, ge=1, le=10)
    JOB_LEASE_SECONDS: int = Field(600, ge=60)
    MAX_CSV_BYTES: int = 2_000_000
    MAX_CSV_ROWS: int = 5000

    APIFY_API_TOKEN: str = ""
    APIFY_DATASET_ID: str = ""
    APIFY_ACTOR_ID: str = "compass/crawler-google-places"
    DISCOVERY_DAILY_LIMIT: int = Field(100, ge=1, le=1000)
    DISCOVERY_RUN_BUDGET_USD: float = Field(0.5, gt=0, le=5)
    DISCOVERY_AI_MAX_CALLS: int = Field(20, ge=0, le=100)
    WEBSITE_MAX_PAGES: int = Field(4, ge=1, le=8)
    WEBSITE_TIMEOUT_SECONDS: int = Field(12, ge=3, le=30)
    SEARCH_API_KEY: str = ""

    @field_validator("APIFY_DATASET_ID")
    @classmethod
    def dataset_identifier(cls, value):
        # Accept a copied dataset API/console URL; never retain query-string tokens.
        if value.startswith("http"):
            import re
            from urllib.parse import urlsplit

            match = re.search(r"/datasets/([^/]+)", urlsplit(value).path)
            return match.group(1) if match else ""
        return value.strip()

    @model_validator(mode="after")
    def validate_production(self):
        if self.is_production:
            if self.SECRET_KEY.startswith("change-me") or len(self.SECRET_KEY) < 32:
                raise ValueError("Production requires a strong SECRET_KEY")
            if len(self.API_TOKEN) < 32:
                raise ValueError("Production requires an API_TOKEN of at least 32 characters")
            if self.WORKER_MODE != "celery" or not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL and WORKER_MODE=celery")
            if not self.PUBLIC_BASE_URL.startswith("https://"):
                raise ValueError("Production PUBLIC_BASE_URL must use HTTPS")
        if self.EMAIL_PROVIDER == "smtp" and self.LIVE_DELIVERY_ENABLED:
            if not self.SMTP_HOST or not self.DEFAULT_FROM_EMAIL:
                raise ValueError("SMTP requires SMTP_HOST and DEFAULT_FROM_EMAIL")
            if self.is_production and self.SMTP_TLS == "none":
                raise ValueError("Production SMTP must use TLS")
        if self.CALENDAR_PROVIDER == "google" and self.LIVE_DELIVERY_ENABLED:
            if not all(
                [self.GOOGLE_CLIENT_ID, self.GOOGLE_CLIENT_SECRET, self.GOOGLE_REFRESH_TOKEN]
            ):
                raise ValueError(
                    "Google Calendar requires OAuth client credentials and refresh token"
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
