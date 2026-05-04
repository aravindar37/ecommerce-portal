# Search Service

FastAPI service for ecommerce product discovery. Search Service owns catalogue listing, filters/facets, product detail retrieval for search flows, keyword search, semantic search, hybrid search, similar products, embedding generation metadata, and search/vector index readiness metadata.

## Responsibilities

- Read product records populated by Core Service ingestion.
- Expose `GET /api/products`, `GET /api/products/{slug}`, `GET /api/facets`, and `GET /api/products/{id}/similar`.
- Own default product search through `GET /api/search/products`; query searches use hybrid retrieval.
- Own explicit hybrid search through `POST /api/search/hybrid`.
- Keep `POST /api/search/semantic` as a legacy/local validation endpoint.
- Generate product-v1 embedding text and embedding JSONL records through `app.embeddings.generate_embeddings`.
- Report configured embedding provider/model/dimensions/template version and Atlas index metadata.
- Write search, filter, and product-detail activity events to Core Service.

Core Service remains the system of record for users, sessions, products, carts, orders, returns, support, and activity storage. Chat Service should call Search Service for retrieval/search and Core Service for transactional tool calls.

## Run

From the repository root:

```bash
export PYTHONPATH=services/search_service
export CORE_SERVICE_BASE_URL=http://127.0.0.1:4000
uvicorn app.main:app --host 127.0.0.1 --port 4001
```

Core Service should be running and seeded before Search API tests or demos:

```bash
export PYTHONPATH=services/core_service
export TEST_ADMIN_TOKEN=replace-with-local-test-admin-token
uvicorn app.main:app --host 127.0.0.1 --port 4000
```

## Configuration

Search Service reads configuration from environment variables. The root `.env.example` includes the shared variables; the main Search variables are:

- `CORE_SERVICE_BASE_URL`: Core Service URL used for activity writes and session validation.
- `CORE_SERVICE_INTERNAL_TOKEN`: optional service-to-service credential.
- `CORE_SERVICE_DATA_PATH`: local Core state path used by the local read model.
- `PRODUCTS_JSONL_PATH`: normalized product JSONL fallback path.
- `PRODUCT_EMBEDDINGS_JSONL_PATH`: generated embedding JSONL path.
- `MONGODB_URI`, `MONGODB_DB`: MongoDB Atlas connection settings for Atlas-backed mode.
- `MONGODB_SEARCH_INDEX_NAME`: Atlas Search full-text index name.
- `MONGODB_VECTOR_INDEX_NAME`: Atlas Vector Search index name.
- `EMBEDDING_PROVIDER`: `ollama` or `voyage_atlas`.
- `EMBEDDING_MODEL`: default `nomic-embed-text:v1.5`.
- `EMBEDDING_DIMENSIONS`: default `768`.
- `EMBEDDING_TEXT_TEMPLATE_VERSION`: default `product-v1`.
- `EMBEDDING_TEXT_MAX_CHARS`: maximum product text length sent to the embedding provider, default `4000`.
- `EMBEDDING_BATCH_SIZE`, `EMBEDDING_TIMEOUT_MS`: embedding generation controls. The default batch size is `8` for local Ollama stability.
- `OLLAMA_BASE_URL`, `OLLAMA_EMBED_PATH`: Ollama embedding endpoint settings.
- `VOYAGE_API_BASE_URL`, `VOYAGE_API_KEY`, `VOYAGE_INPUT_TYPE_DOCUMENT`, `VOYAGE_INPUT_TYPE_QUERY`: Voyage-compatible provider settings.
- `DEMO_CURRENCY`: used in price facets, default `INR`.

Do not put real credentials in source-controlled files. Use shell exports or a local `.env`.

## Implementation Notes

The current local implementation reads products from Core Service's local state file and falls back to normalized ingestion JSONL. This keeps local MacBook demos working without Atlas credentials while preserving provider and index boundaries for the MongoDB Atlas implementation.

When MongoDB Atlas is configured and a query is present, Search Service runs hybrid retrieval: Atlas Search full-text search over `products` and Atlas Vector Search over `productEmbeddings`, applying the same supported filters to both branches before candidate ranking. Local fallback blends deterministic keyword and semantic text scores and de-duplicates products by `_id`.

Create or update Atlas search indexes:

```bash
curl -X POST http://127.0.0.1:4001/api/indexes/ensure
```

Inspect required index definitions without modifying Atlas:

```bash
curl http://127.0.0.1:4001/api/indexes/definitions
```

Responses use the shared envelope:

```json
{"data": {}, "error": null, "meta": {"requestId": "..."}}
```

Errors use the same envelope with `data: null` and a stable error code.

## Embedding Generation

Generate embeddings from normalized product JSONL:

```bash
PYTHONPATH=services/search_service python3 -m app.embeddings.generate_embeddings \
  --products-jsonl ./artifacts/ingestion/products.jsonl \
  --output ./artifacts/embeddings/product_embeddings.jsonl
```

Dry-run a small batch:

```bash
./scripts/generate_embeddings.sh --dry-run --limit 10
```

## Validation

Compile the service:

```bash
PYTHONPATH=services/search_service python3 -m py_compile $(find services/search_service/app -name '*.py' -print)
```

Run Search API contract tests with Core and Search running:

```bash
TEST_ADMIN_TOKEN=replace-with-local-test-admin-token \
CORE_SERVICE_BASE_URL=http://127.0.0.1:4000 \
SEARCH_SERVICE_BASE_URL=http://127.0.0.1:4001 \
pytest tests/api/test_catalog_search_activity.py
```

Run provider/config checks that rely on Core admin status:

```bash
TEST_ADMIN_TOKEN=replace-with-local-test-admin-token \
CORE_SERVICE_BASE_URL=http://127.0.0.1:4000 \
SEARCH_SERVICE_BASE_URL=http://127.0.0.1:4001 \
pytest tests/api/test_provider_config_ingestion.py::test_ingestion_status_reports_kaggle_dataset_local_filesystem_and_embeddings \
  tests/api/test_provider_config_ingestion.py::test_embedding_index_metadata_matches_configured_provider_model_dimensions_and_template
```
