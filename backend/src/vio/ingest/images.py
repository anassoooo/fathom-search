"""Find product images on disk, optionally downloading them from their URLs into a cache dir."""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

from vio.models import Product

log = logging.getLogger(__name__)

_EXTS = (".jpg", ".jpeg", ".png", ".webp")
_MAX_BYTES = 5 * 1024 * 1024


class ImageSource:
    def __init__(self, image_dir: Path | None, *, fetch: bool = False, workers: int = 8) -> None:
        self.image_dir = image_dir
        self.fetch = fetch and image_dir is not None
        self.workers = workers

    def _local_path(self, product_id: str) -> Path | None:
        if self.image_dir is None:
            return None
        for ext in _EXTS:
            p = self.image_dir / f"{product_id}{ext}"
            if p.exists():
                return p
        return None

    def _download(self, client: httpx.Client, product: Product) -> bytes | None:
        assert self.image_dir is not None and product.image_url
        try:
            resp = client.get(product.image_url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.warning("image download failed for %s: %s", product.product_id, e)
            return None
        if len(resp.content) > _MAX_BYTES:
            return None
        self.image_dir.mkdir(parents=True, exist_ok=True)
        (self.image_dir / f"{product.product_id}.jpg").write_bytes(resp.content)
        return resp.content

    def load(self, products: list[Product]) -> dict[str, bytes]:
        """Return image bytes keyed by product_id, for products that have an image."""
        found: dict[str, bytes] = {}
        missing: list[Product] = []
        for p in products:
            path = self._local_path(p.product_id)
            if path is not None:
                found[p.product_id] = path.read_bytes()
            elif self.fetch and p.image_url:
                missing.append(p)

        if missing:
            with (
                httpx.Client(timeout=10, follow_redirects=True) as client,
                ThreadPoolExecutor(self.workers) as pool,
            ):
                for p, data in zip(
                    missing, pool.map(lambda p: self._download(client, p), missing), strict=True
                ):
                    if data is not None:
                        found[p.product_id] = data
        return found
