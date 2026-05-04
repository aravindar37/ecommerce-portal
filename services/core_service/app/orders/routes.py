"""Order history routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.envelope import fail, ok
from app.dependencies import current_user_required
from app.store import Json, store

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(user: Annotated[Json, Depends(current_user_required)]) -> dict[str, object]:
    """Return orders owned by the current user."""

    return ok({"items": store.user_orders(user)})


@router.get("/{order_number}")
def get_order(order_number: str, user: Annotated[Json, Depends(current_user_required)]) -> dict[str, object]:
    """Return one owned order by ID or order number."""

    order = store.find_order_for_user(user, order_number)
    if not order:
        fail(404, "ORDER_NOT_FOUND", "Order was not found.")
    return ok(order)
