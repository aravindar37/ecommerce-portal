"""Core Service ASGI entrypoint."""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as exc:  # pragma: no cover - startup guard
    raise RuntimeError("fastapi must be installed to run Core Service") from exc

from app.api.activity import router as activity_router
from app.api.admin import router as admin_router
from app.api.errors import install_error_handlers
from app.api.internal import router as internal_router
from app.auth.routes import router as auth_router
from app.carts.routes import router as carts_router
from app.checkout.routes import router as checkout_router
from app.database import mongo
from app.orders.routes import router as orders_router
from app.products.routes import router as products_router
from app.returns.routes import router as returns_router
from app.config import settings
from app.security import InMemoryRateLimitMiddleware, parse_cors_origins
from app.support.routes import router as support_router

app = FastAPI(title="Codex Ecommerce Core Service")
install_error_handlers(app)


@app.on_event("startup")
def ensure_database_indexes() -> None:
    """Ensure MongoDB indexes exist when Atlas persistence is configured."""

    mongo.ensure_indexes()


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    InMemoryRateLimitMiddleware,
    path_prefixes=("/api/auth/login",),
    requests_per_minute=settings.rate_limit_auth_per_minute,
    counted_status_codes=(401,),
)

app.include_router(admin_router)
app.include_router(internal_router)
app.include_router(activity_router)
app.include_router(auth_router)
app.include_router(products_router)
app.include_router(carts_router)
app.include_router(checkout_router)
app.include_router(orders_router)
app.include_router(returns_router)
app.include_router(support_router)
