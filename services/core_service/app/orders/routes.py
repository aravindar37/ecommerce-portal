"""Order history routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.envelope import fail, ok
from app.dependencies import current_user_or_on_behalf
from app.models import OrderUpdateRequest
from app.store import Json, store

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(user: Annotated[Json, Depends(current_user_or_on_behalf)]) -> dict[str, object]:
    """Return orders owned by the current user."""

    return ok({"items": store.user_orders(user)})


@router.get("/{order_number}/payment")
def get_payment(order_number: str, user: Annotated[Json, Depends(current_user_or_on_behalf)]) -> dict[str, object]:
    """Return the compact, safe-for-voice payment summary for one order."""

    try:
        return ok(store.payment_details(user, order_number))
    except ValueError:
        fail(404, "ORDER_NOT_FOUND", "Order was not found.")


@router.patch("/{order_number}")
def update_order(
    order_number: str,
    payload: OrderUpdateRequest,
    user: Annotated[Json, Depends(current_user_or_on_behalf)],
) -> dict[str, object]:
    """Cancel pre-dispatch orders or update their shipping address."""

    try:
        return ok(store.update_order(user, order_number, payload.action, payload.shippingAddress.model_dump() if payload.shippingAddress else None))
    except ValueError as exc:
        if str(exc) == "ORDER_NOT_FOUND":
            fail(404, "ORDER_NOT_FOUND", "Order was not found.")
        if str(exc) in {"ORDER_UPDATE_NOT_ALLOWED", "SHIPPING_ADDRESS_REQUIRED", "UNSUPPORTED_ORDER_UPDATE"}:
            fail(409, str(exc), "That order update is not allowed in its current state.")
        raise


@router.get("/{order_number}")
def get_order(order_number: str, user: Annotated[Json, Depends(current_user_or_on_behalf)]) -> dict[str, object]:
    """Return one owned order by ID or order number."""

    order = store.find_order_for_user(user, order_number)
    if not order:
        fail(404, "ORDER_NOT_FOUND", "Order was not found.")
    return ok(order)
