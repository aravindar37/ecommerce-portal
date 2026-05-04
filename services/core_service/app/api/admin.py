"""Admin, health, and test-support routes for Core Service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.envelope import ok
from app.config import settings
from app.database import mongo
from app.dependencies import redact_sensitive, require_admin
from app.store import store

router = APIRouter(prefix="/api", tags=["api"])


class SeedRequest(BaseModel):
    products: str | None = None
    users: bool = False
    orders: bool = False
    embeddings: bool = False


@router.get("/health")
def health() -> dict[str, object]:
    """Return Core Service health metadata."""

    return ok(
        {
            "service": "core",
            "backend": {"runtime": "python", "framework": "fastapi"},
            "database": mongo.health(),
            "mcp": {
                "enabled": settings.codex_mcp_enabled,
                "ready": settings.codex_mcp_enabled,
                "transport": settings.codex_mcp_transport,
            },
        }
    )


@router.post("/test/reset")
def reset_data(_: Annotated[bool, Depends(require_admin)]) -> dict[str, object]:
    """Reset local Core Service state."""

    store.reset()
    return ok({"reset": True})


@router.post("/test/seed")
def seed_data(payload: SeedRequest, _: Annotated[bool, Depends(require_admin)]) -> dict[str, object]:
    """Seed local Core Service state for tests and demos."""

    store.seed(payload.products, payload.users, payload.orders, payload.embeddings)
    return ok({"seeded": True})


@router.get("/admin/config")
def admin_config(_: Annotated[bool, Depends(require_admin)]) -> dict[str, object]:
    """Return non-sensitive runtime configuration choices."""

    config = {
        "services": {
            "core": {"runtime": "python", "framework": "fastapi"},
            "search": {"runtime": "python", "framework": "fastapi"},
            "chat": {"runtime": "python", "framework": "fastapi"},
        },
        "llm": {"provider": settings.llm_provider, "model": settings.llm_model},
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
        "imageStorage": {"provider": "local_filesystem", "localRoot": str(settings.product_image_local_root)},
        "checkout": {"currency": settings.demo_currency},
        "auth": {"googleEnabled": settings.auth_google_enabled},
        "codexMcp": {"enabled": settings.codex_mcp_enabled, "transport": settings.codex_mcp_transport},
        "admin": {"seedUserConfigured": bool(settings.admin_seed_email)},
        "serviceBoundaries": {
            "searchOwnsProductSearch": True,
            "chatUsesCoreAndSearchApis": True,
        },
    }
    return ok(redact_sensitive(config))


@router.get("/admin/ingestion/status")
def ingestion_status(_: Annotated[bool, Depends(require_admin)]) -> dict[str, object]:
    """Return local dataset ingestion and embedding status."""

    return ok(store.ingestion_status())


@router.get("/admin/activity-events")
def activity_events(
    _: Annotated[bool, Depends(require_admin)],
    event_type: Annotated[str | None, Query(alias="eventType")] = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, object]:
    """Return recent user activity events."""

    return ok({"items": redact_sensitive(store.list_activity_events(event_type, limit))})


@router.get("/admin/audit-logs")
def audit_logs(
    _: Annotated[bool, Depends(require_admin)],
    agent_type: Annotated[str | None, Query(alias="agentType")] = None,
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, object]:
    """Return recent agent tool audit logs."""

    return ok({"items": redact_sensitive(store.list_audit_logs(agent_type, limit))})
