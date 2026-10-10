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


def _and(a: qm.Filter | None, b: qm.Filter) -> qm.Filter:
    if a is None:
        return b
    must_a = a.must if isinstance(a.must, list) else ([a.must] if a.must else [])
    must_b = b.must if isinstance(b.must, list) else ([b.must] if b.must else [])
    return a.model_copy(update={"must": [*must_a, *must_b]})


def _query(
    client: QdrantClient,
    collection: str,
    sources: list[tuple[str, Vector | qm.SparseVector]],
    query_filter: qm.Filter | None,
    limit: int,
    prefetch_limit: int,
    boost_filter: qm.Filter | None = None,
) -> list[Candidate]:
    """`query_filter` is hard (applied everywhere). `boost_filter` is soft: each source gets
    an extra prefetch restricted to it, so matching products earn an extra RRF vote and rank
    higher, while everything else stays eligible."""
    if not sources:
        raise ValueError("at least one query vector is required")

    if len(sources) == 1 and boost_filter is None:
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
        prefetch = [
            qm.Prefetch(query=v, using=u, filter=query_filter, limit=prefetch_limit)
            for u, v in sources
        ]
        if boost_filter is not None:
            boosted = _and(query_filter, boost_filter)
            prefetch += [
                qm.Prefetch(query=v, using=u, filter=boosted, limit=prefetch_limit)
                for u, v in sources
            ]
        res = client.query_points(
            collection,
            prefetch=prefetch,
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
    boost_filter: qm.Filter | None = None,
) -> list[Candidate]:
    return _query(
        client, collection, vectors.sources(), query_filter, limit, prefetch_limit, boost_filter
    )


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
