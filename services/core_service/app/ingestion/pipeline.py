"""Product ingestion pipeline for the local fashion dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from app.ingestion.config import CoreSettings
from app.ingestion.models import (
    DatasetValidation,
    IngestionPaths,
    IngestionReport,
    NormalizedProduct,
    ProductAttributes,
    ProductImage,
    ProductInventory,
    ProductPrice,
)


class IngestionError(Exception):
    """Raised when ingestion cannot continue safely."""


class TextExtractor(HTMLParser):
    """Small HTML-to-text extractor for Myntra descriptor snippets."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "li"}:
            self._parts.append(" ")

    def get_text(self) -> str:
        return normalize_space(" ".join(self._parts))


def normalize_space(value: str) -> str:
    """Collapse repeated whitespace."""

    return re.sub(r"\s+", " ", value).strip()


def clean_text(value: Any) -> str:
    """Convert HTML or primitive descriptor values into safe display/index text."""

    if value is None:
        return ""
    raw = html.unescape(str(value))
    parser = TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:
        raise IngestionError(f"Failed to sanitize descriptor text: {exc}") from exc
    text = parser.get_text() or normalize_space(re.sub(r"<[^>]+>", " ", raw))
    text = html.unescape(text)
    return text


def deterministic_int(product_id: str, minimum: int, maximum: int, salt: str) -> int:
    """Generate a stable integer in an inclusive range."""

    if minimum > maximum:
        raise ValueError("minimum must be less than or equal to maximum")
    digest = hashlib.sha256(f"{salt}:{product_id}".encode("utf-8")).hexdigest()
    span = maximum - minimum + 1
    return minimum + (int(digest[:12], 16) % span)


def deterministic_float(product_id: str, minimum: float, maximum: float, salt: str, decimals: int) -> float:
    """Generate a stable float in a range."""

    raw = deterministic_int(product_id, 0, 10_000, salt) / 10_000
    return round(minimum + ((maximum - minimum) * raw), decimals)


def slugify(value: str) -> str:
    """Create a URL-safe slug component."""

    lowered = value.lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", lowered)
    return normalized.strip("-") or "product"


def stable_product_object_id(source_product_id: str) -> str:
    """Create a stable placeholder object ID for JSONL output."""

    return hashlib.sha256(f"product:{source_product_id}".encode("utf-8")).hexdigest()[:24]


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV file into dictionaries."""

    if not path.exists():
        raise IngestionError(f"Missing CSV file: {path}")
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except OSError as exc:
        raise IngestionError(f"Unable to read CSV file {path}: {exc}") from exc


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        raise IngestionError(f"Unable to read JSON file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise IngestionError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IngestionError(f"Expected JSON object in {path}")
    return payload


def get_nested(payload: dict[str, Any], *keys: str) -> Any:
    """Safely fetch a nested dictionary value."""

    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def category_name(value: Any) -> str:
    """Extract category display text from JSON category object or primitive."""

    if isinstance(value, dict):
        raw = value.get("typeName")
        return normalize_space(str(raw)) if raw else ""
    return normalize_space(str(value)) if value is not None else ""


def parse_int(value: Any) -> int | None:
    """Parse an integer-like value."""

    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    """Parse a float-like value."""

    if value is None or value == "":
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def descriptor_value(data: dict[str, Any], descriptor_name: str) -> str:
    """Read and sanitize a product descriptor value."""

    raw = get_nested(data, "productDescriptors", descriptor_name, "value")
    return clean_text(raw)


def fallback_description(row: dict[str, str], data: dict[str, Any]) -> str:
    """Build deterministic fallback description when JSON descriptors are absent."""

    title = row.get("productDisplayName") or str(data.get("productDisplayName") or "Product")
    brand = str(data.get("brandName") or "Demo Brand")
    category = row.get("articleType") or category_name(data.get("articleType")) or "fashion product"
    return normalize_space(f"{title} by {brand}. A {category} from the local fashion product dataset.")


def image_records(
    product_id: str,
    title: str,
    dataset_path: Path,
    public_base_url: str,
    images_by_id: dict[str, str],
    data: dict[str, Any],
) -> tuple[list[ProductImage], bool]:
    """Create image records and indicate whether fallback metadata is used."""

    image_path = dataset_path / "images" / f"{product_id}.jpg"
    original_url = images_by_id.get(product_id) or str(get_nested(data, "styleImages", "default", "imageURL") or "")
    local_available = image_path.exists()
    if local_available:
        return (
            [
                ProductImage(
                    url=f"{public_base_url.rstrip('/')}/{product_id}.jpg",
                    alt=title,
                    sourcePath=f"images/{product_id}.jpg",
                    originalUrl=original_url or None,
                    isLocalFileAvailable=True,
                )
            ],
            False,
        )
    return (
        [
            ProductImage(
                url=f"{public_base_url.rstrip('/')}/fallback.jpg",
                alt=title,
                sourcePath=None,
                originalUrl=original_url or None,
                isLocalFileAvailable=False,
            )
        ],
        True,
    )


def return_policy_code(data: dict[str, Any]) -> str:
    """Derive a demo return policy code from dataset return/exchange flags."""

    article_type = data.get("articleType")
    is_returnable = bool(article_type.get("isReturnable")) if isinstance(article_type, dict) else True
    is_exchangeable = bool(article_type.get("isExchangeable")) if isinstance(article_type, dict) else True
    if is_returnable:
        return "standard-30-day"
    if is_exchangeable:
        return "exchange-only"
    return "final-sale"


def build_tags(*values: Any) -> list[str]:
    """Create stable lowercase search tags from product fields."""

    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            iterable: Iterable[Any] = value.values()
        elif isinstance(value, (list, tuple, set)):
            iterable = value
        else:
            iterable = [value]
        for item in iterable:
            text = normalize_space(str(item)).lower()
            if not text or text in {"na", "none", "null"} or text in seen:
                continue
            seen.add(text)
            tags.append(text)
    return tags


def normalize_product(
    row: dict[str, str],
    data: dict[str, Any],
    dataset_path: Path,
    public_base_url: str,
    images_by_id: dict[str, str],
    currency: str,
) -> tuple[NormalizedProduct, bool, bool]:
    """Normalize one CSV/JSON product pair into the product document shape."""

    product_id = row["id"]
    title = normalize_space(row.get("productDisplayName") or str(data.get("productDisplayName") or f"Product {product_id}"))
    brand = normalize_space(str(data.get("brandName") or f"Demo Brand {deterministic_int(product_id, 1, 12, 'brand')}"))
    description = descriptor_value(data, "description") or fallback_description(row, data)
    care = descriptor_value(data, "materials_care_desc") or "Follow the care guidance in the product description."
    size_fit = descriptor_value(data, "size_fit_desc")
    style_note = descriptor_value(data, "style_note")
    json_price = parse_float(data.get("price"))
    json_discounted_price = parse_float(data.get("discountedPrice"))
    amount = json_discounted_price or json_price
    used_json_price = amount is not None
    used_synthetic_price = amount is None
    if amount is None:
        amount = float(deterministic_int(product_id, 499, 7999, "price"))
    master_category = normalize_space(row.get("masterCategory") or category_name(data.get("masterCategory")))
    sub_category = normalize_space(row.get("subCategory") or category_name(data.get("subCategory")))
    article_type = normalize_space(row.get("articleType") or category_name(data.get("articleType")))
    base_colour = normalize_space(row.get("baseColour") or str(data.get("baseColour") or ""))
    images, used_fallback_image = image_records(product_id, title, dataset_path, public_base_url, images_by_id, data)
    tags = build_tags(
        row.get("gender") or data.get("gender"),
        base_colour,
        data.get("colour1"),
        data.get("colour2"),
        row.get("usage") or data.get("usage"),
        master_category,
        sub_category,
        article_type,
        brand,
        data.get("fashionType"),
        data.get("articleAttributes") if isinstance(data.get("articleAttributes"), dict) else {},
    )
    rating_average = deterministic_float(product_id, 3.6, 4.9, "rating-average", 1)
    rating_count = deterministic_int(product_id, 12, 600, "rating-count")
    inventory = ProductInventory(
        available=deterministic_int(product_id, 5, 125, "inventory"),
        reserved=0,
        trackInventory=True,
    )
    product = NormalizedProduct(
        _id=stable_product_object_id(product_id),
        source="kaggle-fashion-product-images",
        sourceProductId=product_id,
        slug=f"{slugify(title)}-{product_id}",
        title=title,
        description=description,
        brand=brand,
        gender=normalize_space(row.get("gender") or str(data.get("gender") or "")),
        masterCategory=master_category,
        subCategory=sub_category,
        articleType=article_type,
        baseColour=base_colour,
        colour1=normalize_space(str(data.get("colour1") or "")) or None,
        colour2=normalize_space(str(data.get("colour2") or "")) or None,
        fashionType=normalize_space(str(data.get("fashionType") or "")) or None,
        season=normalize_space(row.get("season") or str(data.get("season") or "")) or None,
        year=parse_int(row.get("year") or data.get("year")),
        usage=normalize_space(row.get("usage") or str(data.get("usage") or "")) or None,
        price=ProductPrice(amount=amount, listAmount=json_price, currency=currency),
        inventory=inventory,
        images=images,
        attributes=ProductAttributes(
            ageGroup=normalize_space(str(data.get("ageGroup") or "")) or None,
            variantName=normalize_space(str(data.get("variantName") or "")) or None,
            careInstructions=care or None,
            sizeFit=size_fit or None,
            styleNote=style_note or None,
            articleAttributes=data.get("articleAttributes") if isinstance(data.get("articleAttributes"), dict) else {},
        ),
        tags=tags,
        ratingAverage=rating_average,
        ratingCount=rating_count,
        returnPolicyCode=return_policy_code(data),
        isActive=True,
    )
    return product, used_fallback_image, used_json_price and not used_synthetic_price


def validate_dataset(dataset_path: Path, styles_rows: list[dict[str, str]], images_rows: list[dict[str, str]]) -> DatasetValidation:
    """Validate required structure and collect source-count metadata."""

    required = [dataset_path / "styles.csv", dataset_path / "images.csv", dataset_path / "images", dataset_path / "styles"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise IngestionError(f"Dataset is missing required paths: {', '.join(missing)}")
    style_ids = {row["id"] for row in styles_rows if row.get("id")}
    image_csv_ids = {Path(row["filename"]).stem for row in images_rows if row.get("filename")}
    image_file_ids = {path.stem for path in (dataset_path / "images").glob("*.jpg")}
    json_file_ids = {path.stem for path in (dataset_path / "styles").glob("*.json")}
    return DatasetValidation(
        datasetPath=str(dataset_path),
        stylesCsvRows=len(styles_rows),
        imagesCsvRows=len(images_rows),
        jsonMetadataFiles=len(json_file_ids),
        localImageFiles=len(image_file_ids),
        missingLocalImageIds=sorted(style_ids - image_file_ids),
        jsonMissingIds=sorted(style_ids - json_file_ids),
        imagesCsvMissingIds=sorted(style_ids - image_csv_ids),
        imageFilesWithoutStyleRows=sorted(image_file_ids - style_ids),
        csvJsonIdMismatches=[],
    )


def build_paths(dataset_path: Path, output_dir: Path) -> IngestionPaths:
    """Build output paths and create the output directory."""

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IngestionError(f"Unable to create ingestion output directory {output_dir}: {exc}") from exc
    return IngestionPaths(
        dataset=dataset_path,
        output_dir=output_dir,
        products_jsonl=output_dir / "products.jsonl",
        report_json=output_dir / "ingestion-report.json",
    )


def run_ingestion(dataset_path: Path, output_dir: Path, public_base_url: str, currency: str, limit: int | None) -> IngestionReport:
    """Run the complete local ingestion pipeline and write output artifacts."""

    started = time.perf_counter()
    styles_rows = read_csv(dataset_path / "styles.csv")
    images_rows = read_csv(dataset_path / "images.csv")
    validation = validate_dataset(dataset_path, styles_rows, images_rows)
    images_by_id = {
        Path(row["filename"]).stem: row.get("link", "")
        for row in images_rows
        if row.get("filename")
    }
    paths = build_paths(dataset_path, output_dir)
    products_processed = 0
    products_skipped = 0
    fallback_images = 0
    json_price_count = 0
    synthetic_price_count = 0
    id_mismatches: list[str] = []
    rows_to_process = styles_rows if limit is None else styles_rows[:limit]
    try:
        with paths.products_jsonl.open("w", encoding="utf-8") as handle:
            for row in rows_to_process:
                product_id = row.get("id")
                if not product_id:
                    products_skipped += 1
                    continue
                json_path = dataset_path / "styles" / f"{product_id}.json"
                if not json_path.exists():
                    products_skipped += 1
                    continue
                payload = load_json(json_path)
                data = payload.get("data")
                if not isinstance(data, dict):
                    products_skipped += 1
                    continue
                json_id = str(data.get("id") or "")
                if json_id and json_id != product_id:
                    id_mismatches.append(f"{product_id}:json:{json_id}")
                try:
                    product, used_fallback_image, used_json_price = normalize_product(
                        row=row,
                        data=data,
                        dataset_path=dataset_path,
                        public_base_url=public_base_url,
                        images_by_id=images_by_id,
                        currency=currency,
                    )
                except (ValidationError, IngestionError, ValueError) as exc:
                    products_skipped += 1
                    id_mismatches.append(f"{product_id}:normalize_error:{exc}")
                    continue
                fallback_images += 1 if used_fallback_image else 0
                json_price_count += 1 if used_json_price else 0
                synthetic_price_count += 0 if used_json_price else 1
                handle.write(product.model_dump_json(by_alias=True))
                handle.write("\n")
                products_processed += 1
    except OSError as exc:
        raise IngestionError(f"Unable to write products output {paths.products_jsonl}: {exc}") from exc
    all_mismatches = [
        *validation.jsonMissingIds,
        *validation.imagesCsvMissingIds,
        *validation.imageFilesWithoutStyleRows,
        *id_mismatches,
    ]
    report = IngestionReport(
        datasetPath=str(dataset_path),
        outputProductsPath=str(paths.products_jsonl),
        outputReportPath=str(paths.report_json),
        stylesCsvRows=validation.stylesCsvRows,
        imagesCsvRows=validation.imagesCsvRows,
        jsonMetadataFiles=validation.jsonMetadataFiles,
        localImageFiles=validation.localImageFiles,
        productsRead=len(rows_to_process),
        productsProcessed=products_processed,
        productsSkipped=products_skipped,
        productsInserted=0,
        productsUpdated=0,
        imagesMissing=len(validation.missingLocalImageIds),
        knownMissingLocalImageIds=validation.missingLocalImageIds,
        csvJsonImageIdMismatches=all_mismatches,
        productsUsingFallbackImage=fallback_images,
        productsUsingJsonPrice=json_price_count,
        productsUsingSyntheticPrice=synthetic_price_count,
        providerModelDimensionsTemplateVersion="pending-search-service-embedding-generation",
        durationSeconds=round(time.perf_counter() - started, 3),
    )
    try:
        paths.report_json.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise IngestionError(f"Unable to write ingestion report {paths.report_json}: {exc}") from exc
    return report


def positive_int(value: str) -> int:
    """Argparse parser for positive integers."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    settings = CoreSettings.from_env()
    parser = argparse.ArgumentParser(description="Ingest local fashion products into normalized JSONL artifacts.")
    parser.add_argument("--dataset", type=Path, default=settings.dataset_path, help="Dataset directory containing styles.csv, images.csv, images/, and styles/.")
    parser.add_argument("--output-dir", type=Path, default=settings.ingestion_output_dir, help="Directory for products.jsonl and ingestion-report.json.")
    parser.add_argument("--public-image-base-url", default=settings.product_image_public_base_url, help="Public URL prefix for locally served product images.")
    parser.add_argument("--currency", default=settings.demo_currency, help="Currency code to assign to product prices.")
    parser.add_argument("--limit", type=positive_int, default=None, help="Optional number of products to process for validation runs.")
    return parser


def main() -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args()
    try:
        report = run_ingestion(
            dataset_path=args.dataset,
            output_dir=args.output_dir,
            public_base_url=args.public_image_base_url,
            currency=args.currency,
            limit=args.limit,
        )
    except IngestionError as exc:
        parser.exit(status=1, message=f"ingestion failed: {exc}\n")
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
