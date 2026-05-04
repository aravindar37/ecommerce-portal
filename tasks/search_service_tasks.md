# Search Service Task List

Scope: `services/search_service`

Search Service owns all product search behavior: catalogue listing, product detail for search flows, facets, keyword search, non-semantic search, semantic search, hybrid search, similar products, embedding generation, MongoDB Atlas Search, and MongoDB Atlas Vector Search.

## Foundation

- [x] Create the FastAPI app structure under `services/search_service/app` with routers for `api`, `embeddings`, `indexes`, and `search`.
  - Validation: `PYTHONPATH=services/search_service python3 -m py_compile $(find services/search_service/app -name '*.py' -print)`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

- [x] Implement typed Search Service config for MongoDB Atlas, Core Service base URL, embedding provider, embedding model, dimensions, batch size, timeout, and vector index name.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_admin_config_exposes_provider_choices_without_secrets`

- [x] Implement Core-issued session/service-token validation for requests that need user context and service-to-service calls.
  - Validation: `pytest tests/api/test_catalog_search_activity.py`

## Product Read Model and Catalogue APIs

- [x] Build product read access from MongoDB Atlas `products`, populated by Core Service ingestion.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_catalogue_lists_active_products_with_dataset_and_ecommerce_fields`

- [x] Implement `GET /api/products` with pagination, keyword query, filters, sorting, availability, and active product filtering.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_catalogue_lists_active_products_with_dataset_and_ecommerce_fields`
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_keyword_search_supports_filters_sort_and_pagination`

- [x] Implement `GET /api/products/:slug` product detail lookup and record product-detail activity through Core Service.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_product_detail_by_slug_records_product_selection_activity`

- [x] Implement `GET /api/facets` for gender, category, subcategory, article type, base colour, season, usage, and price.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_facets_expose_catalogue_filters`

- [x] Implement `GET /api/products/:id/similar` using category/color/usage and optionally vector similarity.
  - Validation: `pytest tests/api/test_catalog_search_activity.py`

## Non-Semantic and Keyword Search

- [x] Implement `GET /api/search/products` as the owner of all non-semantic product search with query, filters, sort, and pagination.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_search_service_owns_non_semantic_product_search`

- [ ] Create and validate Atlas Search keyword index over title, description, brand, categories, base colour, usage, and tags.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_keyword_search_supports_filters_sort_and_pagination`

- [x] Write search/filter/sort activity events through Core Service.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_keyword_search_supports_filters_sort_and_pagination`
  - Validation: `pytest tests/api/test_user_activity_events.py::test_client_side_browse_activity_accepts_validated_events`

## Embeddings and Vector Search

- [x] Implement product-v1 embedding text generation from normalized product JSONL.
  - Validation: `./scripts/generate_embeddings.sh --dry-run --limit 10`

- [x] Implement provider adapters for Ollama `nomic-embed-text:v1.5` and Voyage-compatible API shape.
  - Validation: `./scripts/generate_embeddings.sh --dry-run --limit 10`

- [x] Persist generated product embeddings in MongoDB Atlas `productEmbeddings` with provider/model/dimensions/template version/hash metadata.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_embedding_index_metadata_matches_configured_provider_model_dimensions_and_template`

- [ ] Implement vector index creation/validation for the configured embedding dimensions and filter fields.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_embedding_index_metadata_matches_configured_provider_model_dimensions_and_template`

- [x] Implement `POST /api/search/semantic` with query embedding, metadata filters, vector search, relevance score, and provider metadata in response.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_semantic_search_returns_ranked_products_and_embedding_metadata`

- [x] Implement `POST /api/search/hybrid` with vector candidates, keyword candidates, dedupe, score normalization, and ranked results.
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_hybrid_search_deduplicates_keyword_and_vector_results`

## Admin and Service Reporting

- [ ] Report product counts, embedding counts, provider/model/dimensions/template version, vector index name, local dataset counts, and missing-image IDs to Core admin status.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_ingestion_status_reports_kaggle_dataset_local_filesystem_and_embeddings`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_embedding_index_metadata_matches_configured_provider_model_dimensions_and_template`

- [x] Expose health/readiness metadata for Search Service.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

## Search Service Completion Gates

- [x] Search-only API gate passes.
  - Validation: `pytest tests/api/test_catalog_search_activity.py`

- [ ] Provider/config gate passes with Core and Chat running.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py`

- [ ] Cross-service API gate passes with Core and Chat running.
  - Validation: `pytest tests/api`

- [ ] Browser search flows pass after frontend is implemented.
  - Validation: `npx playwright test tests/e2e --workers=1`
