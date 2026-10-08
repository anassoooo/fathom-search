"""Build a populated ProductStore from the fixture CSV with fake encoders."""

from vio.embeddings import Encoders
from vio.embeddings.fake import FAKE_IMAGE_PREFIX
from vio.models import Product
from vio.store.qdrant import ProductPoint, ProductStore


def fake_image_bytes(product: Product) -> bytes:
    """A stand-in 'photo' whose content is the product's own description."""
    return FAKE_IMAGE_PREFIX + f"{product.doc_text()} #{product.product_id}".encode()


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
