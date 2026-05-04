"""Runtime configuration for Core Service utilities."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class CoreSettings(BaseModel):
    """Environment-backed settings used by the ingestion pipeline."""

    dataset_name: str = Field(default="kaggle-fashion-product-images")
    dataset_path: Path = Field(default=Path("./dataset"))
    product_image_public_base_url: str = Field(default="/product-images")
    ingestion_output_dir: Path = Field(default=Path("./artifacts/ingestion"))
    demo_currency: str = Field(default="INR")

    @classmethod
    def from_env(cls) -> "CoreSettings":
        """Build settings from environment variables with spec-defined defaults."""

        return cls(
            dataset_name=os.getenv("DATASET_NAME", "kaggle-fashion-product-images"),
            dataset_path=Path(os.getenv("DATASET_PATH", "./dataset")),
            product_image_public_base_url=os.getenv("PRODUCT_IMAGE_PUBLIC_BASE_URL", "/product-images"),
            ingestion_output_dir=Path(os.getenv("INGESTION_OUTPUT_DIR", "./artifacts/ingestion")),
            demo_currency=os.getenv("DEMO_CURRENCY", "INR"),
        )

