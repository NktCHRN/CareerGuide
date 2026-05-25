"""Налаштування user-service (pydantic-settings).

Читає кореневий монорепо-`.env` (для локального запуску `uvicorn` з каталогу
сервіса це `../../.env`) і, за наявності, локальний `.env` сервіса, який має
вищий пріоритет. У Docker значення приходять зі змінних оточення (env_file +
блок environment у docker-compose.yml), тож відсутні файли просто ігноруються.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Останній існуючий файл має пріоритет: локальний .env > кореневий .env.
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Загальні ---
    APP_ENV: str = "dev"  # dev | prod
    AUTH_MODE: str = "local"  # local | gateway
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- JWT (HS256, видає лише user-service) ---
    JWT_SECRET: str = "change-me-dev-secret-rotate-in-prod"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Email-токени (verify / reset) ---
    VERIFY_TOKEN_TTL_HOURS: int = 48
    RESET_TOKEN_TTL_HOURS: int = 1

    # --- PostgreSQL (userdb) ---
    DATABASE_URL: str = "postgresql+asyncpg://career:career@localhost:5433/userdb"

    # --- Kafka ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"

    # --- Redis (кеш) ---
    REDIS_URL: str = "redis://localhost:6379/0"
    PROFILE_CACHE_TTL_SECONDS: int = 300

    # --- S3 / MinIO ---
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "career-guide"
    S3_REGION: str = "us-east-1"
    RESUME_PRESIGN_TTL_SECONDS: int = 3600

    # --- Email / AWS SES (фіче-флаг, default off) ---
    FEATURE_EMAIL_ENABLED: bool = False
    AWS_SES_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_FROM_EMAIL: str = "no-reply@career-guide.local"

    # Базовий URL фронта — для побудови посилань у листах.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # --- Сідинг початкових акаунтів (alembic) ---
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
