"""LLM query understanding for the `full` search variant (T041).

The model's output is untrusted (Constitution Art. V): it is parsed into `ParsedQuery`,
and the pipeline then validates its filters against the real taxonomy like any other
filters. Results are memoized per normalized query (bounded LRU) so repeated searches
cost no tokens.
"""

import threading
from collections import OrderedDict
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from vio.llm.client import LLMClient
from vio.llm.prompts import load_prompt
from vio.models import Filters

PROMPT_VERSION = "v1"


class ParsedQuery(BaseModel):
    search_text: str = Field(min_length=1, max_length=300)
    category: str | None = None
    price_min: float | None = Field(default=None, ge=0)
    price_max: float | None = Field(default=None, ge=0)
    price_intent: Literal["cheap", "premium"] | None = None
    prompt_version: str = PROMPT_VERSION

    @field_validator("category", mode="before")
    @classmethod
    def _blank_category(cls, v: object) -> object:
        return None if isinstance(v, str) and v.strip().lower() in {"", "null", "none"} else v

    def to_filters(self) -> Filters:
        bucket = self.price_intent if self.price_min is None and self.price_max is None else None
        return Filters(
            category=self.category,
            price_min=self.price_min,
            price_max=self.price_max,
            price_bucket=bucket,
        )


def merge_filters(explicit: Filters, inferred: Filters) -> Filters:
    """Fields the user set explicitly win; the LLM only fills the gaps."""
    data = inferred.model_dump()
    data.update({k: v for k, v in explicit.model_dump().items() if v is not None})
    return Filters.model_validate(data)


class QueryUnderstanding:
    def __init__(
        self,
        llm: LLMClient,
        model: str,
        categories: Callable[[], Iterable[str]],
        cache_size: int = 2048,
    ) -> None:
        self._llm = llm
        self._model = model
        self._categories = categories
        self._cache: OrderedDict[str, ParsedQuery] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def _prompt(self, query: str) -> str:
        cats = "\n".join(f"- {c}" for c in sorted(self._categories()))
        return (
            load_prompt(f"query_understanding.{PROMPT_VERSION}.md")
            .replace("{categories}", cats)
            .replace("{request}", query.replace("</request>", ""))
        )

    def parse(self, query: str) -> ParsedQuery:
        key = " ".join(query.lower().split())
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        parsed = self._llm.structured(
            [{"role": "user", "content": self._prompt(query)}], ParsedQuery, model=self._model
        )
        with self._lock:
            self._cache[key] = parsed
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return parsed
