"""Qdrant access for the product collection (schema v2, see PLAN.md §7.3)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from vio.config import Settings
from vio.embeddings import SparseVector, Vector
from vio.models import Product, point_id_for
from vio.search.filters import Taxonomy

DENSE = "text_dense"
SPARSE = "text_sparse"
IMAGE = "image_clip"

_KEYWORD_INDEXES = ("category", "subcategory", "price_bucket", "product_id")
_FLOAT_INDEXES = ("price", "rating", "bayes_rating")


@dataclass(frozen=True)
class ProductPoint:
    product: Product
    dense: Vector
    sparse: SparseVector
    image: Vector | None = None

    def to_qdrant(self) -> qm.PointStruct:
        vectors: dict[str, Vector | qm.SparseVector] = {
            DENSE: self.dense,
            SPARSE: qm.SparseVector(indices=self.sparse.indices, values=self.sparse.values),
        }
        if self.image is not None:
            vectors[IMAGE] = self.image
        return qm.PointStruct(
            id=self.product.point_id, vector=vectors, payload=self.product.payload()
        )


def create_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url == ":memory:":
        return QdrantClient(location=":memory:")
    api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return QdrantClient(url=settings.qdrant_url, api_key=api_key, timeout=30)


class ProductStore:
    def __init__(self, client: QdrantClient, collection: str) -> None:
        self.client = client
        self.collection = collection

    # --- schema -------------------------------------------------------------

    def ensure_collection(self, dense_dim: int, image_dim: int, *, recreate: bool = False) -> bool:
        """Create the collection if needed. Returns True when it was (re)created."""
        exists = self.client.collection_exists(self.collection)
        if exists and not recreate:
            return False
        if exists:
            self.client.delete_collection(self.collection)

        self.client.create_collection(
            self.collection,
            vectors_config={
                DENSE: qm.VectorParams(size=dense_dim, distance=qm.Distance.COSINE),
                IMAGE: qm.VectorParams(size=image_dim, distance=qm.Distance.COSINE),
            },
            sparse_vectors_config={SPARSE: qm.SparseVectorParams(modifier=qm.Modifier.IDF)},
        )
        for name in _KEYWORD_INDEXES:
            self.client.create_payload_index(
                self.collection, name, field_schema=qm.PayloadSchemaType.KEYWORD
            )
        for name in _FLOAT_INDEXES:
            self.client.create_payload_index(
                self.collection, name, field_schema=qm.PayloadSchemaType.FLOAT
            )
        return True

    # --- writes -------------------------------------------------------------

    def upsert(self, points: Sequence[ProductPoint]) -> None:
        if points:
            self.client.upsert(self.collection, points=[p.to_qdrant() for p in points], wait=True)

    def existing_ids(self, product_ids: Iterable[str]) -> set[str]:
        ids = [point_id_for(pid) for pid in product_ids]
        if not ids:
            return set()
        found = self.client.retrieve(self.collection, ids=ids, with_payload=["product_id"])
        return {str(r.payload["product_id"]) for r in found if r.payload}

    # --- reads --------------------------------------------------------------

    def count(self, query_filter: qm.Filter | None = None) -> int:
        return self.client.count(self.collection, count_filter=query_filter, exact=True).count

    def get(self, product_id: str) -> Product | None:
        found = self.client.retrieve(self.collection, ids=[point_id_for(product_id)])
        return Product.model_validate(found[0].payload) if found and found[0].payload else None

    def browse(
        self, query_filter: qm.Filter | None, limit: int, cursor: str | None = None
    ) -> tuple[list[Product], str | None]:
        records, next_offset = self.client.scroll(
            self.collection,
            scroll_filter=query_filter,
            limit=limit,
            offset=cursor,
            with_payload=True,
        )
        products = [Product.model_validate(r.payload) for r in records if r.payload]
        return products, (str(next_offset) if next_offset is not None else None)

    def taxonomy(self) -> Taxonomy:
        def facet_values(key: str) -> frozenset[str]:
            res = self.client.facet(self.collection, key=key, limit=10_000, exact=True)
            return frozenset(str(h.value) for h in res.hits)

        top = self.client.scroll(
            self.collection,
            limit=1,
            order_by=qm.OrderBy(key="price", direction=qm.Direction.DESC),
            with_payload=["price"],
        )[0]
        max_price = float(top[0].payload["price"]) if top and top[0].payload else 100_000.0
        return Taxonomy(
            categories=facet_values("category"),
            subcategories=facet_values("subcategory"),
            max_price=max_price,
        )
