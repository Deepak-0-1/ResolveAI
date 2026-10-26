"""Environment-driven configuration. Secrets never hard-coded."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central config loaded from environment / .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ResolveAI"
    app_env: str = "development"
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:8501"

    jwt_secret: str = Field(default="change-me-to-a-long-random-string")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    service_api_key: str = Field(default="dev-service-api-key-change-me")

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "resolveai"
    postgres_password: str = "resolveai"
    postgres_db: str = "resolveai"
    database_url: str = "postgresql+psycopg://resolveai:resolveai@localhost:5432/resolveai"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "resolveai_chunks"

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:3b"
    ollama_embed_model: str = "nomic-embed-text"
    embedding_dimensions: int = 768

    chunk_size: int = 800
    chunk_overlap: int = 120
    upload_dir: str = "data/uploads"

    retrieval_top_k: int = 5
    min_retrieval_score: float = 0.25
    # dense | hybrid (dense + BM25 fused with RRF)
    retrieval_mode: str = "hybrid"
    hybrid_rrf_k: int = 60
    # Comma-separated phrases that force human escalation (M3 policy).
    escalate_keywords: str = (
        "delete workspace,delete account,disable mfa,chargeback,legal hold,ssn,social security"
    )

    llm_timeout_seconds: float = 60.0
    http_timeout_seconds: float = 30.0
    embed_timeout_seconds: float = 120.0

    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20
    http_max_retries: int = 2
    http_retry_backoff_seconds: float = 0.4

    @property
    def escalate_keyword_list(self) -> list[str]:
        return [k.strip().lower() for k in self.escalate_keywords.split(",") if k.strip()]

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    def assert_safe_for_production(self) -> None:
        """Fail fast if insecure defaults are used in production."""
        if not self.is_production:
            return
        weak_secrets = {
            "change-me-to-a-long-random-string",
            "dev-service-api-key-change-me",
        }
        if self.jwt_secret in weak_secrets or len(self.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be a strong unique value in production")
        if self.service_api_key in weak_secrets:
            raise RuntimeError("SERVICE_API_KEY must be changed in production")
        if self.postgres_password in {"resolveai", "postgres", "password"}:
            raise RuntimeError("POSTGRES password must be changed in production")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
