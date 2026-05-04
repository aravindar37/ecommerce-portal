"""Checkout routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.envelope import fail, ok
from app.dependencies import anonymous_id_from_request, current_user_required
from app.models import CheckoutQuoteRequest, PlaceOrderRequest
from app.store import Json, store

router = APIRouter(prefix="/api/checkout", tags=["checkout"])


@router.post("/quote")
def quote(
    payload: CheckoutQuoteRequest,
    request: Request,
    response: Response,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Calculate server-side checkout totals in INR."""

    anonymous_id = anonymous_id_from_request(request, response)
    return ok(store.checkout_quote(user, anonymous_id, payload.shippingAddress.model_dump()))


@router.post("/place-order", status_code=status.HTTP_201_CREATED)
def place_order(
    payload: PlaceOrderRequest,
    request: Request,
    response: Response,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Place a demo order using the authenticated user's active cart."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        order = store.place_order(user, anonymous_id, payload.shippingAddress.model_dump(), payload.paymentMethod)
    except ValueError as exc:
        if str(exc) == "CART_EMPTY":
            fail(400, "CART_EMPTY", "Cart is empty.")
        raise
    return ok(order)
