"""Generate product embeddings from normalized product JSONL."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from app.embeddings.config import EmbeddingSettings
from app.embeddings.models import EmbeddingRunReport, ProductEmbeddingMetadata, ProductEmbeddingRecord


class EmbeddingError(Exception):
    """Raised when embedding generation fails."""


def resolve_checkpoint_path(output_path: Path, settings: EmbeddingSettings) -> Path:
    """Return the checkpoint file path for the current run."""

    if settings.checkpoint_path is not None:
        return settings.checkpoint_path
    suffix = f"{output_path.suffix}.checkpoint.json" if output_path.suffix else ".checkpoint.json"
    return output_path.with_suffix(suffix)


def load_checkpoint(path: Path) -> dict[str, Any] | None:
    """Load checkpoint state if the file exists."""

    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EmbeddingError(f"Unable to read checkpoint file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EmbeddingError(f"Checkpoint file {path} contains invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise EmbeddingError(f"Checkpoint file {path} must contain a JSON object")
    return payload


def save_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    """Persist checkpoint state atomically."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(f"{path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)
    except OSError as exc:
        raise EmbeddingError(f"Unable to write checkpoint file {path}: {exc}") from exc


def clear_checkpoint(path: Path) -> None:
    """Remove a completed checkpoint file if present."""

    try:
        if path.exists():
            path.unlink()
    except OSError as exc:
        raise EmbeddingError(f"Unable to remove checkpoint file {path}: {exc}") from exc


def build_checkpoint_signature(
    products_path: Path,
    output_path: Path,
    settings: EmbeddingSettings,
    limit: int | None,
    dry_run: bool,
) -> dict[str, Any]:
    """Build the run signature used to validate resume compatibility."""

    return {
        "productsPath": str(products_path.resolve()),
        "outputPath": str(output_path.resolve()),
        "provider": settings.provider,
        "model": settings.model,
        "dimensions": settings.dimensions,
        "textTemplateVersion": settings.text_template_version,
        "limit": limit,
        "dryRun": dry_run,
    }


def validate_checkpoint(path: Path, checkpoint: dict[str, Any], signature: dict[str, Any]) -> tuple[int, int]:
    """Validate checkpoint compatibility and return resume offsets."""

    stored_signature = checkpoint.get("signature")
    if stored_signature != signature:
        raise EmbeddingError(
            f"Checkpoint file {path} does not match the current embedding configuration; remove it or use a different checkpoint path"
        )
    next_product_offset = checkpoint.get("nextProductOffset", 0)
    records_written = checkpoint.get("recordsWritten", 0)
    if not isinstance(next_product_offset, int) or next_product_offset < 0:
        raise EmbeddingError(f"Checkpoint file {path} has an invalid nextProductOffset")
    if not isinstance(records_written, int) or records_written < 0:
        raise EmbeddingError(f"Checkpoint file {path} has an invalid recordsWritten")
    return next_product_offset, records_written


def reconcile_output_file(path: Path, expected_lines: int) -> None:
    """Ensure the output JSONL matches the checkpointed number of records."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            if expected_lines == 0:
                path.write_text("", encoding="utf-8")
                return
            raise EmbeddingError(
                f"Embedding output file {path} is missing but checkpoint expects {expected_lines} written records"
            )
        if expected_lines == 0:
            path.write_text("", encoding="utf-8")
            return

        kept_lines: list[str] = []
        actual_lines = 0
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if actual_lines < expected_lines:
                    kept_lines.append(line)
                actual_lines += 1
        if actual_lines < expected_lines:
            raise EmbeddingError(
                f"Embedding output file {path} has {actual_lines} records but checkpoint expects {expected_lines}"
            )
        if actual_lines == expected_lines:
            return
        temp_path = path.with_suffix(f"{path.suffix}.resume.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.writelines(kept_lines)
        temp_path.replace(path)
    except OSError as exc:
        raise EmbeddingError(f"Unable to reconcile output file {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read product JSONL records."""

    if not path.exists():
        raise EmbeddingError(f"Input products JSONL does not exist: {path}")
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise EmbeddingError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
                if not isinstance(payload, dict):
                    raise EmbeddingError(f"Expected object at {path}:{line_number}")
                records.append(payload)
    except OSError as exc:
        raise EmbeddingError(f"Unable to read products JSONL {path}: {exc}") from exc
    return records


def text_value(value: Any) -> str:
    """Return a compact string for embedding text fields."""

    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value)


def compact_field(value: Any, max_chars: int) -> str:
    """Return normalized text bounded to a character budget."""

    compacted = " ".join(text_value(value).split())
    if max_chars <= 0 or len(compacted) <= max_chars:
        return compacted
    return compacted[:max_chars].rstrip()


def trim_embedding_text(text: str, max_chars: int) -> str:
    """Trim embedding text to provider-safe size while preserving whole lines when possible."""

    if max_chars <= 0 or len(text) <= max_chars:
        return text
    trimmed = text[:max_chars].rstrip()
    line_break = trimmed.rfind("\n")
    if line_break >= max_chars // 2:
        return trimmed[:line_break].rstrip()
    return trimmed


def build_embedding_text(product: dict[str, Any], max_chars: int = 4000) -> str:
    """Build product-v1 embedding text from normalized product fields."""

    raw_price = product.get("price")
    price: dict[str, Any] = raw_price if isinstance(raw_price, dict) else {}
    raw_attributes = product.get("attributes")
    attributes: dict[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
    category = " > ".join(
        part
        for part in [
            text_value(product.get("masterCategory")),
            text_value(product.get("subCategory")),
            text_value(product.get("articleType")),
        ]
        if part
    )
    text = "\n".join(
        [
            f"Title: {compact_field(product.get('title'), 220)}",
            f"Brand: {compact_field(product.get('brand'), 120)}",
            f"Gender: {compact_field(product.get('gender'), 80)}",
            f"Category: {compact_field(category, 240)}",
            f"Color: {compact_field(product.get('baseColour'), 80)}",
            f"Additional Colors: {compact_field(product.get('colour1'), 80)} {compact_field(product.get('colour2'), 80)}".strip(),
            f"Fashion Type: {compact_field(product.get('fashionType'), 120)}",
            f"Season: {compact_field(product.get('season'), 80)}",
            f"Usage: {compact_field(product.get('usage'), 120)}",
            f"Price: {compact_field(price.get('amount'), 80)} {compact_field(price.get('currency'), 20)}",
            f"Tags: {compact_field(product.get('tags'), 700)}",
            f"Description: {compact_field(product.get('description'), 1200)}",
            f"Style Note: {compact_field(attributes.get('styleNote'), 700)}",
            f"Size/Fit: {compact_field(attributes.get('sizeFit'), 450)}",
            f"Materials/Care: {compact_field(attributes.get('careInstructions'), 450)}",
        ]
    )
    return trim_embedding_text(text, max_chars)


def metadata_from_product(product: dict[str, Any]) -> ProductEmbeddingMetadata:
    """Extract vector-search filter metadata."""

    raw_price = product.get("price")
    price: dict[str, Any] = raw_price if isinstance(raw_price, dict) else {}
    amount = price.get("amount")
    return ProductEmbeddingMetadata(
        gender=product.get("gender"),
        masterCategory=product.get("masterCategory"),
        subCategory=product.get("subCategory"),
        articleType=product.get("articleType"),
        baseColour=product.get("baseColour"),
        season=product.get("season"),
        usage=product.get("usage"),
        priceAmount=float(amount) if isinstance(amount, (int, float)) else None,
        isActive=bool(product.get("isActive", True)),
    )


def batched(items: list[str], batch_size: int) -> list[list[str]]:
    """Split text inputs into batches."""

    if batch_size <= 0:
        raise EmbeddingError("batch size must be greater than zero")
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout_seconds: float) -> dict[str, Any]:
    """POST JSON with stdlib urllib and explicit error handling."""

    encoded = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=encoded,
        method="POST",
        headers={"content-type": "application/json", "accept": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise EmbeddingError(f"Embedding provider HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise EmbeddingError(f"Embedding provider request failed: {exc}") from exc
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise EmbeddingError(f"Embedding provider returned invalid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise EmbeddingError("Embedding provider returned non-object JSON")
    return decoded


def embed_with_ollama(texts: list[str], settings: EmbeddingSettings) -> list[list[float]]:
    """Generate embeddings using Ollama /api/embed."""

    url = f"{settings.ollama_base_url.rstrip('/')}/{settings.ollama_embed_path.lstrip('/')}"
    prefixed = [f"search_document: {text}" for text in texts]
    response = post_json(
        url,
        {"model": settings.model, "input": prefixed},
        headers={},
        timeout_seconds=settings.timeout_ms / 1000,
    )
    embeddings = response.get("embeddings")
    if embeddings is None and "embedding" in response:
        embeddings = [response["embedding"]]
    if not isinstance(embeddings, list):
        raise EmbeddingError("Ollama response did not include embeddings")
    return coerce_embeddings(embeddings)


def embed_with_voyage(texts: list[str], settings: EmbeddingSettings) -> list[list[float]]:
    """Generate embeddings using a Voyage-compatible API."""

    if not settings.voyage_api_key:
        raise EmbeddingError("VOYAGE_API_KEY is required for voyage_atlas embeddings")
    url = f"{settings.voyage_api_base_url.rstrip('/')}/embeddings"
    response = post_json(
        url,
        {
            "model": settings.model,
            "input": texts,
            "input_type": settings.voyage_input_type_document,
        },
        headers={"authorization": f"Bearer {settings.voyage_api_key}"},
        timeout_seconds=settings.timeout_ms / 1000,
    )
    data = response.get("data")
    if not isinstance(data, list):
        raise EmbeddingError("Voyage response did not include data list")
    embeddings = [item.get("embedding") for item in data if isinstance(item, dict)]
    return coerce_embeddings(embeddings)


def coerce_embeddings(raw_embeddings: list[Any]) -> list[list[float]]:
    """Validate and coerce embedding arrays to floats."""

    vectors: list[list[float]] = []
    for raw in raw_embeddings:
        if not isinstance(raw, list):
            raise EmbeddingError("Embedding vector is not a list")
        vector: list[float] = []
        for value in raw:
            if not isinstance(value, (int, float)):
                raise EmbeddingError("Embedding vector contains non-numeric value")
            vector.append(float(value))
        vectors.append(vector)
    return vectors


def generate_vectors(texts: list[str], settings: EmbeddingSettings) -> list[list[float]]:
    """Generate embeddings for one batch using the configured provider."""

    provider = settings.provider.lower()
    if provider == "mongodb_atlas_autoembed":
        raise EmbeddingError("MongoDB Atlas Automated Embedding generates vectors at index time; do not run the legacy embedding generator")
    if provider == "ollama":
        return embed_with_ollama(texts, settings)
    if provider == "voyage_atlas":
        return embed_with_voyage(texts, settings)
    raise EmbeddingError(f"Unsupported EMBEDDING_PROVIDER: {settings.provider}")


def write_records(path: Path, records: list[ProductEmbeddingRecord]) -> None:
    """Append embedding records to JSONL output."""

    try:
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                handle.write(record.model_dump_json())
                handle.write("\n")
    except OSError as exc:
        raise EmbeddingError(f"Unable to write embeddings output {path}: {exc}") from exc


def persist_records_to_mongodb(records: list[ProductEmbeddingRecord], settings: EmbeddingSettings) -> None:
    """Upsert embedding records into MongoDB Atlas when configured."""

    if not settings.mongodb_uri.strip() or not records:
        return
    try:
        import certifi
        from pymongo import MongoClient, UpdateOne
    except ImportError as exc:
        raise EmbeddingError("pymongo and certifi must be installed for MongoDB Atlas embedding persistence") from exc
    operations = []
    for record in records:
        document = record.model_dump(mode="json")
        operations.append(
            UpdateOne(
                {
                    "productId": record.productId,
                    "provider": record.provider,
                    "model": record.model,
                    "dimensions": record.dimensions,
                    "textTemplateVersion": record.textTemplateVersion,
                },
                {"$set": document},
                upsert=True,
            )
        )
    try:
        client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000, tlsCAFile=certifi.where())
        collection = client[settings.mongodb_db]["productEmbeddings"]
        collection.create_index(
            [("productId", 1), ("provider", 1), ("model", 1), ("dimensions", 1), ("textTemplateVersion", 1)],
            unique=True,
        )
        collection.create_index([("metadata.gender", 1), ("metadata.baseColour", 1), ("metadata.usage", 1)])
        collection.bulk_write(operations, ordered=False)
    except Exception as exc:
        raise EmbeddingError(f"Unable to persist embeddings to MongoDB Atlas: {exc}") from exc


def run_embedding_generation(
    products_path: Path,
    output_path: Path,
    settings: EmbeddingSettings,
    limit: int | None,
    dry_run: bool,
) -> EmbeddingRunReport:
    """Generate product embedding JSONL records."""

    started = time.perf_counter()
    products = read_jsonl(products_path)
    products_to_process = products if limit is None else products[:limit]
    checkpoint_path: Path | None = None
    resume_offset = 0
    records_written = 0
    if settings.checkpoint_enabled:
        checkpoint_path = resolve_checkpoint_path(output_path, settings)
        checkpoint = load_checkpoint(checkpoint_path)
        signature = build_checkpoint_signature(products_path, output_path, settings, limit, dry_run)
        if checkpoint is None:
            save_checkpoint(
                checkpoint_path,
                {
                    "signature": signature,
                    "nextProductOffset": 0,
                    "recordsWritten": 0,
                    "createdAt": time.time(),
                },
            )
        else:
            resume_offset, records_written = validate_checkpoint(checkpoint_path, checkpoint, signature)
        reconcile_output_file(output_path, records_written)
    else:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("", encoding="utf-8")
        except OSError as exc:
            raise EmbeddingError(f"Unable to prepare output file {output_path}: {exc}") from exc

    if resume_offset > len(products_to_process):
        raise EmbeddingError(
            f"Checkpoint expects to resume at product offset {resume_offset}, but only {len(products_to_process)} input products are available"
        )

    remaining_products = products_to_process[resume_offset:]
    text_payloads = [build_embedding_text(product, settings.text_max_chars) for product in products_to_process]
    remaining_text_payloads = text_payloads[resume_offset:]
    embeddings_generated = records_written if not dry_run else 0
    skipped = 0
    product_offset = resume_offset
    for text_batch in batched(remaining_text_payloads, settings.batch_size):
        batch_products = remaining_products[: len(text_batch)]
        remaining_products = remaining_products[len(text_batch) :]
        batch_start = product_offset
        product_offset += len(text_batch)
        if dry_run:
            vectors = [[] for _ in text_batch]
        else:
            vectors = generate_vectors(text_batch, settings)
            if len(vectors) != len(text_batch):
                raise EmbeddingError("Embedding provider returned a different number of vectors than inputs")
        records: list[ProductEmbeddingRecord] = []
        for product, text, vector in zip(batch_products, text_batch, vectors, strict=True):
            product_id = product.get("_id")
            source_product_id = product.get("sourceProductId")
            if not isinstance(product_id, str) or not isinstance(source_product_id, str):
                skipped += 1
                continue
            if vector and len(vector) != settings.dimensions:
                raise EmbeddingError(
                    f"Embedding dimension mismatch for {source_product_id}: expected {settings.dimensions}, got {len(vector)}"
                )
            records.append(
                ProductEmbeddingRecord(
                    productId=product_id,
                    sourceProductId=source_product_id,
                    provider=settings.provider,
                    model=settings.model,
                    dimensions=settings.dimensions,
                    textTemplateVersion=settings.text_template_version,
                    embeddingTextHash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    embedding=vector,
                    metadata=metadata_from_product(product),
                )
            )
        write_records(output_path, records)
        if not dry_run:
            persist_records_to_mongodb(records, settings)
        records_written += len(records)
        if checkpoint_path is not None:
            save_checkpoint(
                checkpoint_path,
                {
                    "signature": build_checkpoint_signature(products_path, output_path, settings, limit, dry_run),
                    "nextProductOffset": product_offset,
                    "recordsWritten": records_written,
                    "lastCompletedBatchStart": batch_start,
                    "lastCompletedBatchSize": len(text_batch),
                    "updatedAt": time.time(),
                },
            )
        embeddings_generated += 0 if dry_run else len(records)
    if checkpoint_path is not None:
        clear_checkpoint(checkpoint_path)
    return EmbeddingRunReport(
        inputProductsPath=str(products_path),
        outputEmbeddingsPath=str(output_path),
        provider=settings.provider,
        model=settings.model,
        dimensions=settings.dimensions,
        textTemplateVersion=settings.text_template_version,
        productsRead=len(products_to_process),
        productsSkipped=skipped,
        embeddingsGenerated=embeddings_generated,
        dryRun=dry_run,
        durationSeconds=round(time.perf_counter() - started, 3),
    )


def positive_int(value: str) -> int:
    """Argparse parser for positive integers."""

    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""

    settings = EmbeddingSettings.from_env()
    parser = argparse.ArgumentParser(description="Generate product embeddings from normalized product JSONL.")
    parser.add_argument("--products-jsonl", type=Path, default=settings.input_products_path)
    parser.add_argument("--output", type=Path, default=settings.output_embeddings_path)
    parser.add_argument("--provider", default=settings.provider)
    parser.add_argument("--model", default=settings.model)
    parser.add_argument("--dimensions", type=positive_int, default=settings.dimensions)
    parser.add_argument("--text-max-chars", type=positive_int, default=settings.text_max_chars)
    parser.add_argument("--batch-size", type=positive_int, default=settings.batch_size)
    parser.add_argument("--limit", type=positive_int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args()
    settings = EmbeddingSettings.from_env().model_copy(
        update={
            "provider": args.provider,
            "model": args.model,
            "dimensions": args.dimensions,
            "text_max_chars": args.text_max_chars,
            "batch_size": args.batch_size,
        }
    )
    try:
        report = run_embedding_generation(
            products_path=args.products_jsonl,
            output_path=args.output,
            settings=settings,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    except EmbeddingError as exc:
        parser.exit(status=1, message=f"embedding generation failed: {exc}\n")
    print(report.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
