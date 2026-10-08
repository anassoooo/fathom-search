from typing import Annotated

from fastapi import Depends, Query, Request

from vio.models import Filters, PriceBucket
from vio.search.pipeline import SearchService


def get_service(request: Request) -> SearchService:
    service: SearchService = request.app.state.service
    return service


def filters_from_query(
    category: str | None = None,
    subcategory: str | None = None,
    price_min: Annotated[float | None, Query(ge=0)] = None,
    price_max: Annotated[float | None, Query(ge=0)] = None,
    price_bucket: PriceBucket | None = None,
    min_rating: Annotated[float | None, Query(ge=0, le=5)] = None,
) -> Filters:
    return Filters(
        category=category,
        subcategory=subcategory,
        price_min=price_min,
        price_max=price_max,
        price_bucket=price_bucket,
        min_rating=min_rating,
    )


ServiceDep = Annotated[SearchService, Depends(get_service)]
FiltersDep = Annotated[Filters, Depends(filters_from_query)]
