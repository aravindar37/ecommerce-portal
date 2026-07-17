"""Embedding status routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.api.envelope import ok
from app.config import settings

router = APIRouter(prefix="/api/embeddings", tags=["embeddings"])


def count_jsonl(path: Path) -> int:
    """Count non-empty JSONL rows."""

    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def first_embedding_metadata(path: Path) -> dict[str, Any]:
    """Read metadata from the first embedding record when available."""

    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


@router.get("/status")
def embedding_status() -> dict[str, object]:
    """Return generated embedding metadata."""

    if settings.embedding_provider == "mongodb_atlas_autoembed":
        return ok(
            {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimensions": settings.embedding_dimensions,
                "textTemplateVersion": None,
                "vectorIndexName": settings.mongodb_vector_index_name,
                "embeddingsGenerated": None,
                "embeddingMode": "atlas_automated",
            }
        )
    first = first_embedding_metadata(settings.product_embeddings_jsonl_path)
    return ok(
        {
            "provider": first.get("provider") or settings.embedding_provider,
            "model": first.get("model") or settings.embedding_model,
            "dimensions": int(first.get("dimensions") or settings.embedding_dimensions),
            "textTemplateVersion": first.get("textTemplateVersion") or settings.embedding_text_template_version,
            "vectorIndexName": settings.mongodb_vector_index_name,
            "embeddingsGenerated": count_jsonl(settings.product_embeddings_jsonl_path),
        }
    )
