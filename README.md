# Codex Ecommerce Demo

Demo fashion ecommerce application with three Python/FastAPI backend services, a Next.js/React frontend, MongoDB Atlas product/vector storage, semantic search, and Codex-powered shopping and support agents.

The authoritative product and engineering spec is in [ecommerce-demo-spec.md](./codex_workspace/ecommerce-demo-spec.md).
See [docs/architecture.md](./docs/architecture.md) for the runtime and voice-call architecture diagrams.

## How It Is Set Up

The app is split into four runtime processes:

- Core Service, `http://localhost:4000`: owns identity, sessions, users, carts, checkout, orders, returns, support tickets, product ingestion, local image serving, activity events, admin/test APIs, and agent audit logs.
- Search Service, `http://localhost:4001`: owns catalogue listing, filters/facets, keyword search, semantic search, hybrid search, similar products, embedding generation, and Atlas search/vector metadata.
- Chat Service, `http://localhost:4002`: owns shopping/support assistant sessions, LLM routing, local Codex MCP readiness, pending assistant actions, and tool calls into Core/Search.
- Web App, `http://localhost:3000`: Next.js frontend. Browser calls go through app-local API proxy routes under `apps/web/app/api/*`.

Service boundaries matter:

- Chat calls Core for account/cart/order/return/support writes.
- Chat calls Search for product retrieval and discovery.
- Search records search/filter/product-detail activity by calling Core.
- Core is the only service that owns ecommerce transactions and user activity storage.

## Directory Structure

```text
.
├── apps/
│   └── web/                         # Next.js frontend
├── dataset/                         # Kaggle fashion dataset, local only
├── scripts/
│   ├── ingest_products.sh
│   ├── load_products_to_atlas.sh
│   └── generate_embeddings.sh
├── services/
│   ├── core_service/                # FastAPI Core Service
│   ├── search_service/              # FastAPI Search Service
│   └── chat_service/                # FastAPI Chat Service
├── tests/
│   ├── api/                         # pytest API contracts
│   └── e2e/                         # Playwright browser flows
├── .env.example
└── codex_workspace/                  # specs, task logs, and review docs
    ├── ecommerce-demo-spec.md
    ├── task-log.md
    ├── codex-rules.md
    ├── chat_service_tasks.md
    ├── core_service_tasks.md
    ├── search_service_tasks.md
    ├── ux-tasks.md
    ├── code-review-comments.md
    └── ux-design-review-comments.md
```

## Prerequisites

Install or have available:

- Python 3.11 or newer.
- Node.js and npm for the Next.js frontend.
- MongoDB Atlas cluster with your Service IPs allowed in Network Access.
- Ollama running locally for default embeddings.
- `nomic-embed-text:v1.5` pulled in Ollama.
- OpenAI-compatible LLM credentials if you want live assistant LLM calls. Without a key, local deterministic assistant behavior is still used for demo/test flows.
- Codex CLI available for local MCP readiness when using the default `CODEX_MCP_TRANSPORT=stdio`.

Useful checks:

```bash
python3 --version
node --version
npm --version
ollama list | grep 'nomic-embed-text'
command -v codex
```

If the embedding model is missing:

```bash
ollama pull nomic-embed-text:v1.5
```

## Environment Setup

Create a local `.env` from the example and then edit it. Do not commit `.env`.

```bash
cp .env.example .env
```

Minimum local values to set:

```env
APP_ENV=development
APP_BASE_URL=http://localhost:3000

CORE_SERVICE_BASE_URL=http://localhost:4000
SEARCH_SERVICE_BASE_URL=http://localhost:4001
CHAT_SERVICE_BASE_URL=http://localhost:4002

MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/
MONGODB_DB=ecommerce_demo

TEST_ADMIN_TOKEN=<local-admin-token>
CORE_SERVICE_INTERNAL_TOKEN=<core-search-shared-token>
SEARCH_SERVICE_INTERNAL_TOKEN=<core-search-shared-token>
CHAT_SERVICE_INTERNAL_TOKEN=<chat-core-shared-token>

ADMIN_SEED_EMAIL=admin@example.test
ADMIN_SEED_PASSWORD=<local-admin-password>

AUTH_GOOGLE_ENABLED=false
COOKIE_SECURE=false

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text:v1.5
EMBEDDING_DIMENSIONS=768
EMBEDDING_TEXT_MAX_CHARS=4000
EMBEDDING_BATCH_SIZE=8
OLLAMA_BASE_URL=http://localhost:11434

LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_CHAT_COMPLETIONS_PATH=/chat/completions
LLM_API_KEY=<openai-or-grove-key>

CODEX_MCP_ENABLED=true
CODEX_MCP_TRANSPORT=stdio
CODEX_MCP_COMMAND=codex
CODEX_MCP_ARGS=mcp,serve
```

Load the env into your shell before running scripts or services:

```bash
set -a
source .env
set +a
```

## Internal Tokens

Use separate, random local strings for admin and service-to-service access.

Recommended local setup:

```bash
export TEST_ADMIN_TOKEN="$(openssl rand -hex 24)"
export CORE_SEARCH_TOKEN="$(openssl rand -hex 24)"
export CHAT_CORE_TOKEN="$(openssl rand -hex 24)"

export CORE_SERVICE_INTERNAL_TOKEN="$CORE_SEARCH_TOKEN"
export SEARCH_SERVICE_INTERNAL_TOKEN="$CORE_SEARCH_TOKEN"
export CHAT_SERVICE_INTERNAL_TOKEN="$CHAT_CORE_TOKEN"
```

Copy the generated `TEST_ADMIN_TOKEN`, `CORE_SEARCH_TOKEN`, and `CHAT_CORE_TOKEN` values into `.env`, or run those exports after `source .env` in every service terminal. If you source `.env` after exporting random values, `.env` will overwrite them.

How those values are used:

- `TEST_ADMIN_TOKEN`: Core admin/test bearer token for `/api/admin/*` and `/api/test/*`.
- `CHAT_SERVICE_INTERNAL_TOKEN`: set in both Core and Chat. Chat sends it as `x-service-token` when writing agent audit logs to Core internal APIs.
- `CORE_SERVICE_INTERNAL_TOKEN`: set in Search. Search validates `x-service-token` against this value for trusted service calls.
- `SEARCH_SERVICE_INTERNAL_TOKEN`: set in Chat. Chat sends this value when calling Search. For trusted Chat-to-Search calls, set it to the same value as Search's `CORE_SERVICE_INTERNAL_TOKEN`.

Do not use the literal placeholders from `.env.example` as real tokens. Empty or placeholder-like token values are rejected by protected Core routes.

## Install Dependencies

The services are plain Python packages under `services/*`. From the repo root, install the service dependencies you need:

```bash
python3 -m pip install -e services/core_service
python3 -m pip install -e services/search_service
python3 -m pip install -e services/chat_service
```

Install frontend dependencies:

```bash
npm --prefix apps/web install
```

If npm fails with `ECONNRESET`, retry when registry/network access is available.

## Dataset

The local Kaggle product dataset is expected at `./dataset`.
Kaggle dataset used is https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-dataset

Expected contents:

- `dataset/styles.csv`: 44,446 product rows.
- `dataset/images.csv`: 44,446 image URL rows.
- `dataset/styles/`: 44,446 product JSON metadata files.
- `dataset/images/`: 44,441 local JPG files.

Known missing local JPGs: `12347`, `39401`, `39403`, `39410`, `39425`.

## One-Time Product Load

Run this flow once when loading product data into MongoDB Atlas.

1. Normalize dataset to product JSONL:

```bash
./scripts/ingest_products.sh
```

Outputs:

- `artifacts/ingestion/products.jsonl`
- `artifacts/ingestion/ingestion-report.json`

2. Upsert normalized products into Atlas:

```bash
./scripts/load_products_to_atlas.sh
```

This writes to `db.products` and creates basic uniqueness/filter indexes.

3. Generate product embeddings with Ollama and upsert vectors:

```bash
EMBEDDING_PROVIDER=ollama \
EMBEDDING_MODEL=nomic-embed-text:v1.5 \
EMBEDDING_DIMENSIONS=768 \
EMBEDDING_TEXT_MAX_CHARS=4000 \
EMBEDDING_BATCH_SIZE=8 \
./scripts/generate_embeddings.sh
```

This writes `artifacts/embeddings/product_embeddings.jsonl` and upserts to `db.productEmbeddings` when `MONGODB_URI` is configured. The script caps each embedding text and uses a small Ollama batch size to avoid context-length errors from long product descriptors.

Smoke test with a small batch:

```bash
./scripts/ingest_products.sh --limit 10
./scripts/load_products_to_atlas.sh
./scripts/generate_embeddings.sh --limit 10
```

After the smoke test passes, rerun the three commands without `--limit` for the full dataset.

## Start The Application

Open four terminal windows from the repo root. In each terminal, load `.env` first:

```bash
set -a
source .env
set +a
```

Terminal 1, Core Service:

```bash
PYTHONPATH=services/core_service \
uvicorn app.main:app --host 127.0.0.1 --port 4000
```

Terminal 2, Search Service:

```bash
PYTHONPATH=services/search_service \
uvicorn app.main:app --host 127.0.0.1 --port 4001
```

Terminal 3, Chat Service:

```bash
PYTHONPATH=services/chat_service \
uvicorn app.main:app --host 127.0.0.1 --port 4002
```

Terminal 4, frontend:

```bash
npm --prefix apps/web run dev
```

Open:

```text
http://localhost:3000
```

## Seed Local Demo Data

For local demos and tests, seed Core Service after it starts:

```bash
curl -X POST http://127.0.0.1:4000/api/test/reset \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN"

curl -X POST http://127.0.0.1:4000/api/test/seed \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{"products":"fashion-minimal","users":true,"orders":true,"embeddings":true}'
```

Use `"products":"fashion-minimal"` for a fast local seed. Use the ingestion/load scripts for the full dataset.

## Health And Debug Checks

Service health:

```bash
curl http://127.0.0.1:4000/api/health
curl http://127.0.0.1:4001/api/health
curl http://127.0.0.1:4002/api/health
```

Admin config:

```bash
curl http://127.0.0.1:4000/api/admin/config \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN"
```

Ingestion status:

```bash
curl http://127.0.0.1:4000/api/admin/ingestion/status \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN"
```

Search smoke:

```bash
curl "http://127.0.0.1:4001/api/products?limit=3"
curl "http://127.0.0.1:4001/api/search/products?query=black%20shoes&limit=3"
```

Embedding smoke:

```bash
./scripts/generate_embeddings.sh --dry-run --limit 10
./scripts/generate_embeddings.sh --limit 2
```

MongoDB Atlas count check:

```bash
python3 - <<'PY'
import os
import certifi
from pymongo import MongoClient

client = MongoClient(os.environ["MONGODB_URI"], tlsCAFile=certifi.where())
db = client[os.getenv("MONGODB_DB", "ecommerce_demo")]
print("products", db.products.count_documents({}))
print("productEmbeddings", db.productEmbeddings.count_documents({}))
sample = db.productEmbeddings.find_one({}, {"embedding": 1})
print("embedding dimensions", len(sample["embedding"]) if sample else 0)
PY
```

## Common Issues

`401 UNAUTHENTICATED` on admin/test endpoints:

- Confirm `TEST_ADMIN_TOKEN` is non-empty in the Core Service shell.
- Confirm your curl header is exactly `authorization: Bearer $TEST_ADMIN_TOKEN`.

Chat can answer but audit writes fail:

- Set the same `CHAT_SERVICE_INTERNAL_TOKEN` value in both Core and Chat shells.

Trusted Chat-to-Search calls are not accepted:

- Set Search's `CORE_SERVICE_INTERNAL_TOKEN` and Chat's `SEARCH_SERVICE_INTERNAL_TOKEN` to the same value.

Ollama returns `the input length exceeds the context length`:

- Use the current `generate_embeddings.sh` defaults: `EMBEDDING_TEXT_MAX_CHARS=4000` and `EMBEDDING_BATCH_SIZE=8`.
- Lower `EMBEDDING_TEXT_MAX_CHARS` or `EMBEDDING_BATCH_SIZE` further for smaller local models.

MongoDB Atlas TLS/certificate errors:

- The Python Mongo clients use `tlsCAFile=certifi.where()`.
- Make sure `certifi` is installed through the service dependency install commands.

Frontend cannot reach backend:

- Confirm Core/Search/Chat are running on ports `4000`, `4001`, and `4002`.
- Confirm `CORE_SERVICE_BASE_URL`, `SEARCH_SERVICE_BASE_URL`, and `CHAT_SERVICE_BASE_URL` are loaded before starting `npm run dev`.

## Tests

Compile Python services:

```bash
PYTHONPATH=services/core_service python3 -m py_compile $(find services/core_service/app -name '*.py' -print)
PYTHONPATH=services/search_service python3 -m py_compile $(find services/search_service/app -name '*.py' -print)
PYTHONPATH=services/chat_service python3 -m py_compile $(find services/chat_service/app -name '*.py' -print)
```

Run API tests with Core, Search, and Chat running:

```bash
TEST_ADMIN_TOKEN=$TEST_ADMIN_TOKEN \
CORE_SERVICE_BASE_URL=http://127.0.0.1:4000 \
SEARCH_SERVICE_BASE_URL=http://127.0.0.1:4001 \
CHAT_SERVICE_BASE_URL=http://127.0.0.1:4002 \
pytest tests/api
```

Run frontend checks:

```bash
npm --prefix apps/web run typecheck
npx playwright test tests/e2e --workers=1
```
