"""Load normalized product JSONL into MongoDB Atlas."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


class ProductLoadError(Exception):
    """Raised when product loading cannot complete."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read normalized product JSONL documents."""

    if not path.exists():
        raise ProductLoadError(f"Products JSONL does not exist: {path}")
    products: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    raise ProductLoadError(f"Expected product object at {path}:{line_number}")
                products.append(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductLoadError(f"Unable to read products JSONL {path}: {exc}") from exc
    return products


def load_products(products_path: Path, mongodb_uri: str, mongodb_db: str, batch_size: int) -> dict[str, int]:
    """Upsert normalized products into MongoDB Atlas products collection."""

    if not mongodb_uri.strip():
        raise ProductLoadError("MONGODB_URI is required")
    if batch_size <= 0:
        raise ProductLoadError("batch size must be greater than zero")
    try:
        import certifi
        from pymongo import MongoClient, UpdateOne
    except ImportError as exc:
        raise ProductLoadError("pymongo and certifi must be installed to load products into MongoDB Atlas") from exc
    products = read_jsonl(products_path)
    inserted_or_updated = 0
    skipped = 0
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
    collection = client[mongodb_db]["products"]
    collection.create_index([("source", 1), ("sourceProductId", 1)], unique=True)
    collection.create_index("slug", unique=True)
    collection.create_index([("gender", 1), ("masterCategory", 1), ("subCategory", 1), ("articleType", 1)])
    collection.create_index([("baseColour", 1), ("usage", 1), ("isActive", 1)])
    operations: list[Any] = []
    for product in products:
        source = product.get("source")
        source_product_id = product.get("sourceProductId")
        if not isinstance(source, str) or not isinstance(source_product_id, str):
            skipped += 1
            continue
        operations.append(
            UpdateOne(
                {"source": source, "sourceProductId": source_product_id},
                {"$set": product},
                upsert=True,
            )
        )
        if len(operations) >= batch_size:
            collection.bulk_write(operations, ordered=False)
            inserted_or_updated += len(operations)
            operations = []
    if operations:
        collection.bulk_write(operations, ordered=False)
        inserted_or_updated += len(operations)
    return {"productsRead": len(products), "productsLoaded": inserted_or_updated, "productsSkipped": skipped}


def positive_int(value: str) -> int:
    """Argparse parser for positive integers."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""

    parser = argparse.ArgumentParser(description="Load normalized product JSONL into MongoDB Atlas.")
    parser.add_argument("--products-jsonl", type=Path, default=Path(os.getenv("PRODUCTS_JSONL_PATH", "./artifacts/ingestion/products.jsonl")))
    parser.add_argument("--mongodb-uri", default=os.getenv("MONGODB_URI", ""))
    parser.add_argument("--mongodb-db", default=os.getenv("MONGODB_DB", "ecommerce_demo"))
    parser.add_argument("--batch-size", type=positive_int, default=int(os.getenv("PRODUCT_LOAD_BATCH_SIZE", "500")))
    return parser


def main() -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        result = load_products(
            products_path=args.products_jsonl,
            mongodb_uri=args.mongodb_uri,
            mongodb_db=args.mongodb_db,
            batch_size=args.batch_size,
        )
    except ProductLoadError as exc:
        parser.exit(status=1, message=f"product load failed: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
