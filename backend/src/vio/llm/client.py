"""OpenAI-compatible chat client with validated JSON output, retries, and a disk cache.

Works against Groq, Ollama, or any OpenAI-compatible endpoint (Constitution Art. IV).
LLM output is untrusted (Art. V): every response is parsed into a Pydantic model, and
invalid output gets bounded repair attempts before the call fails.

The SQLite cache keys on (model, temperature, messages). Free-tier daily token limits
are tight, so eval runs resume across days without re-paying for finished calls, and
re-running an eval is deterministic.
"""

import hashlib
import json
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from vio.config import Settings

log = logging.getLogger(__name__)

Message = dict[str, str]


@dataclass
class ChatResult:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


# (model, messages, temperature, json_mode) -> ChatResult. Injected so tests need no network.
ChatFn = Callable[[str, list[Message], float, bool], ChatResult]


class LLMError(RuntimeError):
    pass


class RateLimitedError(LLMError):
    def __init__(self, retry_after: float | None, message: str = "") -> None:
        super().__init__(message or f"rate limited (retry after {retry_after}s)")
        self.retry_after = retry_after


class QuotaExhaustedError(LLMError):
    """A long-window quota (e.g. tokens per day) is used up: retrying now is pointless.
    Finished calls are cached, so re-running later resumes where this stopped."""


# Waits longer than this mean a daily-style quota, not a per-minute one: stop cleanly.
MAX_RATE_LIMIT_WAIT_S = 120.0


@dataclass
class Usage:
    calls: int = 0
    cache_hits: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    repairs: int = 0
    by_model: dict[str, int] = field(default_factory=dict)


def openai_chat_fn(settings: Settings) -> ChatFn:
    import openai

    client = openai.OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        max_retries=0,  # retries are ours, so 429 handling is explicit
    )

    def chat(
        model: str, messages: list[Message], temperature: float, json_mode: bool
    ) -> ChatResult:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object" if json_mode else "text"},
        }
        if settings.llm_reasoning_effort:
            kwargs["reasoning_effort"] = settings.llm_reasoning_effort
        try:
            resp = client.chat.completions.create(**kwargs)
        except openai.RateLimitError as e:
            header = e.response.headers.get("retry-after")
            raise RateLimitedError(float(header) if header else None, str(e)) from e
        except (openai.APIConnectionError, openai.APITimeoutError, openai.InternalServerError) as e:
            raise LLMError(str(e)) from e
        usage = resp.usage
        return ChatResult(
            text=resp.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    return chat


class _Cache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, text TEXT)")
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT text FROM calls WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, text: str) -> None:
        with self._lock:
            self._db.execute("INSERT OR REPLACE INTO calls VALUES (?, ?)", (key, text))
            self._db.commit()


class LLMClient:
    def __init__(
        self,
        chat_fn: ChatFn,
        *,
        cache_path: Path | None = None,
        max_attempts: int = 6,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._chat = chat_fn
        self._cache = _Cache(cache_path) if cache_path else None
        self._max_attempts = max_attempts
        self._sleep = sleep
        self.usage = Usage()

    @classmethod
    def from_settings(cls, settings: Settings, cache_path: Path | None = None) -> "LLMClient":
        return cls(openai_chat_fn(settings), cache_path=cache_path)

    def _call(self, model: str, messages: list[Message], temperature: float) -> str:
        key = hashlib.sha256(
            json.dumps([model, temperature, messages], sort_keys=True).encode()
        ).hexdigest()
        if self._cache and (hit := self._cache.get(key)) is not None:
            self.usage.cache_hits += 1
            return hit

        delay = 2.0
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = self._chat(model, messages, temperature, True)
                break
            except RateLimitedError as e:
                if e.retry_after is not None and e.retry_after > MAX_RATE_LIMIT_WAIT_S:
                    raise QuotaExhaustedError(
                        f"quota exhausted, retry in ~{e.retry_after / 60:.0f} min: {e}"
                    ) from e
                wait = e.retry_after if e.retry_after is not None else delay
            except LLMError as e:
                wait = delay
                log.warning("LLM call failed (attempt %d): %s", attempt, e)
            if attempt == self._max_attempts:
                raise LLMError(f"gave up after {attempt} attempts")
            self._sleep(min(wait, 120.0))
            delay = min(delay * 2, 60.0)

        self.usage.calls += 1
        self.usage.prompt_tokens += result.prompt_tokens
        self.usage.completion_tokens += result.completion_tokens
        self.usage.by_model[model] = self.usage.by_model.get(model, 0) + 1
        if self._cache:
            self._cache.put(key, result.text)
        return result.text

    def structured[T: BaseModel](
        self,
        messages: list[Message],
        schema: type[T],
        *,
        model: str,
        temperature: float = 0.0,
        repairs: int = 2,
    ) -> T:
        """Return the model's JSON answer validated as `schema`, repairing invalid output."""
        convo = list(messages)
        for attempt in range(repairs + 1):
            text = self._call(model, convo, temperature)
            try:
                return schema.model_validate_json(text)
            except ValidationError as e:
                if attempt == repairs:
                    raise LLMError(f"invalid {schema.__name__} after {repairs} repairs: {e}") from e
                self.usage.repairs += 1
                convo = [
                    *convo,
                    {"role": "assistant", "content": text},
                    {
                        "role": "user",
                        "content": "That JSON did not match the required schema. Errors:\n"
                        f"{e.errors(include_url=False)}\nReply with corrected JSON only.",
                    },
                ]
        raise AssertionError("unreachable")
