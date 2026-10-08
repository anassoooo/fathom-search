import math

from vio.embeddings.fake import FakeDense, FakeImage, FakeSparse


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_dense_is_normalized_deterministic_and_shaped() -> None:
    enc = FakeDense(dim=64)
    a, b = enc.embed_documents(["wireless headphones", "wireless headphones"])
    assert len(a) == enc.dim == 64
    assert a == b
    assert math.isclose(math.sqrt(sum(v * v for v in a)), 1.0, rel_tol=1e-9)


def test_dense_shared_words_are_closer() -> None:
    enc = FakeDense()
    q = enc.embed_query("noise cancelling headphones")
    near, far = enc.embed_documents(["Anker noise cancelling headphones", "cast iron skillet"])
    assert _cos(q, near) > _cos(q, far)


def test_dense_empty_text_still_returns_unit_vector() -> None:
    v = FakeDense().embed_query("")
    assert math.isclose(sum(x * x for x in v), 1.0)


def test_sparse_counts_terms() -> None:
    vec = FakeSparse().embed_query("coffee coffee maker")
    assert sorted(vec.values) == [1.0, 2.0]
    assert vec.indices == sorted(vec.indices)


def test_image_identical_bytes_match() -> None:
    enc = FakeImage()
    a, b, c = enc.embed_images([b"img-1", b"img-1", b"img-2"])
    assert a == b != c
    assert len(enc.embed_text("red dress")) == enc.dim


def test_fake_image_descriptions_live_in_text_space() -> None:
    from vio.embeddings.fake import FAKE_IMAGE_PREFIX

    enc = FakeImage()
    shoe, skillet = enc.embed_images(
        [FAKE_IMAGE_PREFIX + b"red running shoe", FAKE_IMAGE_PREFIX + b"cast iron skillet"]
    )
    q = enc.embed_text("running shoe")
    assert _cos(q, shoe) > _cos(q, skillet)
