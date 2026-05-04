"""Pydantic request models for Search Service APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=10, ge=1, le=100)
    page: int = Field(default=1, ge=1)


class HybridSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)
    page: int = Field(default=1, ge=1)
