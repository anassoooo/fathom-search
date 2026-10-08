"""Runs the real ONNX models. Downloads ~400 MB on first run."""

import io
import math

import pytest
from PIL import Image

from vio.config import Settings
from vio.embeddings import Encoders
from vio.embeddings.fastembed_impl import build_encoders

pytestmark = [pytest.mark.integration, pytest.mark.models]


@pytest.fixture(scope="module")
def encoders() -> Encoders:
    return build_encoders(Settings())


def _png(color: tuple[int, int, int]) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_dense_bge_small(encoders: Encoders) -> None:
    assert encoders.dense.dim == 384
    q = encoders.dense.embed_query("noise cancelling headphones")
    near, far = encoders.dense.embed_documents(
        ["Sony WH-1000XM5 Wireless Noise Canceling Headphones", "Lodge Cast Iron Skillet"]
    )
    assert math.isclose(sum(v * v for v in q), 1.0, rel_tol=1e-4)
    assert _cos(q, near) > _cos(q, far)


def test_sparse_bm25(encoders: Encoders) -> None:
    doc = encoders.sparse.embed_documents(["Keurig coffee maker single serve"])[0]
    query = encoders.sparse.embed_query("coffee maker")
    assert set(query.indices) <= set(doc.indices)


def test_clip_text_and_image_share_space(encoders: Encoders) -> None:
    assert encoders.image.dim == 512
    red, blue = encoders.image.embed_images([_png((220, 20, 20)), _png((20, 20, 220))])
    t = encoders.image.embed_text("a plain red square")
    assert len(red) == 512
    assert _cos(t, red) > _cos(t, blue)


def test_cross_encoder_prefers_relevant_doc() -> None:
    from vio.search.rerank import FastEmbedReranker

    r = FastEmbedReranker(Settings().rerank_model)
    good, bad = r.score(
        "espresso machine", ["Breville Barista Express Espresso Machine", "LEGO Classic Brick Box"]
    )
    assert good > bad
