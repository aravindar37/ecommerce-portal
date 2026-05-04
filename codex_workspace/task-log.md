- [x] Created Python package skeleton, dependency manifest, .gitignore, and .env.example for the ingestion pipeline.
  Validation: python3 -m py_compile core_service/__init__.py passed.
- [x] Implemented Core Service product ingestion models, normalization, dataset validation, JSONL output, and report generation.
  Validation: py_compile plus 25-product smoke ingestion passed with 25 processed and 0 skipped.
- [x] Validated product ingestion against the full local dataset and declared test dependencies in pyproject.toml.
  Validation: full run processed 44,446 products, skipped 0, and produced a 44,446-line products.jsonl report in /private/tmp/codex_ingest_full.
- [x] Reorganized Core Service ingestion under services/core_service/app/ingestion with service-local packaging.
  Validation: py_compile and PYTHONPATH=services/core_service ingestion smoke run processed 10 products with 0 skipped.
- [x] Added Search Service embedding generation module with product-v1 text building and Ollama/Voyage provider support.
  Validation: py_compile and dry-run embedding generation processed 10 products with 0 skipped.
- [x] Added executable scripts for product ingestion and product embedding generation using the service directory layout.
  Validation: bash -n passed; ingest script processed 10 products; embedding script dry-run wrote 10 records.
- [x] Updated README and ecommerce spec command examples to use the scripts and new service module layout.
  Validation: final py_compile and bash -n checks passed for Core/Search service modules and scripts.
- [x] Created service-specific implementation task lists for Core, Search, and Chat services without modifying README/spec.
  Validation: task files exist and rg confirmed service paths plus pytest/Playwright validation commands are included.
- [x] Implemented Core Service FastAPI routes, typed config, envelopes, local repository, MongoDB Atlas helpers, auth, carts, checkout, orders, returns, support, products, activity, admin/test APIs, and service README.
  Validation: py_compile passed; Core API contract tests passed 19/19; core admin/MCP checks passed 5/5 against local Uvicorn.
- [x] Implemented Search Service FastAPI routes, typed config, Core activity bridge, optional Core session/service-token validation, local/Atlas product read model, catalogue/facet/detail/similar APIs, keyword/semantic/hybrid search, embedding status, optional Atlas embedding upserts, and service README.
  Validation: search_service py_compile passed; generate_embeddings dry-run limit 10 passed; Search API contract tests passed 7/7; Core ingestion/provider checks passed 2/2 with local Core/Search.
- [x] Implemented Chat Service FastAPI routes, typed config, LLM adapter, MCP facade, chat state, tool registry, shopping/support agents, action confirmation, Core session validation, Core audit-write endpoint, and service README.
  Validation: chat/core py_compile passed; Chat API tests passed 5/5; cross-service agent/Core tests passed 14/14; full API suite passed 35/35 with local Core/Search/Chat.
- [x] Added MongoDB Atlas product load documentation to root README and implemented `scripts/load_products_to_atlas.sh` plus the Core ingestion loader for normalized product JSONL.
  Validation: loader py_compile passed, shell scripts passed `bash -n`, loader help command ran successfully, and README references were verified with rg.
- [x] Reviewed `code-review-comments.md` and fixed confirmed security, auth, chat-support, ingestion, and frontend functionality gaps without changing the spec.
  Validation: all service py_compile checks passed; Argon2/password-reset smoke passed; API contract suite passed 35/35. Frontend typecheck was blocked by npm registry `ECONNRESET`.
- [x] Updated MongoDB Atlas client creation to use certifi CA bundles in Core and Search service Mongo paths; Chat has no MongoClient constructor.
  Validation: rg confirmed all `MongoClient(` calls pass `tlsCAFile=certifi.where()`; certifi import smoke and py_compile for Core/Search/Chat passed.
- [x] Fixed Ollama embedding context-length failures by bounding product embedding text and lowering the default local batch size for `generate_embeddings.sh`.
  Validation: Search py_compile and script syntax passed; all 44,446 product texts are <= 4000 chars; live Ollama `--limit 2` generated 768-dimension embeddings.
- [x] Rewrote the root README as a setup and operations runbook for prerequisites, env configuration, internal token wiring, startup, data load, and debugging.
  Validation: README content checks passed for required sections, token guidance, embedding knobs, and removal of the stale `dev.sh` reference.
- [x] Populated local `.env` operational gaps, started Core/Search/Chat/Web, installed frontend dependencies, and checked live service logs/health.
  Validation: Core/Search/Chat health and frontend HTTP checks pass; frontend typecheck passes; fixed Search Atlas catalogue timeout. Actual Codex MCP server command needs user input because this CLI has no `mcp serve`.
- [x] Added `scripts/start_all.sh` to start Core, Search, Chat, and the Next.js frontend from one command, with `.env` loading, logs, PIDs, health checks, and cleanup.
  Validation: `bash -n scripts/start_all.sh` passed; live run reached all four health checks and Ctrl-C stopped only the processes started by the script.
- [x] Fixed startup failure from missing `uvicorn` in the project `.venv` by installing service dependencies and adding Python module preflight checks to `start_all.sh`.
  Validation: `.venv` imports for FastAPI/Uvicorn passed; live startup reached Core/Search/Chat/Web readiness with Core running through Uvicorn.
- [x] Added direct `starlette` runtime dependencies to Core, Search, and Chat `pyproject.toml` files because each service imports Starlette modules directly.
  Validation: script syntax, Starlette/FastAPI/Uvicorn import smoke, service main py_compile, and manifest/source `rg` checks passed.
- [x] Implemented high/medium UX review fixes for the catalogue: warm brand palette, accent CTAs, refined product cards, local serif/sans typography, search styling, and size chip controls.
  Validation: `npm --prefix apps/web run typecheck` and `npm --prefix apps/web run build` both passed.
- [x] Ran the full documented test suite and captured results in `test-summary.md`, including compile/typecheck/build, API contracts, and Playwright E2E.
  Validation: compile/typecheck/build passed; API suite failed 3/35 and E2E failed 5/6 with failure details recorded.
- [x] Fixed spec-aligned API/E2E failures and improved frontend error handling across auth, catalogue, checkout, assistant, and support flows.
  Validation: Core/Search py_compile, frontend typecheck/build, API contracts 35/35, and Playwright E2E 6/6 all passed after a clean service restart.
- [x] Implemented updated UX review fixes for gated navigation, account/sign-out, login redirect on add-to-bag, sidebar filters, product visual polish, ratings, cart thumbnails, empty/loading states, and assistant styling.
  Validation: frontend typecheck/build passed; Core py_compile passed; API contracts passed 35/35 after adding cart image snapshots.
- [x] Implemented one-button Atlas hybrid search with shared full-text/vector prefilters, Atlas search-index definition/ensure APIs, frontend single search UX, spec updates, and aligned tests.
  Validation: Atlas `products_keyword` and `product_embeddings_ollama_768` indexes were created; Search py_compile passed; frontend typecheck/build passed; API contracts passed 36/36; Playwright E2E passed 6/6 after a clean service restart.
- [x] Gated catalogue shopping assistant chat to logged-in users and moved the chat launcher into a fixed bottom-left floating control.
  Validation: frontend typecheck and production build both passed.
- [x] Created and verified one admin plus four customer test users through Core Service APIs, and enabled DEBUG Chat Service logging for requests, responses, agent tasks, service calls, MCP planning, and LLM fallback paths.
  Validation: Core API login plus `/api/me` verified expected roles for all five users; Chat/Core py_compile passed; Chat debug logs showed redacted request/response and `agent.task`/`agent.response` entries; Chat API contracts passed 5/5.
- [x] Fixed Core identity persistence so password/Google users, sessions, preferences, and password reset tokens use MongoDB Atlas when `MONGODB_URI` is configured, with file-backed behavior retained for no-Atlas local mode.
  Validation: Core py_compile passed; new user `mongo-verify-1777830186@example.test` registered via API, logged in, returned from `/api/me`, and was found in Atlas `users` with one Atlas `sessions` record; auth API contracts passed 7/7.
- [x] Completed the open Core order-detail, Chat persistence/history, and UX conversation-history tasks from the task lists.
  Validation: Core/Chat py_compile passed; frontend `npx tsc --noEmit` passed; targeted API checks passed 4/4; full `tests/api/test_ai_agents_mcp.py` passed 6/6 after replacing local placeholder service tokens in `.env`.
- [x] Completed the remaining open Chat Service and UX assistant/support tasks: OpenAI-compatible tool registry, matching/comparison tools, cart-aware shopping recommendations, multi-turn history, natural-language support order lookup, HTTP MCP plan execution fallback, support order picker, persistent support feed, inline return/cart confirmations, and safe assistant text handling.
  Validation: Chat py_compile passed; frontend `npx tsc --noEmit` and `npm run build` passed; `tests/api/test_ai_agents_mcp.py` passed 9/9; Playwright E2E passed 6/6.
