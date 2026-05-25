"""recommendation-api settings (pydantic-settings).

Reads the monorepo root `.env` (running `uvicorn` locally from this directory it
is `../../../.env`) and, if present, the service's local `.env`, which takes
higher priority. In Docker the values come from environment variables (env_file +
the environment block in docker-compose.yml), so missing files are simply ignored.

recommendation-api is a synchronous, READ-ONLY consumer of `recommendationdb`
(pgvector): it ranks `profession_vectors` against `user_vectors[user_id]` by
cosine similarity. The worker owns the schema/migrations; this service never
creates or modifies the tables. Port 8003.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # The last existing file wins: local .env > root .env.
        env_file=("../../../.env", "../../.env", ".env"),
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

    # --- PostgreSQL (recommendationdb in the shared instance; pgvector, READ-ONLY) ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://career:career@localhost:5432/recommendationdb"
    )

    # --- Redis (cache: the first page of a user's recommendations) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    RECO_CACHE_TTL_SECONDS: int = 300  # ~5 minutes

    # --- Scoring / output ---
    # POST /recommendations/scores caps the number of profession_ids per request.
    MAX_SCORE_IDS: int = 200

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
