"""api-gateway settings (pydantic-settings).

Reads the monorepo root `.env` (for running `uvicorn` locally from the service
directory this is `../../.env`) and, if present, the service's local `.env`,
which takes higher priority. In Docker the values come from environment
variables (env_file + the environment block in docker-compose.yml), so missing
files are simply ignored.

The gateway is stateless: no database, no Kafka. It only needs the shared JWT
secret (to validate access tokens) and the URLs of the downstream services it
proxies to.
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
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- JWT (HS256; tokens are issued only by user-service, validated here) ---
    JWT_SECRET: str = "change-me-dev-secret-rotate-in-prod"
    JWT_ALG: str = "HS256"

    # --- Downstream services (internal docker names in compose / K8s; localhost ports for dev) ---
    USER_SERVICE_URL: str = "http://localhost:8001"
    CAREER_SERVICE_URL: str = "http://localhost:8002"
    RECO_API_URL: str = "http://localhost:8003"
    CHAT_SERVICE_URL: str = "http://localhost:8004"

    # --- Reverse-proxy behaviour ---
    # Connect timeout is short (fail fast → 502); the overall read/write timeout is
    # generous because some downstream calls are slow (e.g. the chat assistant calls an LLM).
    PROXY_CONNECT_TIMEOUT_SECONDS: float = 5.0
    PROXY_TIMEOUT_SECONDS: float = 60.0
    # Retries for IDEMPOTENT requests (GET/HEAD) on connection-level failures only.
    PROXY_RETRIES: int = 1

    # --- Optional: additionally verify the token via user-service ---
    # When true, after validating the JWT locally the gateway calls
    # `GET {USER_SERVICE_URL}/api/profile/me` to confirm the user still exists /
    # is active (catches revoked or deleted accounts whose token has not expired).
    # Default false — local validation is sufficient for the prototype.
    GATEWAY_VERIFY_VIA_USER_SERVICE: bool = False

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
