#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PRODUCTS_JSONL_PATH="${PRODUCTS_JSONL_PATH:-${REPO_ROOT}/artifacts/ingestion/products.jsonl}"
MONGODB_DB="${MONGODB_DB:-ecommerce_demo}"
PRODUCT_LOAD_BATCH_SIZE="${PRODUCT_LOAD_BATCH_SIZE:-500}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="${REPO_ROOT}/services/core_service${PYTHONPATH:+:${PYTHONPATH}}"

"${PYTHON_BIN}" -m app.ingestion.load_products \
  --products-jsonl "${PRODUCTS_JSONL_PATH}" \
  --mongodb-db "${MONGODB_DB}" \
  --batch-size "${PRODUCT_LOAD_BATCH_SIZE}" \
  "$@"
