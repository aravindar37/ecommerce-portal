# Core Service

FastAPI service that owns all ecommerce transactional data and identity for the Codex demo. It is the single source of truth for users, sessions, carts, orders, returns, support tickets, product records, activity events, and agent audit logs.

---

## Architecture Overview

```
Browser / Next.js (port 3000)
        │  HTTP + session cookie (core_session)
        ▼
  Core Service (port 4000)
  ┌──────────────────────────────────────────────────────────┐
  │  FastAPI + CORS + rate-limit middleware                   │
  │                                                          │
  │  Routers                                                  │
  │  ┌──────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐       │
  │  │  auth    │ │carts │ │ checkout │ │  orders  │       │
  │  └──────────┘ └──────┘ └──────────┘ └──────────┘       │
  │  ┌──────────┐ ┌──────┐ ┌──────────┐ ┌──────────┐       │
  │  │ products │ │returns│ │ support │ │ activity │       │
  │  └──────────┘ └──────┘ └──────────┘ └──────────┘       │
  │  ┌──────────────────────────────────────────────┐       │
  │  │  admin / test / internal routers             │       │
  │  └──────────────────────────────────────────────┘       │
  │                                                          │
  │  ┌──────────────────────────────────────────────┐       │
  │  │  CoreStore  (store.py)                       │       │
  │  │  MongoDB Atlas primary ──► all collections   │       │
  │  │  File fallback ─────────► state.json         │       │
  │  └──────────────────────────────────────────────┘       │
  └──────────────────────────────────────────────────────────┘
        │
        ▼
  MongoDB Atlas (ecommerce_demo database)
  ┌─────────────────────────────────────────────┐
  │ users          sessions      products        │
  │ carts          orders        returnRequests  │
  │ supportTickets counters      serviceMetadata │
  │ userActivityEvents           agentToolAuditLogs │
  │ passwordResetTokens                          │
  └─────────────────────────────────────────────┘
```

---

## Responsibilities

Core Service is the single authority for:

- **Identity** — password registration, Argon2id hashing, login, secure HTTP-only session cookies, `/api/me`, logout, Google OAuth (hosted demos), password reset
- **Products** — local Kaggle dataset ingestion, normalized product JSONL, upsert to Atlas, local image serving from `PRODUCT_IMAGE_LOCAL_ROOT`
- **Carts** — anonymous carts, authenticated carts, anonymous-to-authenticated merge after login, server-side INR totals
- **Checkout** — quote generation with server-side total recalculation, demo order placement
- **Orders** — owned order list and detail with full item/address/payment fields
- **Returns** — 30-day return window eligibility check and return request creation
- **Support tickets** — ticket creation, customer messages, ownership-protected ticket reads
- **Activity events** — validated client-side browse events and authoritative server-side cart/checkout/order/return/ticket events
- **Agent audit logs** — per-tool-call audit records written by Chat Service for MCP compliance

**Core Service does not own** product search (Search Service) or assistant/agent workflows (Chat Service). Both services call Core APIs for data.

---

## Module Structure

```
app/
├── main.py              # FastAPI app, middleware, router registration, startup hooks
├── config.py            # Pydantic settings loaded from env vars
├── database.py          # Lazy MongoDB Atlas connection, index creation
├── store.py             # CoreStore — MongoDB-primary repository with file fallback
├── dependencies.py      # FastAPI dependencies: session resolution, auth guards
├── models.py            # Pydantic request/response models
├── security.py          # is_configured_secret(), InMemoryRateLimitMiddleware
├── auth/
│   └── routes.py        # /api/auth/* and /api/me
├── carts/
│   └── routes.py        # /api/cart/*
├── checkout/
│   └── routes.py        # /api/checkout/*
├── orders/
│   └── routes.py        # /api/orders/*
├── products/
│   └── routes.py        # /api/products/*, /api/facets, /product-images/*
├── returns/
│   └── routes.py        # /api/returns/*
├── support/
│   └── routes.py        # /api/support/tickets/*
├── api/
│   ├── activity.py      # /api/activity-events
│   ├── admin.py         # /api/health, /api/test/*, /api/admin/*
│   ├── internal.py      # /api/internal/* (service-to-service only)
│   ├── envelope.py      # ok() / fail() response helpers
│   └── errors.py        # Global exception handlers
└── ingestion/
    ├── pipeline.py      # Orchestrates dataset → JSONL normalization
    ├── ingest_products.py # CSV/JSON parsing and product normalization
    ├── load_products.py  # Atlas bulk upsert
    └── models.py        # Ingestion report schema
```

---

## API Reference

### Health and service metadata

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | None | Service health, database mode, MCP readiness |
| `GET` | `/api/admin/config` | Admin token | Provider choices without secrets |
| `GET` | `/api/admin/ingestion/status` | Admin token | Dataset, product count, embedding metadata |
| `GET` | `/api/admin/activity-events` | Admin token | Recent activity events |
| `GET` | `/api/admin/audit-logs` | Admin token | Recent agent tool audit logs |

### Auth and identity

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/register` | None | Create password account |
| `POST` | `/api/auth/login` | None | Authenticate and set session cookie |
| `POST` | `/api/auth/logout` | Cookie | Invalidate session |
| `GET` | `/api/me` | Cookie | Current user (no password hash) |
| `PATCH` | `/api/me/preferences` | Cookie | Save one user preference |
| `GET` | `/api/auth/google/start` | None | Start Google OAuth (hosted demos only) |
| `GET` | `/api/auth/google/callback` | None | Google OAuth callback |
| `POST` | `/api/auth/password-reset/request` | None | Safe-response password reset request |
| `POST` | `/api/auth/password-reset/confirm` | None | Consume reset token and change password |

### Products

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/products` | None | Paginated product list with optional query filter |
| `GET` | `/api/products/{slug}` | None | Product detail by ID, slug, or sourceProductId |
| `GET` | `/api/facets` | None | Catalogue facets for filter UI |
| `GET` | `/product-images/{filename}` | None | Local product image serving |

### Carts

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/cart` | Cookie/anon | Active cart with server-side totals |
| `POST` | `/api/cart/items` | Cookie/anon | Add product to cart |
| `PATCH` | `/api/cart/items/{cartItemId}` | Cookie/anon | Update item quantity |
| `DELETE` | `/api/cart/items/{cartItemId}` | Cookie/anon | Remove item |
| `DELETE` | `/api/cart` | Cookie/anon | Clear cart |
| `POST` | `/api/cart/merge` | Cookie | Merge anonymous cart after login |

### Checkout and orders

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/checkout/quote` | Cookie | Server-side total recalculation with shipping address |
| `POST` | `/api/checkout/place-order` | Cookie | Demo order from active cart |
| `GET` | `/api/orders` | Cookie | Owned order list |
| `GET` | `/api/orders/{orderNumber}` | Cookie | Owned order detail |

### Returns and support

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/returns/check-eligibility` | Cookie | 30-day window eligibility check |
| `POST` | `/api/returns` | Cookie | Create return request |
| `POST` | `/api/support/tickets` | Cookie | Create support ticket |
| `GET` | `/api/support/tickets` | Cookie | Owned ticket list |
| `GET` | `/api/support/tickets/{ticketNumber}` | Cookie | Owned ticket detail |
| `POST` | `/api/support/tickets/{ticketNumber}/messages` | Cookie | Append customer message |

### Activity and audit (internal/admin)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/activity-events` | None | Validated client-side activity events |
| `POST` | `/api/internal/agent-audit-logs` | Service token | Agent tool audit log write (Chat Service) |

### Test and seed (restricted)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/test/reset` | Admin token | Clear all transactional data |
| `POST` | `/api/test/seed` | Admin token | Seed products, admin user, demo audit log |

---

## Persistence Design

### MongoDB Atlas (primary when `MONGODB_URI` is set)

All transactional collections live in the `ecommerce_demo` database (overridable with `MONGODB_DB`). The service creates indexes on startup via `mongo.ensure_indexes()`.

| Collection | Primary key | Indexes | Contents |
|---|---|---|---|
| `users` | `_id` (hex24) | `email` unique | Accounts, password hashes, roles, preferences |
| `sessions` | `_id` (hex24) | `sessionTokenHash` unique, `expiresAt` TTL | HTTP-only session tokens (hashed SHA-256) |
| `passwordResetTokens` | `_id` (hex24) | `tokenHash` unique, `expiresAt` TTL | One-time reset tokens (hashed, 30-min TTL) |
| `products` | `_id` (hex24) | `(source, sourceProductId)` unique, `slug` unique, `(gender, masterCategory, subCategory)` | Normalized Kaggle fashion product records |
| `carts` | `_id` (hex24) | `(userId, status)`, `(anonymousId, status)` | Active and merged carts with item snapshots and server-side totals |
| `orders` | `_id` (hex24) | `(userId, orderNumber)` unique, `(userId, createdAt)` | Placed orders with items, shipping address, payment, and totals |
| `returnRequests` | `_id` (hex24) | `(userId, createdAt)`, `orderId` | Return requests with eligibility, reason, and condition |
| `supportTickets` | `_id` (hex24) | `ticketNumber` unique, `(userId, createdAt)` | Support tickets with embedded message thread |
| `userActivityEvents` | `_id` (hex24) | `(eventType, occurredAt)`, `(userId, occurredAt)` | Browse, cart, checkout, and order events |
| `agentToolAuditLogs` | `_id` (hex24) | `(agentType, createdAt)` | Per-tool-call audit records from Chat Service |
| `counters` | counter name | `_id` unique | Atomic sequential counters for ORD/RET/SUP numbers |
| `serviceMetadata` | key string | — | Ingestion and embedding status snapshots |

TTL indexes on `sessions.expiresAt` and `passwordResetTokens.expiresAt` let MongoDB automatically remove expired records.

### File-backed fallback (when `MONGODB_URI` is not set)

All collections above are stored in a single JSON file at `CORE_SERVICE_DATA_PATH` (default `./artifacts/core_service/state.json`). This mode is intended for local development and contract tests without Atlas credentials. The file is read on startup and written after every mutation.

### Persistence decision flow

```
request arrives
    │
    ▼
mongo.configured?  (MONGODB_URI is set and non-placeholder)
    ├─ yes → read/write MongoDB Atlas collections
    └─ no  → read/write self.state[collection] + save to state.json
```

Every `CoreStore` method follows this pattern. The two modes are behaviorally identical from the perspective of all callers.

---

## Authentication Design

### Session cookies

Login sets an HTTP-only `core_session` cookie containing a `secrets.token_urlsafe(32)` token. The raw token is never stored — only its SHA-256 hash (`sessionTokenHash`) is persisted in the `sessions` collection. On each authenticated request, the raw cookie value is hashed and looked up.

```
POST /api/auth/login
    │
    ├── verify Argon2id hash(password) against stored hash
    ├── generate raw_token = secrets.token_urlsafe(32)
    ├── store {sessionTokenHash: sha256(raw_token), expiresAt: now + 7d}
    └── Set-Cookie: core_session=raw_token; HttpOnly; SameSite=Lax
```

### Password hashing

Default algorithm is **Argon2id** via `argon2-cffi`. Legacy PBKDF2-SHA256 (200,000 iterations) is supported for test compatibility. The algorithm is stored as a prefix in the hash string (`argon2id$...` or `pbkdf2_sha256$salt$hash`).

### Anonymous identity

Guest users are identified by a random `core_anonymous_id` cookie set by the cart route on first access. This ID is used to associate anonymous carts. On login, the anonymous cart is merged into the authenticated cart and the anonymous ID is retained for activity event attribution.

### Rate limiting

Login failures are rate-limited by a fixed-window per-IP middleware (`InMemoryRateLimitMiddleware`). The counter only increments on 401 responses, so successful logins do not consume the limit. The limit is per-process and not shared across uvicorn workers.

---

## Product Ingestion

The ingestion pipeline (`/api/test/seed`) runs on demand:

```
./dataset/styles.csv       ─┐
./dataset/images.csv        ├─► pipeline.py ─► products.jsonl
./dataset/styles/{id}.json ─┘                      │
                                                    ▼
                                         load_products.py
                                         bulk upsert → Atlas products
```

1. `ingest_products.py` reads `styles.csv`, `images.csv`, and per-product JSON files from the Kaggle fashion dataset.
2. Each product is normalized to the canonical schema: `_id`, `slug`, `title`, `price` (INR), `images`, `inventory`, tags, ratings, and return policy hint.
3. `pipeline.py` writes a JSONL file to `INGESTION_OUTPUT_DIR`.
4. When MongoDB is configured, `seed_products()` bulk-upserts all products into the `products` Atlas collection using `(source, sourceProductId)` as the upsert key, making re-seeding idempotent.

---

## Cart Totals

All cart and order totals are calculated server-side in INR. The formula:

```
subtotal  = sum(price × quantity for each item)
tax       = subtotal × DEMO_TAX_PERCENT / 100      (default 18%)
shipping  = 0  if subtotal ≥ DEMO_FREE_SHIPPING_THRESHOLD (default ₹3000)
            else DEMO_SHIPPING_FEE                   (default ₹99)
grandTotal = subtotal + tax + shipping
```

The frontend never computes totals — it reads them from the API response.

---

## Sequential Numbering

Order (`ORD`), return (`RET`), and support ticket (`SUP`) numbers are generated by an atomic counter:

- **MongoDB**: `findOneAndUpdate({_id: counterName}, {$inc: {value: 1}}, upsert=True)` — safe across concurrent requests and multiple processes.
- **File-backed**: in-memory increment written to `state.json` — single-process only.

Format: `{PREFIX}-{YYYYMMDD}-{count:06d}` (e.g. `ORD-20260504-000001`).

---

## Activity Events

The 14 validated event types split into two categories:

**Client-side** (from the browser via `POST /api/activity-events`):
`page_viewed`, `product_list_viewed`, `product_detail_viewed`, `search_performed`, `filter_applied`, `assistant_opened`

**Server-side** (written directly by Core route handlers):
`cart_item_added`, `cart_item_updated`, `cart_item_removed`, `checkout_started`, `order_placed`, `return_requested`, `support_ticket_created`, `assistant_product_recommended`

Unknown event types and sensitive metadata fields (session tokens, passwords) are rejected by the client-side endpoint.

---

## Run

```bash
export PYTHONPATH=services/core_service
export TEST_ADMIN_TOKEN=replace-with-local-test-admin-token
export MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
uvicorn app.main:app --host 127.0.0.1 --port 4000
```

Seed demo data:

```bash
curl -X POST http://127.0.0.1:4000/api/test/reset \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN"

curl -X POST http://127.0.0.1:4000/api/test/seed \
  -H "authorization: Bearer $TEST_ADMIN_TOKEN" \
  -H "content-type: application/json" \
  -d '{"products":"fashion-minimal","users":true,"orders":true,"embeddings":true}'
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `` | Atlas connection string. When set, all data goes to Atlas. |
| `MONGODB_DB` | `ecommerce_demo` | Atlas database name |
| `CORE_SERVICE_DATA_PATH` | `./artifacts/core_service/state.json` | File-backed state path (local dev fallback) |
| `TEST_ADMIN_TOKEN` | `` | Bearer token for `/api/test/*` and `/api/admin/*` |
| `CHAT_SERVICE_INTERNAL_TOKEN` | `` | Token Chat Service uses to write audit logs |
| `PASSWORD_HASH_ALGORITHM` | `argon2id` | `argon2id` or `pbkdf2_sha256` |
| `COOKIE_SECURE` | `false` | Set `true` in HTTPS environments |
| `SESSION_COOKIE_MAX_AGE_SECONDS` | `604800` | Session lifetime (7 days) |
| `ADMIN_SEED_EMAIL` | `admin@example.test` | Admin account created on seed |
| `ADMIN_SEED_PASSWORD` | `` | Admin password (required for seed) |
| `DATASET_PATH` | `./dataset` | Kaggle dataset root |
| `PRODUCT_IMAGE_LOCAL_ROOT` | `./dataset/images` | Local image directory |
| `DEMO_CURRENCY` | `INR` | Currency for all totals |
| `DEMO_TAX_PERCENT` | `18` | GST percentage |
| `DEMO_FREE_SHIPPING_THRESHOLD` | `3000` | Cart total above which shipping is free |
| `DEMO_SHIPPING_FEE` | `99` | Flat shipping fee |
| `AUTH_GOOGLE_ENABLED` | `false` | Enable Google OAuth (hosted demos only) |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `0` | Login 401 rate limit per IP (0 = disabled) |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |

Do not put real credentials in source-controlled files. Use `.env` or shell exports.

---

## Response Envelope

All endpoints return the same JSON envelope:

```json
{ "data": { ... }, "error": null, "meta": { "requestId": "abc123" } }
```

Errors return `data: null` with a stable machine-readable code:

```json
{ "data": null, "error": { "code": "EMAIL_ALREADY_EXISTS", "message": "..." }, "meta": { ... } }
```

---

## Validation

Compile check:

```bash
PYTHONPATH=services/core_service python3 -m py_compile \
  $(find services/core_service/app -name '*.py' -print)
```

Run API contract tests (Core Service must be running):

```bash
TEST_ADMIN_TOKEN=replace-with-local-test-admin-token \
CORE_SERVICE_BASE_URL=http://127.0.0.1:4000 \
pytest tests/api/test_auth_and_identity.py \
       tests/api/test_cart_checkout_orders.py \
       tests/api/test_returns_support_agent.py \
       tests/api/test_user_activity_events.py \
       tests/api/test_provider_config_ingestion.py
```
