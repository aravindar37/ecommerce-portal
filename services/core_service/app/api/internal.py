"""Internal Core Service APIs for trusted service-to-service writes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.envelope import ok
from app.dependencies import require_chat_service
from app.models import AgentToolAuditLogRequest
from app.store import store

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.post("/agent-audit-logs", status_code=status.HTTP_201_CREATED)
def create_agent_audit_log(
    payload: AgentToolAuditLogRequest,
    _: Annotated[bool, Depends(require_chat_service)],
) -> dict[str, object]:
    """Persist one agent tool audit log from Chat Service."""

    return ok(store.add_audit_log(payload.model_dump()))
