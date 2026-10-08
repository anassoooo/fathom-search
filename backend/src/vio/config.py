"""Typed runtime configuration. This module is the only place that reads env vars."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "vio_products_v2"

    # LLM (any OpenAI-compatible endpoint: Groq, Ollama, ...)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: SecretStr = SecretStr("ollama")
    llm_model_query: str = "qwen2.5:3b-instruct"
    llm_model_agent: str = "qwen2.5:3b-instruct"
    llm_timeout_s: float = 10.0

    # Models
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    image_model: str = "Qdrant/clip-ViT-B-32-vision"
    clip_text_model: str = "Qdrant/clip-ViT-B-32-text"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    model_cache_dir: str | None = None
    rerank_top_n: int = Field(default=50, ge=1, le=200)
    rerank_timeout_s: float = 2.0

    # Observability
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    log_level: str = "INFO"

    # API
    cors_origins: list[str] = ["http://localhost:3000"]
    max_image_bytes: int = 5 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
