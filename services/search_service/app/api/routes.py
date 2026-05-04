"""Health and service metadata routes."""

from __future__ import annotations

from app.api.envelope import ok
from app.config import settings
from app.indexes.atlas import atlas_indexes

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, object]:
    """Return Search Service readiness metadata."""

    return ok(
        {
            "service": "search",
            "backend": {"runtime": "python", "framework": "fastapi"},
            "database": atlas_indexes.health(),
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "textMaxChars": settings.embedding_text_max_chars,
                "textTemplateVersion": settings.embedding_text_template_version,
            },
            "indexes": atlas_indexes.metadata(),
        }
    )


@router.get("/config")
def config() -> dict[str, object]:
    """Return non-sensitive Search Service configuration choices."""

    return ok(
        {
            "service": {"runtime": "python", "framework": "fastapi"},
            "coreServiceBaseUrl": settings.core_service_base_url,
            "embedding": {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "textMaxChars": settings.embedding_text_max_chars,
                "batchSize": settings.embedding_batch_size,
                "timeoutMs": settings.embedding_timeout_ms,
                "textTemplateVersion": settings.embedding_text_template_version,
            },
            "indexes": atlas_indexes.metadata(),
        }
    )


@router.get("/indexes/definitions")
def index_definitions() -> dict[str, object]:
    """Return required MongoDB Atlas full-text and vector index definitions."""

    return ok(atlas_indexes.definitions())


@router.post("/indexes/ensure")
def ensure_indexes() -> dict[str, object]:
    """Create or update required MongoDB Atlas Search and Vector Search indexes."""

    return ok(atlas_indexes.ensure_indexes())
