"""Pydantic request models for Chat Service APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ShoppingSessionRequest(BaseModel):
    entryPoint: str = Field(min_length=1)
    productId: str | None = None
    cartAware: bool = False


class ShoppingMessageRequest(BaseModel):
    sessionId: str
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class SupportSessionRequest(BaseModel):
    orderId: str | None = None


class SupportMessageRequest(BaseModel):
    sessionId: str
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class ConfirmActionRequest(BaseModel):
    actionId: str
    confirm: bool
    reason: str | None = None
    condition: str | None = None
    resolution: str | None = None
