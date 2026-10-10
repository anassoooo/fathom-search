"""Typed runtime configuration. This module is the only place that reads env vars."""

from functools import lru_cache
from typing import Literal

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
    llm_timeout_s: float = 30.0
    # Offline eval (query generation, relevance judging): a stronger model than serving needs.
    llm_model_eval: str = "llama-3.3-70b-versatile"

    # Models
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    image_model: str = "Qdrant/clip-ViT-B-32-vision"
    clip_text_model: str = "Qdrant/clip-ViT-B-32-text"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    model_cache_dir: str | None = None
    # ONNX Runtime threads per model. Using every core oversubscribes the CPU and was
    # 5-8x slower than 4 threads on a 16-thread laptop; tune per deployment target.
    onnx_threads: int | None = Field(default=4, ge=1)
    # "cuda" needs the GPU build (`uv sync --extra gpu`) and an NVIDIA GPU.
    onnx_device: Literal["cpu", "cuda"] = "cpu"
    rerank_top_n: int = Field(default=30, ge=1, le=200)  # revisit with M2 eval data
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
