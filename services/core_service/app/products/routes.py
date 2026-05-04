"""Product record and local image routes."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse

from app.api.envelope import fail, ok
from app.config import settings
from app.dependencies import anonymous_id_from_request, current_user_optional
from app.store import Json, store

router = APIRouter(tags=["products"])


@router.get("/api/products")
def list_products(
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
    query: str | None = None,
    limit: int = Query(default=12, ge=1, le=100),
    page: int = Query(default=1, ge=1),
) -> dict[str, object]:
    """List active product records."""

    anonymous_id = anonymous_id_from_request(request, response)
    data = store.list_products(limit=limit, page=page, query=query)
    if query:
        store.add_activity("search_performed", {"query": query, "resultCount": len(data["items"])}, user, anonymous_id)
    return ok(data)


@router.get("/api/products/{product_slug}")
def product_detail(
    product_slug: str,
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Return one product by ID or slug and capture selection activity."""

    product = store.find_product(product_slug)
    if not product:
        fail(404, "PRODUCT_NOT_FOUND", "Product was not found.")
    anonymous_id = anonymous_id_from_request(request, response)
    store.add_activity(
        "product_detail_viewed",
        {"productId": product["_id"], "sourceProductId": product["sourceProductId"]},
        user,
        anonymous_id,
    )
    return ok(product)


@router.get("/api/facets")
def facets() -> dict[str, object]:
    """Return catalogue facets derived from product records."""

    return ok(store.product_facets())


@router.get("/product-images/{filename}")
def product_image(filename: str) -> FileResponse:
    """Serve local product images from the demo dataset directory."""

    safe_name = Path(filename).name
    image_path = settings.product_image_local_root / safe_name
    if not image_path.exists() and safe_name != "fallback.jpg":
        fallback = settings.product_image_local_root / "fallback.jpg"
        if fallback.exists():
            return FileResponse(fallback)
    if not image_path.exists():
        fail(404, "IMAGE_NOT_FOUND", "Product image was not found.")
    return FileResponse(image_path)
