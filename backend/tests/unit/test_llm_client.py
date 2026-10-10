from pathlib import Path

import pytest
from pydantic import BaseModel

from vio.llm.client import ChatResult, LLMClient, LLMError, Message, RateLimitedError


class Answer(BaseModel):
    label: str
    score: int


class Scripted:
    """Fake chat endpoint returning (or raising) a scripted sequence."""

    def __init__(self, *outputs: str | Exception) -> None:
        self.outputs = list(outputs)
        self.calls: list[list[Message]] = []

    def __call__(
        self, model: str, messages: list[Message], temperature: float, json_mode: bool
    ) -> ChatResult:
        self.calls.append(messages)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return ChatResult(out, prompt_tokens=10, completion_tokens=5)


MSG: list[Message] = [{"role": "user", "content": "classify"}]


def _client(fake: Scripted, tmp_path: Path | None = None) -> LLMClient:
    return LLMClient(
        fake, cache_path=tmp_path / "c.sqlite" if tmp_path else None, sleep=lambda s: None
    )


def test_valid_json_is_parsed() -> None:
    c = _client(Scripted('{"label": "shoe", "score": 2}'))
    assert c.structured(MSG, Answer, model="m") == Answer(label="shoe", score=2)
    assert c.usage.calls == 1 and c.usage.prompt_tokens == 10


def test_invalid_output_is_repaired() -> None:
    fake = Scripted('{"label": "shoe"}', '{"label": "shoe", "score": 1}')
    c = _client(fake)
    assert c.structured(MSG, Answer, model="m").score == 1
    assert c.usage.repairs == 1
    assert "did not match" in fake.calls[1][-1]["content"]  # errors fed back to the model


def test_gives_up_after_repairs() -> None:
    c = _client(Scripted("nope", "still nope", "never"))
    with pytest.raises(LLMError, match="invalid Answer"):
        c.structured(MSG, Answer, model="m", repairs=2)


def test_rate_limit_waits_then_succeeds() -> None:
    waits: list[float] = []
    fake = Scripted(RateLimitedError(7.0), RateLimitedError(None), '{"label": "x", "score": 0}')
    c = LLMClient(fake, sleep=waits.append)
    assert c.structured(MSG, Answer, model="m").label == "x"
    assert waits == [7.0, 4.0]  # honors Retry-After, then exponential backoff


def test_persistent_failure_raises() -> None:
    c = LLMClient(Scripted(*[LLMError("down")] * 3), max_attempts=3, sleep=lambda s: None)
    with pytest.raises(LLMError, match="gave up"):
        c.structured(MSG, Answer, model="m")


def test_disk_cache_survives_restarts(tmp_path: Path) -> None:
    first = _client(Scripted('{"label": "a", "score": 1}'), tmp_path)
    first.structured(MSG, Answer, model="m")
    second = _client(Scripted(), tmp_path)  # would fail if it called the endpoint
    assert second.structured(MSG, Answer, model="m").label == "a"
    assert second.usage.cache_hits == 1 and second.usage.calls == 0


def test_daily_quota_stops_immediately() -> None:
    from vio.llm.client import QuotaExhaustedError

    waits: list[float] = []
    c = LLMClient(Scripted(RateLimitedError(367.0, "tokens per day (TPD)")), sleep=waits.append)
    with pytest.raises(QuotaExhaustedError, match="retry in ~6 min"):
        c.structured(MSG, Answer, model="m")
    assert waits == []  # no pointless retries
