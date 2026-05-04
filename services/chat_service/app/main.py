"""Chat Service ASGI entrypoint."""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - startup guard
    raise RuntimeError("fastapi must be installed to run Chat Service") from exc

from app.api.errors import install_error_handlers
from app.api.routes import router as api_router
from app.config import settings
from app.database import mongo
from app.observability import DebugRequestLoggingMiddleware, configure_logging
from app.security import InMemoryRateLimitMiddleware, parse_cors_origins

configure_logging()
app = FastAPI(title="Codex Ecommerce Chat Service")
install_error_handlers(app)
app.add_middleware(DebugRequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    InMemoryRateLimitMiddleware,
    path_prefixes=("/api/assistant",),
    requests_per_minute=settings.rate_limit_chat_per_minute,
)
app.include_router(api_router)


@app.on_event("startup")
def ensure_database_indexes() -> None:
    """Ensure MongoDB Atlas indexes exist when chat persistence is configured."""

    mongo.ensure_indexes()
