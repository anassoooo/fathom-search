"""The search pipeline: sanitize filters -> encode -> retrieve (RRF) -> rerank -> top k."""

import base64
import binascii
import logging
import threading
from concurrent.futures import Executor, ThreadPoolExecutor

from vio.config import Settings
from vio.embeddings import Encoders, Vector
from vio.llm.query_understanding import ParsedQuery, QueryUnderstanding, merge_filters
from vio.models import Filters, Product, SearchHit, SearchRequest, SearchResponse
from vio.observability.timing import timed
from vio.search.filters import Taxonomy, sanitize, to_qdrant
from vio.search.rerank import Reranker, rerank
from vio.search.retrieve import Candidate, QueryVectors, retrieve, similar
from vio.search.variants import VARIANTS
from vio.store.qdrant import ProductStore

log = logging.getLogger(__name__)


class SearchInputError(ValueError):
    """The request cannot be served as given (e.g. unreadable image and no text)."""


def decode_image(image_b64: str, max_bytes: int) -> bytes:
    data = image_b64.split(",", 1)[1] if image_b64.startswith("data:") else image_b64
    try:
        raw = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as e:
        raise SearchInputError("image is not valid base64") from e
    if len(raw) > max_bytes:
        raise SearchInputError(f"image exceeds {max_bytes // (1024 * 1024)} MB")
    return raw


class SearchService:
    def __init__(
        self,
        store: ProductStore,
        encoders: Encoders,
        reranker: Reranker,
        settings: Settings,
        executor: Executor | None = None,
        understander: QueryUnderstanding | None = None,
    ) -> None:
        self.understander = understander
        self.store = store
        self.encoders = encoders
        self.reranker = reranker
        self.settings = settings
        self._executor = executor or ThreadPoolExecutor(max_workers=4, thread_name_prefix="rerank")
        self._taxonomy: Taxonomy | None = None
        self._taxonomy_lock = threading.Lock()

    def warmup(self) -> None:
        """Load every model now, so the first request is not timed against model loading."""
        self.encoders.dense.embed_query("warmup")
        self.encoders.sparse.embed_query("warmup")
        self.encoders.image.embed_text("warmup")
        self.reranker.score("warmup", ["warm", "up"])

    # --- taxonomy -----------------------------------------------------------

    def taxonomy(self, *, refresh: bool = False) -> Taxonomy:
        if self._taxonomy is None or refresh:
            with self._taxonomy_lock:
                if self._taxonomy is None or refresh:
                    self._taxonomy = self.store.taxonomy()
        return self._taxonomy

    # --- search -------------------------------------------------------------

    def _understand(
        self, text: str, timings: dict[str, float], degraded: list[str]
    ) -> ParsedQuery | None:
        """LLM query understanding; any failure degrades to plain retrieval (Art. VI)."""
        if self.understander is None:
            degraded.append("llm")
            return None
        try:
            with timed(timings, "understand_ms"):
                return self.understander.parse(text)
        except Exception:
            log.warning("query understanding failed; searching without it", exc_info=True)
            degraded.append("llm")
            return None

    def _encode(
        self, request: SearchRequest, timings: dict[str, float], degraded: list[str]
    ) -> QueryVectors:
        cfg = VARIANTS[request.variant]
        text = (request.query or "").strip()
        dense = sparse = clip_text = image = None

        with timed(timings, "encode_ms"):
            if text:
                dense = self.encoders.dense.embed_query(text) if cfg.dense else None
                sparse = self.encoders.sparse.embed_query(text) if cfg.sparse else None
                clip_text = self.encoders.image.embed_text(text) if cfg.clip_text else None
            if request.image_b64:
                image = self._encode_image(
                    request.image_b64, has_text=bool(text), degraded=degraded
                )

        return QueryVectors(dense=dense, sparse=sparse, clip_text=clip_text, image=image)

    def _encode_image(
        self, image_b64: str, *, has_text: bool, degraded: list[str]
    ) -> Vector | None:
        raw = decode_image(image_b64, self.settings.max_image_bytes)
        try:
            return self.encoders.image.embed_images([raw])[0]
        except Exception as e:
            if not has_text:
                raise SearchInputError("could not read the image") from e
            log.warning("image encoding failed; continuing text-only", exc_info=True)
            degraded.append("image_encoder")
            return None

    def search(self, request: SearchRequest, trace_id: str | None = None) -> SearchResponse:
        timings: dict[str, float] = {}
        degraded: list[str] = []
        cfg = VARIANTS[request.variant]

        with timed(timings, "total_ms"):
            text = (request.query or "").strip()
            requested = request.filters
            parsed = None
            if cfg.llm and text:
                parsed = self._understand(text, timings, degraded)
                if parsed is not None:
                    requested = merge_filters(request.filters, parsed.to_filters())
                    text = parsed.search_text.strip() or text
                    request = request.model_copy(update={"query": text})

            filters, dropped = sanitize(requested, self.taxonomy())
            vectors = self._encode(request, timings, degraded)
            if not vectors.sources():
                raise SearchInputError("nothing to search with: empty query and no usable image")

            use_rerank = cfg.rerank and bool(text)
            limit = max(request.k, self.settings.rerank_top_n) if use_rerank else request.k

            with timed(timings, "retrieve_ms"):
                candidates = retrieve(
                    self.store.client, self.store.collection, vectors, to_qdrant(filters), limit
                )

            if use_rerank:
                with timed(timings, "rerank_ms"):
                    outcome = rerank(
                        self.reranker,
                        text,
                        candidates,
                        top_n=self.settings.rerank_top_n,
                        timeout_s=self.settings.rerank_timeout_s,
                        executor=self._executor,
                    )
                candidates = outcome.candidates
                if outcome.degraded:
                    degraded.append("reranker")

        log.info(
            "search",
            extra={
                "fields": {
                    "event": "search",
                    "variant": request.variant,
                    "query": text[:200],
                    "has_image": request.image_b64 is not None,
                    "k": request.k,
                    "n_results": min(len(candidates), request.k),
                    "filters": filters.model_dump(exclude_none=True),
                    "dropped_filters": dropped,
                    "degraded": degraded,
                    "timings_ms": timings,
                }
            },
        )
        return SearchResponse(
            results=_to_hits(candidates[: request.k]),
            variant=request.variant,
            applied_filters=filters,
            dropped_filters=dropped,
            timings_ms=timings,
            degraded=degraded,
            parsed_query=parsed.model_dump() if parsed else None,
            trace_id=trace_id,
        )

    # --- catalog ------------------------------------------------------------

    def get(self, product_id: str) -> Product | None:
        return self.store.get(product_id)

    def similar(self, product_id: str, filters: Filters, k: int) -> list[SearchHit]:
        clean, _ = sanitize(filters, self.taxonomy())
        return _to_hits(
            similar(self.store.client, self.store.collection, product_id, to_qdrant(clean), k)
        )

    def browse(
        self, filters: Filters, limit: int, cursor: str | None
    ) -> tuple[list[Product], str | None]:
        clean, _ = sanitize(filters, self.taxonomy())
        return self.store.browse(to_qdrant(clean), limit, cursor)


def _to_hits(candidates: list[Candidate]) -> list[SearchHit]:
    return [
        SearchHit(product=c.product, score=c.score, rank=i)
        for i, c in enumerate(candidates, start=1)
    ]
