"""Embed products in batches and upsert them. Safe to re-run: existing points are skipped."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from PIL import UnidentifiedImageError

from vio.embeddings import Encoders, Vector
from vio.ingest.images import ImageSource
from vio.models import Product
from vio.store.qdrant import ProductPoint, ProductStore

log = logging.getLogger(__name__)


@dataclass
class IngestReport:
    total: int = 0
    upserted: int = 0
    skipped_existing: int = 0
    with_image: int = 0
    image_errors: int = 0


def _batches(items: Sequence[Product], size: int) -> list[Sequence[Product]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _embed_images(
    encoders: Encoders, images: dict[str, bytes], report: IngestReport
) -> dict[str, Vector]:
    if not images:
        return {}
    ids = list(images)
    try:
        return dict(zip(ids, encoders.image.embed_images([images[i] for i in ids]), strict=True))
    except (UnidentifiedImageError, OSError):
        # One corrupt file shouldn't sink the batch: fall back to one at a time.
        out: dict[str, Vector] = {}
        for pid in ids:
            try:
                out[pid] = encoders.image.embed_images([images[pid]])[0]
            except (UnidentifiedImageError, OSError):
                report.image_errors += 1
                log.warning("unreadable image for product %s", pid)
        return out


def ingest(
    products: Sequence[Product],
    store: ProductStore,
    encoders: Encoders,
    images: ImageSource,
    *,
    batch_size: int = 64,
    skip_existing: bool = True,
    on_batch: Callable[[int], None] | None = None,
) -> IngestReport:
    report = IngestReport(total=len(products))
    store.ensure_collection(encoders.dense.dim, encoders.image.dim)

    for batch in _batches(products, batch_size):
        todo = list(batch)
        if skip_existing:
            existing = store.existing_ids(p.product_id for p in batch)
            todo = [p for p in batch if p.product_id not in existing]
            report.skipped_existing += len(batch) - len(todo)

        if todo:
            texts = [p.doc_text() for p in todo]
            dense = encoders.dense.embed_documents(texts)
            sparse = encoders.sparse.embed_documents(texts)
            image_vecs = _embed_images(encoders, images.load(todo), report)
            report.with_image += len(image_vecs)
            store.upsert(
                [
                    ProductPoint(p, d, s, image_vecs.get(p.product_id))
                    for p, d, s in zip(todo, dense, sparse, strict=True)
                ]
            )
            report.upserted += len(todo)

        if on_batch:
            on_batch(len(batch))
    return report
