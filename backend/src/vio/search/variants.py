"""Named retrieval configurations. Offline eval and online A/B use exactly these."""

from dataclasses import dataclass

from vio.models import Variant


@dataclass(frozen=True)
class VariantConfig:
    dense: bool
    sparse: bool
    clip_text: bool
    rerank: bool
    llm: bool


VARIANTS: dict[Variant, VariantConfig] = {
    "bm25": VariantConfig(dense=False, sparse=True, clip_text=False, rerank=False, llm=False),
    "dense": VariantConfig(dense=True, sparse=False, clip_text=False, rerank=False, llm=False),
    "hybrid": VariantConfig(dense=True, sparse=True, clip_text=True, rerank=False, llm=False),
    "hybrid_rerank": VariantConfig(dense=True, sparse=True, clip_text=True, rerank=True, llm=False),
    # LLM query understanding is wired in by T041; until then `full` == `hybrid_rerank`.
    "full": VariantConfig(dense=True, sparse=True, clip_text=True, rerank=True, llm=True),
}
