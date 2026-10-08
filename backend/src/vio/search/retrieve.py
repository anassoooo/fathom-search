"""First-stage retrieval: one Qdrant Query API call over any mix of sources, fused with RRF.

Filters are attached to every prefetch so each source only ever ranks eligible
products. Post-filtering would silently return fewer than `limit` results.
"""

from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client import models as qm

from vio.embeddings import SparseVector, Vector
from vio.models import Product, point_id_for
from vio.store.qdrant import DENSE, IMAGE, SPARSE


@dataclass(frozen=True)
class QueryVectors:
    dense: Vector | None = None
    sparse: SparseVector | None = None
    clip_text: Vector | None = None  # text query in CLIP space, matched against product images
    image: Vector | None = None  # uploaded image in CLIP space, matched against product images

    def sources(self) -> list[tuple[str, Vector | qm.SparseVector]]:
        out: list[tuple[str, Vector | qm.SparseVector]] = []
        if self.dense is not None:
            out.append((DENSE, self.dense))
        if self.sparse is not None:
            out.append(
                (SPARSE, qm.SparseVector(indices=self.sparse.indices, values=self.sparse.values))
            )
        if self.clip_text is not None:
            out.append((IMAGE, self.clip_text))
        if self.image is not None:
            out.append((IMAGE, self.image))
        return out


@dataclass(frozen=True)
class Candidate:
    product: Product
    score: float


def _to_candidates(points: list[qm.ScoredPoint]) -> list[Candidate]:
    return [Candidate(Product.model_validate(p.payload), p.score) for p in points if p.payload]


def _with_exclusion(base: qm.Filter | None, point_id: str) -> qm.Filter:
    exclude = qm.HasIdCondition(has_id=[point_id])
    if base is None:
        return qm.Filter(must_not=[exclude])
    match base.must_not:
        case None:
            existing = []
        case list():
            existing = list(base.must_not)
        case single:
            existing = [single]
    return base.model_copy(update={"must_not": [*existing, exclude]})


def _query(
    client: QdrantClient,
    collection: str,
    sources: list[tuple[str, Vector | qm.SparseVector]],
    query_filter: qm.Filter | None,
    limit: int,
    prefetch_limit: int,
) -> list[Candidate]:
    if not sources:
        raise ValueError("at least one query vector is required")

    if len(sources) == 1:
        using, vector = sources[0]
        res = client.query_points(
            collection,
            query=vector,
            using=using,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
    else:
        res = client.query_points(
            collection,
            prefetch=[
                qm.Prefetch(query=v, using=u, filter=query_filter, limit=prefetch_limit)
                for u, v in sources
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
    return _to_candidates(res.points)


def retrieve(
    client: QdrantClient,
    collection: str,
    vectors: QueryVectors,
    query_filter: qm.Filter | None,
    limit: int,
    prefetch_limit: int = 100,
) -> list[Candidate]:
    return _query(client, collection, vectors.sources(), query_filter, limit, prefetch_limit)


def similar(
    client: QdrantClient,
    collection: str,
    product_id: str,
    query_filter: qm.Filter | None,
    limit: int,
    prefetch_limit: int = 100,
) -> list[Candidate]:
    """Products similar to `product_id` by text and (when available) image, excluding itself."""
    pid = point_id_for(product_id)
    found = client.retrieve(collection, ids=[pid], with_vectors=[DENSE, IMAGE])
    if not found or not isinstance(found[0].vector, dict):
        return []
    vecs = found[0].vector
    sources: list[tuple[str, Vector | qm.SparseVector]] = [
        (name, vecs[name])  # type: ignore[misc]
        for name in (DENSE, IMAGE)
        if isinstance(vecs.get(name), list)
    ]
    return _query(
        client, collection, sources, _with_exclusion(query_filter, pid), limit, prefetch_limit
    )
