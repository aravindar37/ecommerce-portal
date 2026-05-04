"""API envelope and error helpers."""

from __future__ import annotations

import uuid
from typing import Any, NoReturn

from fastapi import HTTPException
from pydantic import BaseModel, Field


class ApiError(BaseModel):
    code: str
    message: str


class ApiEnvelope(BaseModel):
    data: Any | None
    error: ApiError | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a successful API envelope."""

    return {
        "data": data,
        "error": None,
        "meta": {"requestId": uuid.uuid4().hex, **(meta or {})},
    }


def fail(status_code: int, code: str, message: str) -> NoReturn:
    """Raise an HTTPException carrying the standard envelope."""

    raise HTTPException(
        status_code=status_code,
        detail={
            "data": None,
            "error": {"code": code, "message": message},
            "meta": {"requestId": uuid.uuid4().hex},
        },
    )
