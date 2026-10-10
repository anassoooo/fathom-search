"""fastembed (ONNX, CPU-friendly) implementations of the encoder protocols."""

import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from fastembed import ImageEmbedding, SparseTextEmbedding, TextEmbedding
from PIL import Image

from vio.config import Settings
from vio.embeddings.base import Encoders, SparseVector, Vector
from vio.lazy import Lazy


@dataclass(frozen=True)
class Runtime:
    """Where and how ONNX models run. Passed to every fastembed model."""

    cache_dir: str | None = None
    threads: int | None = None
    cuda: bool = False

    def kwargs(self) -> dict[str, Any]:
        if self.cuda:
            enable_cuda()
            return {"cache_dir": self.cache_dir, "cuda": True}
        return {"cache_dir": self.cache_dir, "threads": self.threads}

    @classmethod
    def from_settings(cls, settings: Settings) -> "Runtime":
        # A fixed default: fastembed-gpu otherwise resolves its cache to the working directory.
        cache = settings.model_cache_dir or str(Path.home() / ".cache" / "vio" / "models")
        return cls(cache, settings.onnx_threads, settings.onnx_device == "cuda")


_cuda_ready = False


def enable_cuda() -> None:
    """Load the CUDA/cuDNN DLLs shipped as nvidia-* pip packages (needed on Windows)."""
    global _cuda_ready
    if _cuda_ready:
        return
    import onnxruntime as ort

    if "CUDAExecutionProvider" not in ort.get_available_providers():
        raise RuntimeError(
            "ONNX_DEVICE=cuda but onnxruntime has no CUDA provider; run `uv sync --extra gpu`"
        )
    if hasattr(ort, "preload_dlls"):
        ort.preload_dlls()
    _cuda_ready = True


def _normalize(arr: Any) -> Vector:
    vec = np.asarray(arr, dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    out: Vector = (vec / norm if norm > 0 else vec).tolist()
    return out


class FastEmbedDense:
    def __init__(self, model_name: str, runtime: Runtime | None = None) -> None:
        rt = runtime or Runtime()
        self._model = Lazy(lambda: TextEmbedding(model_name, **rt.kwargs()))
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
    def __init__(self, model_name: str, runtime: Runtime | None = None) -> None:
        # BM25 is a tokenizer + statistics, not a neural model: always CPU.
        rt = runtime or Runtime()
        self._model = Lazy(
            lambda: SparseTextEmbedding(model_name, cache_dir=rt.cache_dir, threads=rt.threads)
        )

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
    def __init__(self, vision_model: str, text_model: str, runtime: Runtime | None = None) -> None:
        rt = runtime or Runtime()
        self._vision = Lazy(lambda: ImageEmbedding(vision_model, **rt.kwargs()))
        self._text = Lazy(lambda: TextEmbedding(text_model, **rt.kwargs()))
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
    rt = Runtime.from_settings(settings)
    return Encoders(
        dense=FastEmbedDense(settings.dense_model, rt),
        sparse=FastEmbedSparse(settings.sparse_model, rt),
        image=FastEmbedClip(settings.image_model, settings.clip_text_model, rt),
    )
