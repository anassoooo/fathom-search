"""Build a populated ProductStore from the fixture CSV with fake encoders."""

import hashlib

from vio.embeddings import Encoders
from vio.models import Product
from vio.store.qdrant import ProductPoint, ProductStore


def fake_image_bytes(product: Product) -> bytes:
    return hashlib.sha256(f"img:{product.product_id}".encode()).digest()


def populate(store: ProductStore, products: list[Product], enc: Encoders) -> None:
    store.ensure_collection(enc.dense.dim, enc.image.dim, recreate=True)
    texts = [p.doc_text() for p in products]
    dense = enc.dense.embed_documents(texts)
    sparse = enc.sparse.embed_documents(texts)
    with_image = [p for p in products if p.image_url]
    images = dict(
        zip(
            [p.product_id for p in with_image],
            enc.image.embed_images([fake_image_bytes(p) for p in with_image]),
            strict=True,
        )
    )
    store.upsert(
        [
            ProductPoint(p, d, s, images.get(p.product_id))
            for p, d, s in zip(products, dense, sparse, strict=True)
        ]
    )
