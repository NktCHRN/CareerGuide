"""recommendation-worker settings (pydantic-settings).

Reads the monorepo root `.env` (for running locally from the worker directory
this is `../../../.env`) and, if present, the worker's local `.env`, which takes
higher priority. In Docker the values come from environment variables (env_file +
the environment block in docker-compose.yml), so missing files are simply ignored.

The worker is a background Kafka consumer with no public REST API (only
`GET /api/health` on port 8005). It owns the `recommendationdb` migrations
(pgvector); recommendation-api only reads.
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
    HEALTH_PORT: int = 8005

    # --- PostgreSQL (recommendationdb in the shared instance; pgvector enabled) ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://career:career@localhost:5432/recommendationdb"
    )

    # --- Kafka (Message Bus) ---
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:29092"
    # Separate consumer groups, one per consumed topic (idempotent upserts).
    KAFKA_GROUP_PROFESSIONS: str = "reco-worker-professions"
    KAFKA_GROUP_USERS: str = "reco-worker-users"
    # Batch drain window for profession.upserted events (SBERT is batched).
    PROFESSION_BATCH_MAX: int = 64
    PROFESSION_BATCH_TIMEOUT_MS: int = 500

    # --- S3 / MinIO (resume PDFs live here; uploaded by user-service, read here) ---
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "career-guide"
    S3_REGION: str = "us-east-1"

    # --- OpenAI (resume parsing) ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # --- career-SBERT: role/skill/summary/profession embeddings fed to CareerRNN ---
    SBERT_MODEL: str = "ElenaSenger/career-path-representation-mpnet-decorte"

    # --- CareerRNN checkpoint + auxiliary vocab/data (relative to the worker dir) ---
    MODEL_CKPT_PATH: str = "./models/gru-attn-bidirectional-final_seed4.pth"
    INDUSTRY_VOCAB_PATH: str = "./models/industry_to_id.json"
    LIVECAREER_CATEGORIES_PATH: str = "./data/livecareer_resume_categories.csv"

    # --- CareerRNN hyperparameters (must match the checkpoint — do not change) ---
    EMBEDDING_DIM: int = 768
    SKILLS_DIM_IN: int = 768
    MONTHS_DIM: int = 16
    INDUSTRY_DIM: int = 32
    SKILL_DIM: int = 64
    HIDDEN: int = 512
    DROPOUT: float = 0.5

    # --- ESCO skill-mapping (v3): EmbeddingGemma over the full ESCO skill catalogue ---
    ESCO_SKILLS_CSV: str = "./data/skills_en.csv"
    ESCO_SKILL_EMBED_MODEL: str = "google/embeddinggemma-300m"  # gated → HF_TOKEN
    HF_TOKEN: str = ""
    COSINE_THRESHOLD: float = 0.6
    ESCO_EMBED_BATCH_SIZE: int = 64

    # --- Compute ---
    DEVICE: str = "auto"  # auto | cpu | cuda

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV.lower() == "dev"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
