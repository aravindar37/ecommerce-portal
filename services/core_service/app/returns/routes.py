"""Return request routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.envelope import fail, ok
from app.dependencies import anonymous_id_from_request, current_user_or_on_behalf
from app.models import CreateReturnRequest, ReturnEligibilityRequest
from app.store import Json, store

router = APIRouter(prefix="/api/returns", tags=["returns"])


@router.post("/check-eligibility")
def check_eligibility(
    payload: ReturnEligibilityRequest,
    user: Annotated[Json, Depends(current_user_or_on_behalf)],
) -> dict[str, object]:
    """Check whether an order item can be returned."""

    try:
        eligibility = store.check_return_eligibility(user, payload.orderId, payload.orderItemId)
    except ValueError as exc:
        code = str(exc)
        if code == "ORDER_NOT_FOUND":
            fail(404, "ORDER_NOT_FOUND", "Order was not found.")
        if code == "ORDER_ITEM_NOT_FOUND":
            fail(404, "ORDER_ITEM_NOT_FOUND", "Order item was not found.")
        raise
    return ok(eligibility)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_return(
    payload: CreateReturnRequest,
    request: Request,
    response: Response,
    user: Annotated[Json, Depends(current_user_or_on_behalf)],
) -> dict[str, object]:
    """Create a customer return request."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        return_request = store.create_return(user, anonymous_id, payload.orderId, [item.model_dump() for item in payload.items])
    except ValueError as exc:
        if str(exc) == "ORDER_NOT_FOUND":
            fail(404, "ORDER_NOT_FOUND", "Order was not found.")
        raise
    return ok(return_request)
