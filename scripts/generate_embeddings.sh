#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PRODUCTS_JSONL_PATH="${PRODUCTS_JSONL_PATH:-${REPO_ROOT}/artifacts/ingestion/products.jsonl}"
PRODUCT_EMBEDDINGS_JSONL_PATH="${PRODUCT_EMBEDDINGS_JSONL_PATH:-${REPO_ROOT}/artifacts/embeddings/product_embeddings.jsonl}"
EMBEDDING_PROVIDER="${EMBEDDING_PROVIDER:-ollama}"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text:v1.5}"
EMBEDDING_DIMENSIONS="${EMBEDDING_DIMENSIONS:-768}"
EMBEDDING_TEXT_MAX_CHARS="${EMBEDDING_TEXT_MAX_CHARS:-4000}"
EMBEDDING_BATCH_SIZE="${EMBEDDING_BATCH_SIZE:-8}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="${REPO_ROOT}/services/search_service${PYTHONPATH:+:${PYTHONPATH}}"

"${PYTHON_BIN}" -m app.embeddings.generate_embeddings \
  --products-jsonl "${PRODUCTS_JSONL_PATH}" \
  --output "${PRODUCT_EMBEDDINGS_JSONL_PATH}" \
  --provider "${EMBEDDING_PROVIDER}" \
  --model "${EMBEDDING_MODEL}" \
  --dimensions "${EMBEDDING_DIMENSIONS}" \
  --text-max-chars "${EMBEDDING_TEXT_MAX_CHARS}" \
  --batch-size "${EMBEDDING_BATCH_SIZE}" \
  "$@"
