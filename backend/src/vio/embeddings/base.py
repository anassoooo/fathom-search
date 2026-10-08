"""Encoder interfaces. Everything above this layer depends on these protocols, not on fastembed."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

Vector = list[float]


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]
    values: list[float]


class TextDenseEncoder(Protocol):
    @property
    def dim(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[Vector]: ...

    def embed_query(self, text: str) -> Vector: ...


class SparseEncoder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[SparseVector]: ...

    def embed_query(self, text: str) -> SparseVector: ...


class ImageEncoder(Protocol):
    """A joint image-text space (CLIP): images and text queries map to comparable vectors."""

    @property
    def dim(self) -> int: ...

    def embed_images(self, images: Sequence[bytes]) -> list[Vector]: ...

    def embed_text(self, text: str) -> Vector: ...


@dataclass(frozen=True)
class Encoders:
    dense: TextDenseEncoder
    sparse: SparseEncoder
    image: ImageEncoder
