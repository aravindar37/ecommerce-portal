"""Chat Service API envelope helpers."""

from __future__ import annotations

import uuid
from typing import Any, NoReturn

from fastapi import HTTPException


def ok(data: Any, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a standard success envelope."""

    return {"data": data, "error": None, "meta": {"requestId": uuid.uuid4().hex, **(meta or {})}}


def fail(status_code: int, code: str, message: str) -> NoReturn:
    """Raise a standard error envelope."""

    raise HTTPException(
        status_code=status_code,
        detail={"data": None, "error": {"code": code, "message": message}, "meta": {"requestId": uuid.uuid4().hex}},
    )
