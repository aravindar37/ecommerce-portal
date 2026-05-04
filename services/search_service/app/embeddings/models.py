"""Pydantic models for product embedding generation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProductEmbeddingMetadata(BaseModel):
    gender: str | None = None
    masterCategory: str | None = None
    subCategory: str | None = None
    articleType: str | None = None
    baseColour: str | None = None
    season: str | None = None
    usage: str | None = None
    priceAmount: float | None = None
    isActive: bool = True


class ProductEmbeddingRecord(BaseModel):
    productId: str
    sourceProductId: str
    provider: str
    model: str
    dimensions: int
    textTemplateVersion: str
    embeddingTextHash: str
    embedding: list[float]
    metadata: ProductEmbeddingMetadata
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EmbeddingRunReport(BaseModel):
    inputProductsPath: str
    outputEmbeddingsPath: str
    provider: str
    model: str
    dimensions: int
    textTemplateVersion: str
    productsRead: int
    productsSkipped: int
    embeddingsGenerated: int
    dryRun: bool
    durationSeconds: float
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
