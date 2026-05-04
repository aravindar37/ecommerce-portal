"""Cart routes for anonymous and authenticated shoppers."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.envelope import fail, ok
from app.dependencies import anonymous_id_from_request, current_user_optional, current_user_required
from app.models import AddCartItemRequest, UpdateCartItemRequest
from app.store import Json, store

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("")
def get_cart(
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Return the current active cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    return ok(store.cart_snapshot(user, anonymous_id))


@router.post("/items", status_code=status.HTTP_201_CREATED)
def add_item(
    payload: AddCartItemRequest,
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Add a product to the active cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        item = store.add_cart_item(user, anonymous_id, payload.productId, payload.quantity, payload.size)
    except ValueError as exc:
        if str(exc) == "PRODUCT_NOT_FOUND":
            fail(404, "PRODUCT_NOT_FOUND", "Product was not found.")
        raise
    return ok(item)


@router.patch("/items/{cart_item_id}")
def update_item(
    cart_item_id: str,
    payload: UpdateCartItemRequest,
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Update a cart item quantity."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        item = store.update_cart_item(user, anonymous_id, cart_item_id, payload.quantity)
    except ValueError as exc:
        if str(exc) == "CART_ITEM_NOT_FOUND":
            fail(404, "CART_ITEM_NOT_FOUND", "Cart item was not found.")
        raise
    return ok(item)


@router.delete("/items/{cart_item_id}")
def remove_item(
    cart_item_id: str,
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Remove an item from the active cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        item = store.remove_cart_item(user, anonymous_id, cart_item_id)
    except ValueError as exc:
        if str(exc) == "CART_ITEM_NOT_FOUND":
            fail(404, "CART_ITEM_NOT_FOUND", "Cart item was not found.")
        raise
    return ok(item)


@router.delete("")
def clear_cart(
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Clear the active cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    return ok(store.clear_cart(user, anonymous_id))


@router.post("/merge")
def merge_cart(
    request: Request,
    response: Response,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Merge the anonymous cart into the current user's cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    return ok(store.merge_cart(user, anonymous_id))
