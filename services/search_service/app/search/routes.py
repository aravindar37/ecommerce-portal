"""Catalogue and product search routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Query

from app.api.envelope import fail, ok
from app.config import settings
from app.core_client import CoreClientError, core_client
from app.models import HybridSearchRequest, SemanticSearchRequest
from app.search.read_model import Json, read_model

router = APIRouter(prefix="/api", tags=["search"])


def query_filters(
    gender: str | None,
    master_category: str | None,
    sub_category: str | None,
    article_type: str | None,
    base_colour: str | None,
    season: str | None,
    usage: str | None,
    price_min: float | None,
    price_max: float | None,
) -> Json:
    """Build filter dictionary from query parameters."""

    filters: Json = {}
    mapping: list[tuple[str, Any]] = [
        ("gender", gender),
        ("masterCategory", master_category),
        ("subCategory", sub_category),
        ("articleType", article_type),
        ("baseColour", base_colour),
        ("season", season),
        ("usage", usage),
        ("priceMin", price_min),
        ("priceMax", price_max),
    ]
    for key, value in mapping:
        if value is not None:
            filters[key] = value
    return filters


def record_activity(event_type: str, metadata: Json) -> None:
    """Write activity to Core Service without failing the search response."""

    try:
        core_client.post_activity_event(event_type, metadata)
    except CoreClientError:
        return


@router.get("/products")
def list_products(
    background_tasks: BackgroundTasks,
    query: str | None = None,
    gender: str | None = None,
    master_category: Annotated[str | None, Query(alias="masterCategory")] = None,
    sub_category: Annotated[str | None, Query(alias="subCategory")] = None,
    article_type: Annotated[str | None, Query(alias="articleType")] = None,
    base_colour: Annotated[str | None, Query(alias="baseColour")] = None,
    season: str | None = None,
    usage: str | None = None,
    price_min: Annotated[float | None, Query(alias="priceMin")] = None,
    price_max: Annotated[float | None, Query(alias="priceMax")] = None,
    sort: str = "relevance",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
) -> dict[str, object]:
    """List and search products with filters and sorting."""

    filters = query_filters(
        gender,
        master_category,
        sub_category,
        article_type,
        base_colour,
        season,
        usage,
        price_min,
        price_max,
    )
    data = read_model.search_products(query=query, filters=filters, sort=sort, page=page, limit=limit)
    if query:
        background_tasks.add_task(record_activity, "search_performed", {"query": query, "searchMode": "hybrid", "resultCount": data["total"], "filters": filters})
    if filters:
        background_tasks.add_task(record_activity, "filter_applied", {"filters": filters})
    return ok(data, meta=hybrid_meta(data.get("source") if isinstance(data, dict) else None))


@router.get("/products/{product_slug}")
def product_detail(product_slug: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Return product detail by ID or slug and record detail activity."""

    product = read_model.find_product(product_slug)
    if not product:
        fail(404, "PRODUCT_NOT_FOUND", "Product was not found.")
    background_tasks.add_task(
        record_activity,
        "product_detail_viewed",
        {"productId": product["_id"], "sourceProductId": product["sourceProductId"], "origin": "search_service"},
    )
    return ok(product)


@router.get("/products/{product_id}/similar")
def similar_products(product_id: str, limit: int = Query(default=8, ge=1, le=50)) -> dict[str, object]:
    """Return products similar to a product."""

    product = read_model.find_product(product_id)
    if not product:
        fail(404, "PRODUCT_NOT_FOUND", "Product was not found.")
    return ok({"items": read_model.similar_products(str(product["_id"]), limit)})


@router.get("/facets")
def facets() -> dict[str, object]:
    """Return available catalogue facets."""

    return ok(read_model.facets())


@router.get("/search/products")
def keyword_search(
    background_tasks: BackgroundTasks,
    query: str | None = None,
    gender: str | None = None,
    master_category: Annotated[str | None, Query(alias="masterCategory")] = None,
    sub_category: Annotated[str | None, Query(alias="subCategory")] = None,
    article_type: Annotated[str | None, Query(alias="articleType")] = None,
    base_colour: Annotated[str | None, Query(alias="baseColour")] = None,
    season: str | None = None,
    usage: str | None = None,
    price_min: Annotated[float | None, Query(alias="priceMin")] = None,
    price_max: Annotated[float | None, Query(alias="priceMax")] = None,
    sort: str = "relevance",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=12, ge=1, le=100),
) -> dict[str, object]:
    """Search products through the public product search endpoint using hybrid retrieval."""

    filters = query_filters(
        gender,
        master_category,
        sub_category,
        article_type,
        base_colour,
        season,
        usage,
        price_min,
        price_max,
    )
    data = read_model.search_products(query=query, filters=filters, sort=sort, page=page, limit=limit)
    background_tasks.add_task(record_activity, "search_performed", {"query": query or "", "searchMode": "hybrid", "resultCount": data["total"], "filters": filters})
    if filters:
        background_tasks.add_task(record_activity, "filter_applied", {"filters": filters})
    return ok(data, meta=hybrid_meta(data.get("source") if isinstance(data, dict) else None))


@router.post("/search/semantic")
def semantic_search(payload: SemanticSearchRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Run local semantic search fallback with configured embedding metadata."""

    filtered = read_model.filter_products(read_model.active_products(), payload.filters)
    scored = [
        {"product": product, "score": read_model.semantic_score(product, payload.query), "source": "vector"}
        for product in filtered
    ]
    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
    start = max(payload.page - 1, 0) * payload.limit
    background_tasks.add_task(
        record_activity,
        "search_performed",
        {"query": payload.query, "searchMode": "semantic", "resultCount": len(ranked), "filters": payload.filters},
    )
    if payload.filters:
        background_tasks.add_task(record_activity, "filter_applied", {"filters": payload.filters})
    return ok(
        {"results": ranked[start : start + payload.limit], "page": payload.page, "limit": payload.limit, "total": len(ranked)},
        meta={
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
    )


@router.post("/search/hybrid")
def hybrid_search(payload: HybridSearchRequest, background_tasks: BackgroundTasks) -> dict[str, object]:
    """Run hybrid full-text and vector search with shared pre-filters."""

    data = read_model.hybrid_results(payload.query, payload.filters, payload.page, payload.limit)
    background_tasks.add_task(
        record_activity,
        "search_performed",
        {"query": payload.query, "searchMode": "hybrid", "resultCount": data["total"], "filters": payload.filters},
    )
    if payload.filters:
        background_tasks.add_task(record_activity, "filter_applied", {"filters": payload.filters})
    return ok(data, meta=hybrid_meta(data.get("source") if isinstance(data, dict) else None))


def hybrid_meta(source: object | None) -> Json:
    """Return response metadata for hybrid search executions."""

    return {
        "searchMode": "hybrid",
        "execution": source or "catalogue",
        "fullTextIndexName": settings.mongodb_search_index_name,
        "vectorIndexName": settings.mongodb_vector_index_name,
        "filtersAppliedTo": ["fullText", "vector"],
        "fusion": {"vectorWeight": 0.6, "fullTextWeight": 0.4},
    }
