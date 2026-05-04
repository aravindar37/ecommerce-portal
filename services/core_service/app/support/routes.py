"""Support ticket routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.envelope import fail, ok
from app.dependencies import anonymous_id_from_request, current_user_required
from app.models import AddTicketMessageRequest, CreateSupportTicketRequest
from app.store import Json, store

router = APIRouter(prefix="/api/support/tickets", tags=["support"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: CreateSupportTicketRequest,
    request: Request,
    response: Response,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Create a support ticket."""

    anonymous_id = anonymous_id_from_request(request, response)
    try:
        ticket = store.create_ticket(user, anonymous_id, payload.model_dump())
    except ValueError as exc:
        if str(exc) == "ORDER_NOT_FOUND":
            fail(404, "ORDER_NOT_FOUND", "Order was not found.")
        raise
    return ok(ticket)


@router.get("")
def list_tickets(user: Annotated[Json, Depends(current_user_required)]) -> dict[str, object]:
    """Return support tickets owned by the current user."""

    return ok({"items": store.user_tickets(user)})


@router.get("/{ticket_number}")
def get_ticket(ticket_number: str, user: Annotated[Json, Depends(current_user_required)]) -> dict[str, object]:
    """Return one owned support ticket."""

    ticket = store.find_ticket_for_user(user, ticket_number)
    if not ticket:
        fail(404, "TICKET_NOT_FOUND", "Support ticket was not found.")
    return ok(ticket)


@router.post("/{ticket_number}/messages", status_code=status.HTTP_201_CREATED)
def add_message(
    ticket_number: str,
    payload: AddTicketMessageRequest,
    user: Annotated[Json, Depends(current_user_required)],
) -> dict[str, object]:
    """Append a customer message to an owned support ticket."""

    try:
        message = store.add_ticket_message(user, ticket_number, payload.message)
    except ValueError as exc:
        if str(exc) == "TICKET_NOT_FOUND":
            fail(404, "TICKET_NOT_FOUND", "Support ticket was not found.")
        raise
    return ok(message)
