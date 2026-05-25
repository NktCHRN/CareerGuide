"""user-service settings (pydantic-settings).

Reads the monorepo root `.env` (for running `uvicorn` locally from the service
directory this is `../../.env`) and, if present, the service's local `.env`,
which takes higher priority. In Docker the values come from environment
variables (env_file + the environment block in docker-compose.yml), so missing
files are simply ignored.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The last existing file wins: local .env > root .env.
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- General ---
    APP_ENV: str = "dev"  # dev | prod
    AUTH_MODE: str = "local"  # local | gateway
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- JWT (HS256, issued only by user-service) ---
    JWT_SECRET: str = "change-me-dev-secret-rotate-in-prod"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Email tokens (verify / reset) ---
    VERIFY_TOKEN_TTL_HOURS: int = 48
    RESET_TOKEN_TTL_HOURS: int = 1

    # --- PostgreSQL (userdb in the shared instance; exposed on localhost:5432) ---
    DATABASE_URL: str = "postgresql+asyncpg://career:career@localhost:5432/userdb"

    # --- Kafka ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"

    # --- Redis (cache) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    PROFILE_CACHE_TTL_SECONDS: int = 300

    # --- S3 / MinIO ---
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "career-guide"
    S3_REGION: str = "us-east-1"
    RESUME_PRESIGN_TTL_SECONDS: int = 3600

    # --- Email / AWS SES (feature flag, default off) ---
    FEATURE_EMAIL_ENABLED: bool = False
    AWS_SES_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_FROM_EMAIL: str = "no-reply@career-guide.local"

    # Frontend base URL — used to build links in emails.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # --- Seeding of initial accounts (alembic) ---
    SEED_ADMIN_EMAIL: str = "admin@career-guide.local"
    SEED_ADMIN_PASSWORD: str = "admin12345"
    SEED_ADMIN_NAME: str = "Administrator"
    SEED_USER_EMAIL: str = "user@career-guide.local"
    SEED_USER_PASSWORD: str = "user12345"
    SEED_USER_NAME: str = "Test User"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
