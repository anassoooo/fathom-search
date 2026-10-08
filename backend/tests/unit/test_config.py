import pytest

from vio.config import Settings


def test_defaults_point_at_local_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QDRANT_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.rerank_top_n == 50


def test_env_overrides_and_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://example.qdrant.io")
    monkeypatch.setenv("LLM_API_KEY", "super-secret")
    settings = Settings(_env_file=None)
    assert settings.qdrant_url == "https://example.qdrant.io"
    assert settings.llm_api_key.get_secret_value() == "super-secret"
    assert "super-secret" not in settings.model_dump_json()
