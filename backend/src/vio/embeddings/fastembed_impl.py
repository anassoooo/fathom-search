"""fastembed (ONNX, CPU-friendly) implementations of the encoder protocols."""

import io
import threading
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from fastembed import ImageEmbedding, SparseTextEmbedding, TextEmbedding
from PIL import Image

from vio.config import Settings
from vio.embeddings.base import Encoders, SparseVector, Vector


class _Lazy[T]:
    """Load a model on first use, so importing or constructing the app stays fast."""

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._value: T | None = None
        self._lock = threading.Lock()

    def get(self) -> T:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = self._factory()
        return self._value


def _normalize(arr: Any) -> Vector:
    vec = np.asarray(arr, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    out: Vector = (vec / norm if norm > 0 else vec).tolist()
    return out


class FastEmbedDense:
    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self._model = _Lazy(lambda: TextEmbedding(model_name, cache_dir=cache_dir))
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed_query("probe"))
        return self._dim

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [_normalize(v) for v in self._model.get().passage_embed(list(texts))]

    def embed_query(self, text: str) -> Vector:
        return _normalize(next(iter(self._model.get().query_embed(text))))


class FastEmbedSparse:
    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self._model = _Lazy(lambda: SparseTextEmbedding(model_name, cache_dir=cache_dir))

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [
            SparseVector(e.indices.tolist(), e.values.tolist())
            for e in self._model.get().passage_embed(list(texts))
        ]

    def embed_query(self, text: str) -> SparseVector:
        # BM25 encodes queries differently from documents (no term-frequency saturation).
        e = next(iter(self._model.get().query_embed(text)))
        return SparseVector(e.indices.tolist(), e.values.tolist())


class FastEmbedClip:
    def __init__(self, vision_model: str, text_model: str, cache_dir: str | None = None) -> None:
        self._vision = _Lazy(lambda: ImageEmbedding(vision_model, cache_dir=cache_dir))
        self._text = _Lazy(lambda: TextEmbedding(text_model, cache_dir=cache_dir))
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = len(self.embed_text("probe"))
        return self._dim

    def embed_images(self, images: Sequence[bytes]) -> list[Vector]:
        pil = [Image.open(io.BytesIO(b)).convert("RGB") for b in images]
        return [_normalize(v) for v in self._vision.get().embed(pil)]

    def embed_text(self, text: str) -> Vector:
        return _normalize(next(iter(self._text.get().embed([text]))))


def build_encoders(settings: Settings) -> Encoders:
    cache = settings.model_cache_dir
    return Encoders(
        dense=FastEmbedDense(settings.dense_model, cache),
        sparse=FastEmbedSparse(settings.sparse_model, cache),
        image=FastEmbedClip(settings.image_model, settings.clip_text_model, cache),
    )
