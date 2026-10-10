from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from vio import __version__
from vio.api.deps import FiltersDep, ServiceDep
from vio.api.schemas import HealthOut, ProductPage, SimilarOut, TaxonomyOut
from vio.models import Product, SearchRequest, SearchResponse

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["ops"])
def health(service: ServiceDep) -> HealthOut | JSONResponse:
    try:
        points = service.store.count()
    except Exception:
        body = HealthOut(status="degraded", version=__version__, qdrant=False)
        return JSONResponse(body.model_dump(), status_code=503)
    return HealthOut(status="ok", version=__version__, qdrant=True, points=points)


@router.get("/v1/taxonomy", response_model=TaxonomyOut, tags=["catalog"])
def taxonomy(service: ServiceDep) -> TaxonomyOut:
    t = service.taxonomy()
    return TaxonomyOut(
        categories=sorted(t.categories),
        subcategories=sorted(t.subcategories),
        price_buckets=["cheap", "mid", "premium"],
        max_price=t.max_price,
    )


@router.post("/v1/search", response_model=SearchResponse, tags=["search"])
def search(body: SearchRequest, request: Request, service: ServiceDep) -> SearchResponse:
    return service.search(body, trace_id=request.state.request_id)


@router.get("/v1/products", response_model=ProductPage, tags=["catalog"])
def browse(
    service: ServiceDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
) -> ProductPage:
    """Browse the catalog, best Bayesian rating first."""
    items, total = service.browse(filters, limit, page)
    return ProductPage(
        items=items, page=page, limit=limit, total=total, has_more=page * limit < total
    )


@router.get("/v1/products/{product_id}", response_model=Product, tags=["catalog"])
def get_product(product_id: str, service: ServiceDep) -> Product:
    product = service.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail=f"product {product_id} not found")
    return product


@router.get("/v1/products/{product_id}/similar", response_model=SimilarOut, tags=["catalog"])
def similar_products(
    product_id: str,
    service: ServiceDep,
    filters: FiltersDep,
    k: Annotated[int, Query(ge=1, le=50)] = 8,
) -> SimilarOut:
    if service.get(product_id) is None:
        raise HTTPException(status_code=404, detail=f"product {product_id} not found")
    return SimilarOut(product_id=product_id, results=service.similar(product_id, filters, k))
