"""career-service settings (pydantic-settings).

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

    # --- JWT (HS256; tokens are issued only by user-service, validated here in local mode) ---
    JWT_SECRET: str = "change-me-dev-secret-rotate-in-prod"
    JWT_ALG: str = "HS256"

    # --- PostgreSQL (careerdb in the shared instance; exposed on localhost:5432) ---
    DATABASE_URL: str = "postgresql+asyncpg://career:career@localhost:5432/careerdb"

    # --- Kafka ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"

    # --- Redis (cache) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    PROFESSION_CACHE_TTL_SECONDS: int = 600  # ~10 minutes

    # --- S3 / MinIO ---
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "career-guide"
    S3_REGION: str = "us-east-1"
    PHOTO_PRESIGN_TTL_SECONDS: int = 3600  # ~1 hour

    # --- ESCO seeding (Alembic data migration reads the CSVs from this directory) ---
    ESCO_DATA_DIR: str = "./data/esco"

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
