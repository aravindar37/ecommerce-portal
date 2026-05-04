"""Search Service ASGI entrypoint."""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - startup guard
    raise RuntimeError("fastapi must be installed to run Search Service") from exc

from app.api.errors import install_error_handlers
from app.api.routes import router as api_router
from app.config import settings
from app.embeddings.routes import router as embeddings_router
from app.search.routes import router as search_router
from app.security import InMemoryRateLimitMiddleware, parse_cors_origins

app = FastAPI(title="Codex Ecommerce Search Service")
install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    InMemoryRateLimitMiddleware,
    path_prefixes=("/api/products", "/api/search", "/api/facets"),
    requests_per_minute=settings.rate_limit_search_per_minute,
)

app.include_router(api_router)
app.include_router(embeddings_router)
app.include_router(search_router)
