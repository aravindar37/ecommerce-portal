"""Client-side user activity event routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.envelope import fail, ok
from app.dependencies import anonymous_id_from_request, current_user_optional
from app.models import ActivityEventRequest
from app.store import Json, store

router = APIRouter(prefix="/api", tags=["activity"])

ALLOWED_EVENT_TYPES = {
    "search_performed",
    "filter_applied",
    "sort_changed",
    "product_card_clicked",
    "product_detail_viewed",
    "cart_item_added",
    "cart_item_updated",
    "cart_item_removed",
    "checkout_started",
    "order_placed",
    "return_requested",
    "support_ticket_created",
    "assistant_opened",
    "assistant_product_recommended",
}

SENSITIVE_KEY_PARTS = ("apikey", "api_key", "secret", "password", "token", "authorization")


def contains_sensitive_metadata(value: Any) -> bool:
    """Detect sensitive-looking metadata keys recursively."""

    if isinstance(value, dict):
        for key, item in value.items():
            lowered = key.lower()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                return True
            if contains_sensitive_metadata(item):
                return True
        return False
    if isinstance(value, list):
        return any(contains_sensitive_metadata(item) for item in value)
    return False


@router.post("/activity-events", status_code=status.HTTP_201_CREATED)
def create_activity_event(
    payload: ActivityEventRequest,
    request: Request,
    response: Response,
    user: Annotated[Json | None, Depends(current_user_optional)],
) -> dict[str, object]:
    """Capture a validated client-side activity event."""

    if payload.eventType not in ALLOWED_EVENT_TYPES:
        fail(400, "INVALID_ACTIVITY_EVENT", "Activity event type is not supported.")
    if contains_sensitive_metadata(payload.metadata):
        fail(400, "SENSITIVE_ACTIVITY_METADATA", "Activity metadata contains sensitive fields.")
    anonymous_id = anonymous_id_from_request(request, response)
    event = store.add_activity(payload.eventType, payload.metadata, user, anonymous_id)
    return ok(event)
