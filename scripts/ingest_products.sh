#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATASET_PATH="${DATASET_PATH:-${REPO_ROOT}/dataset}"
INGESTION_OUTPUT_DIR="${INGESTION_OUTPUT_DIR:-${REPO_ROOT}/artifacts/ingestion}"
PRODUCT_IMAGE_PUBLIC_BASE_URL="${PRODUCT_IMAGE_PUBLIC_BASE_URL:-/product-images}"
DEMO_CURRENCY="${DEMO_CURRENCY:-INR}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="${REPO_ROOT}/services/core_service${PYTHONPATH:+:${PYTHONPATH}}"

"${PYTHON_BIN}" -m app.ingestion.ingest_products \
  --dataset "${DATASET_PATH}" \
  --output-dir "${INGESTION_OUTPUT_DIR}" \
  --public-image-base-url "${PRODUCT_IMAGE_PUBLIC_BASE_URL}" \
  --currency "${DEMO_CURRENCY}" \
  "$@"
