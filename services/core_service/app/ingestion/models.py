"""Pydantic models for product ingestion inputs, outputs, and reports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductPrice(BaseModel):
    amount: float
    currency: str
    listAmount: float | None = None


class ProductInventory(BaseModel):
    available: int
    reserved: int = 0
    trackInventory: bool = True


class ProductImage(BaseModel):
    url: str
    alt: str
    sourcePath: str | None = None
    originalUrl: str | None = None
    isPrimary: bool = True
    isLocalFileAvailable: bool


class ProductAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")

    ageGroup: str | None = None
    variantName: str | None = None
    careInstructions: str | None = None
    sizeFit: str | None = None
    styleNote: str | None = None
    articleAttributes: dict[str, Any] = Field(default_factory=dict)


class NormalizedProduct(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(alias="_id")
    source: str
    sourceProductId: str
    slug: str
    title: str
    description: str
    brand: str
    gender: str
    masterCategory: str
    subCategory: str
    articleType: str
    baseColour: str
    colour1: str | None = None
    colour2: str | None = None
    fashionType: str | None = None
    season: str | None = None
    year: int | None = None
    usage: str | None = None
    price: ProductPrice
    inventory: ProductInventory
    images: list[ProductImage]
    attributes: ProductAttributes
    tags: list[str]
    ratingAverage: float
    ratingCount: int
    returnPolicyCode: str
    isActive: bool = True
    createdAt: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DatasetValidation(BaseModel):
    datasetPath: str
    stylesCsvRows: int
    imagesCsvRows: int
    jsonMetadataFiles: int
    localImageFiles: int
    missingLocalImageIds: list[str]
    jsonMissingIds: list[str]
    imagesCsvMissingIds: list[str]
    imageFilesWithoutStyleRows: list[str]
    csvJsonIdMismatches: list[str]


class IngestionReport(BaseModel):
    datasetPath: str
    outputProductsPath: str
    outputReportPath: str
    stylesCsvRows: int
    imagesCsvRows: int
    jsonMetadataFiles: int
    localImageFiles: int
    productsRead: int
    productsProcessed: int
    productsSkipped: int
    productsInserted: int
    productsUpdated: int
    imagesMissing: int
    knownMissingLocalImageIds: list[str]
    csvJsonImageIdMismatches: list[str]
    productsUsingFallbackImage: int
    productsUsingJsonPrice: int
    productsUsingSyntheticPrice: int
    providerModelDimensionsTemplateVersion: str
    durationSeconds: float
    generatedAt: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IngestionPaths(BaseModel):
    dataset: Path
    output_dir: Path
    products_jsonl: Path
    report_json: Path

