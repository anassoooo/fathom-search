"""Deterministic, dependency-free encoders for tests and offline CI.

They hash tokens into buckets, so texts that share words get similar vectors.
That is enough to test retrieval plumbing without downloading models.
"""

import hashlib
import math
import re
from collections import Counter
from collections.abc import Sequence

from vio.embeddings.base import Encoders, SparseVector, Vector

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _bucket(token: str, n: int) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big") % n


def _hashed_bow(text: str, dim: int) -> Vector:
    vec = [0.0] * dim
    for tok in _tokens(text):
        vec[_bucket(tok, dim)] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0
        return vec
    return [v / norm for v in vec]


class FakeDense:
    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [_hashed_bow(t, self._dim) for t in texts]

    def embed_query(self, text: str) -> Vector:
        return _hashed_bow(text, self._dim)


class FakeSparse:
    def _encode(self, text: str) -> SparseVector:
        counts = Counter(_bucket(t, 2**20) for t in _tokens(text))
        indices = sorted(counts)
        return SparseVector(indices, [float(counts[i]) for i in indices])

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]:
        return [self._encode(t) for t in texts]

    def embed_query(self, text: str) -> SparseVector:
        return self._encode(text)


class FakeImage:
    """Images hash to a vector; text uses bag-of-words. Identical image bytes match exactly."""

    def __init__(self, dim: int = 32) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed_images(self, images: Sequence[bytes]) -> list[Vector]:
        return [_hashed_bow(hashlib.sha256(b).hexdigest(), self._dim) for b in images]

    def embed_text(self, text: str) -> Vector:
        return _hashed_bow(text, self._dim)


def fake_encoders() -> Encoders:
    return Encoders(dense=FakeDense(), sparse=FakeSparse(), image=FakeImage())
