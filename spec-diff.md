# Spec Comparison: ecommerce-demo-spec.md vs stylesense_spec.md

## Summary

`ecommerce-demo-spec.md` is the authoritative engineering spec for this project. `stylesense_spec.md` is an earlier or alternative draft with a simpler, more monolithic design. The two specs share the same product domain and dataset but diverge significantly in architecture, data model, auth strategy, AI integration, and scope.

---

## 1. Architecture

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Backend | Three separate Python FastAPI services: Core (port 4000), Search (port 4001), Chat (port 4002) | Single monolithic FastAPI service (port 8000) with internal service classes |
| Frontend | Next.js App Router, React, TypeScript | React 18+ with Vite 5+, TailwindCSS, Zustand (no Next.js) |
| Frontend HTTP client | Not specified (fetch / custom BFF) | Axios |
| Service discovery | Configurable `CORE_SERVICE_BASE_URL`, `SEARCH_SERVICE_BASE_URL`, `CHAT_SERVICE_BASE_URL` env vars, internal service tokens | Single base URL `http://localhost:8000` |
| Inter-service auth | Internal bearer tokens (`x-service-token`) per service pair | Not applicable (monolith) |

---

## 2. Authentication

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Auth mechanism | Server-issued session tokens stored as HTTP-only cookies | JWTs stored in HTTP-only cookies |
| Token storage | Session records in `sessions` MongoDB collection with `sessionTokenHash` and TTL index | JWT signed with `JWT_SECRET`, no server-side session storage |
| Password hashing | Argon2id preferred, bcrypt acceptable | bcrypt only (passlib, 12 rounds) |
| Google OAuth gate | Disabled in local development; enabled only via `AUTH_GOOGLE_ENABLED=true` in shared demo environments | Enabled by default; no local/remote distinction |
| Google OAuth CSRF | Explicit CSRF protection required | Google OAuth state parameter validated |
| Rate limiting | Configurable env vars: `RATE_LIMIT_AUTH_PER_MINUTE`, `RATE_LIMIT_SEARCH_PER_MINUTE`, `RATE_LIMIT_CHAT_PER_MINUTE` | 5 failed login attempts → 15 min lockout tracked in Atlas |
| Password reset | Required: `/api/auth/password-reset/request` and `/api/auth/password-reset/confirm` | Not specified |
| JWT refresh | Not applicable (cookie sessions expire via TTL index) | Required: `POST /auth/refresh` |
| Auth token scope | Separate `authAccounts` collection for OAuth provider records | Flat `auth_provider` / `google_id` fields on the `users` document |

---

## 3. Data Model

### Users

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Auth identity | `passwordHash`, `roles`, `emailVerified`, separate `authAccounts` collection | `password_hash`, `auth_provider`, `google_id` inline on user document |
| Preferences shape | `{gender, sizes, colors}` | `{style, budget: {min, max}, sizes: {top, bottom, shoe}}` |
| Personalization vector | Not specified | `preference_vector` (768 or 1024 floats) stored on user |
| Extra timestamps | `lastLoginAt` | Not present |

### Products

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Embedding storage | Separate `productEmbeddings` collection (provider + model + dimensions versioned) | Inline `embedding` field on `products` document |
| Price | Nested object `{amount, listAmount, currency}` | Flat `price` float + separate `currency` string |
| Images | Array of image objects `{url, alt, sourcePath, originalUrl, isPrimary, isLocalFileAvailable}` | Single `image_url` string |
| Inventory | Nested `{available, reserved, trackInventory}` | Flat `stock` int |
| Rating | Separate `ratingAverage` and `ratingCount` fields | Flat `rating` and `review_count` fields |
| Descriptor fields | `attributes.careInstructions`, `attributes.sizeFit`, `attributes.styleNote`, `attributes.articleAttributes` | Not present |
| Return policy | `returnPolicyCode` string referencing policy catalogue | Not present |
| Identity fields | `source`, `sourceProductId`, `slug` | `product_id` (integer from CSV) |

### Cart

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Shape | Single `carts` document per cart with embedded `items` array and computed `totals` | Flat `cart_items` collection — one document per item |
| Anonymous support | `anonymousId` on cart document | Not specified (JWT required) |
| Cart merge | Explicit `POST /api/cart/merge` endpoint | Not specified |

### Orders

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Order number | Human-readable `ORD-YYYYMMDD-NNNNNN` format | `ORD-YYYY-NNNNN` format |
| Return status | `returnStatus` per `orderItem` | `return_initiated` as top-level order status |
| Tracking history | Not modeled (delivery events deferred) | `tracking` array on the order document |

### Returns and Support

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Returns | Separate `returnRequests` collection with full status lifecycle: `requested → approved → rejected → label_created → received → refunded → cancelled` | No separate collection; return initiated by updating order `status` to `return_initiated` |
| Support tickets | `supportTickets` collection with `priority`, `category`, `messages` array, `agentSessionId` | `support_tickets` collection with `codex_thread_id` reference; no priority or messages array |
| Ticket statuses | `open`, (escalated implied via agent log) | `open`, `resolved`, `escalated` |

### Chat and AI

| Field | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Chat session storage | `chatSessions` and `chatMessages` collections with `usedMcp`, `tokenUsage` | `codex_sessions` (one per user per type, TTL 30 days) and `codex_messages` (TTL 90 days) |
| Agent audit logs | Dedicated `agentToolAuditLogs` collection with confirmation tracking | Not specified |
| Activity events | `userActivityEvents` collection — 14 required event types | Not specified |

---

## 4. AI and Embedding Layer

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Ollama embedding model | `nomic-embed-text:v1.5` (768 dims) | `nomic-embed-text-v1.5` (768 dims) — model name formatted differently |
| Voyage embedding model | `voyage-4` (1024 dims) | `voyage-3-large` — different model version |
| Search diagram dimensions | Consistent: 768 or 1024 | Inconsistent: diagram shows 1536 dims but model supports 1024 max |
| Embedding versioning | Provider + model + dimensions + text-template version tracked per record; re-embedding required on any change | No versioning; embeddings overwritten on re-ingestion |
| Embedding text hash | `embeddingTextHash` (SHA-256) stored for skip-unchanged optimization | Not stored |
| Ollama document prefix | `search_document: ` prefix required for documents, `search_query: ` for queries | Not specified |
| Voyage input types | `input_type=document` for products, `input_type=query` for search queries via env vars | Not specified |
| LLM providers | OpenAI or Grove/Azure gateway via `LLM_PROVIDER` env var | `openai` or `custom` (any OpenAI-compatible endpoint) |
| LLM env var shape | `LLM_API_BASE_URL` + `LLM_CHAT_COMPLETIONS_PATH` composable | `CUSTOM_LLM_URL` is the full URL including path |
| Grove URL handling | `LLM_API_BASE_URL` configurable without code change | `CUSTOM_LLM_URL` is full URL; spec example hardcodes Grove URL |

### Shopping Assistant AI Integration

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Standard queries | Standard LLM adapter via `LLMClient` | All queries route through Codex MCP |
| Complex support queries | `MCPComplexChatClient` (mandatory for multi-step workflows) | All support queries route through Codex MCP |
| MCP scope | Used only when routing policy triggers it (complex support, multi-step returns) | Used for every assistant and support turn |
| Conversation state | Chat Service stores sessions and messages; Codex thread IDs are internal | `codex_sessions` stores thread IDs; multi-turn state lives in the Codex process |
| Cart upsell | Not specified | LLM one-shot call when user views cart |
| Match reasons | Not specified | LLM one-shot call for top 5 results |

### MCP Integration

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| MCP enabled flag | `CODEX_MCP_ENABLED=true`; health check fails when disabled | `CODEX_MCP_COMMAND` and `CODEX_MCP_ARGS` — no explicit enable flag |
| Health gate | Demo health check must fail if MCP unavailable or disabled | MCP crash triggers auto-restart on next request; 502 on current |
| MCP process lifecycle | Managed by Chat Service; transport configurable (`stdio`, `sse`, `streamable_http`) | Spawned once at FastAPI startup as a subprocess |
| Subprocess arguments | `CODEX_MCP_ARGS=mcp,serve` (comma-separated or JSON array) | `CODEX_MCP_ARGS=-y,codex,mcp-server` via `npx` |
| MCP tool exposure | Ecommerce-safe tools only; explicitly forbids filesystem/shell/developer tools | `approval_mode: never` + no shell tools; tools injected via `config.instructions` |
| Return workflow trigger | Routing policy in Chat Service decides when to invoke MCP | Always MCP for support agent |

---

## 5. Search

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Keyword search index | Atlas Search (Lucene-based) with fuzzy matching and autocomplete | Atlas Search with `lucene.english` analyzer; no fuzzy or autocomplete specified |
| Semantic search backing | Atlas Vector Search on `productEmbeddings` collection (separate) | Atlas Vector Search on `products.embedding` inline field |
| Hybrid weights | Semantic 0.70 / Keyword 0.20 / Popularity 0.10 | Reciprocal Rank Fusion (RRF) with K=60; no fixed weights |
| Result envelope | `{data: {results: [{product, score, matchReason}]}, meta: {provider, model, dimensions}}` | `{query, total, results: [{product_id, ..., match_reason, vector_score, text_score, rrf_score}]}` |
| Sort options | Relevance, price_asc, price_desc, newest, rating | price_asc, price_desc, rating, newest |
| Product count in spec | 44,446 verified | ~44,000 (approximate) |

---

## 6. API Design

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Path prefix | All routes under `/api/` | No prefix (e.g., `/auth/register`, `/products`) |
| Success envelope | `{data: {}, error: null, meta: {requestId}}` | `{data: {}, meta: {page, total}}` |
| Error envelope | `{data: null, error: {code, message}, meta: {requestId}}` | `{detail: "message", code: "CODE"}` |
| Product lookup route | `GET /api/products/:slug` | `GET /products/{id}` |
| Similar products route | `GET /api/products/:id/similar` | `GET /products/{id}/similar` |
| Search route | `POST /api/search/semantic`, `POST /api/search/hybrid`, `GET /api/search/products` | `POST /search` (single endpoint for all modes) |
| Cart routes | All require cookie session; anonymous cart supported | All require JWT |
| Orders route | `GET /api/orders/:orderNumber` | `GET /orders/{id}` |
| Admin console API | `/api/admin/config`, `/api/admin/ingestion/status`, `/api/admin/activity-events`, `/api/admin/audit-logs` | Not specified |
| Test/reset API | `POST /api/test/reset`, `POST /api/test/seed` | Not specified |
| Internal API | `POST /api/internal/agent-audit-logs` (Chat Service writes to Core via token-protected endpoint) | Not specified |

---

## 7. Ingestion Pipeline

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Pipeline stages | 14-stage pipeline including cross-ID validation, HTML sanitization, embedding generation, Atlas upsert | 6 steps (read CSV, load JSON, assign price, embed, upsert, copy image) |
| Images source | `dataset/images/` JPGs served from Core Service local filesystem route | Copied to `static/images/` for FastAPI static file serving |
| `images.csv` usage | Parsed; `link` field stored as `originalUrl` metadata per image | Not referenced |
| Price determinism | Deterministic by `sourceProductId` (SHA-256 seeded) | `seed_price(row.id)` (deterministic implied but not defined) |
| Rating/stock | Deterministic (SHA-256 seeded) | `random.uniform(3.5, 5.0)` and `random.randint(10, 500)` — **non-deterministic** |
| Ingestion output | JSONL artifacts + ingestion report JSON | Direct MongoDB upsert during ingestion |
| Dataset license | MIT | Open Data Commons (ODE) |
| Ingestion resumption | Required: "Ingestion can resume after failure" | Not specified |
| Re-embedding | `--reembed` flag, skip unchanged (hash comparison) | `--reembed` flag, no skip logic |

---

## 8. Configuration

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Config mechanism | `pydantic-settings` `BaseSettings` with env file support | Manual `os.getenv()` calls in custom `from_env()` classmethod |
| Session secret | `SESSION_SECRET` for cookie signing | `JWT_SECRET` / `JWT_ALGORITHM` / `JWT_EXPIRE_MINUTES` |
| Cookie security | `COOKIE_SECURE` env var | Cookie security implicit in JWT storage |
| Image base URL | `PRODUCT_IMAGE_PUBLIC_BASE_URL=/product-images` (relative path prefix) | `IMAGE_BASE_URL=http://localhost:8000/static/images` (full URL) |
| Notable env vars in spec1 only | `LLM_ORGANIZATION_ID`, `LLM_PROJECT_ID`, `LLM_TIMEOUT_MS`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_TEMPERATURE`, `LLM_STREAMING_ENABLED`, `EMBEDDING_TEXT_TEMPLATE_VERSION`, `EMBEDDING_BATCH_SIZE`, `EMBEDDING_TIMEOUT_MS`, `VOYAGE_INPUT_TYPE_DOCUMENT`, `VOYAGE_INPUT_TYPE_QUERY`, `CODEX_MCP_ENABLED`, `CODEX_MCP_URL`, `AUTH_PASSWORD_ENABLED`, `AUTH_GOOGLE_ENVIRONMENTS`, `RATE_LIMIT_*` | Not present |
| Notable env vars in spec2 only | `JWT_EXPIRE_MINUTES`, `VOYAGE_EMBEDDING_MODEL`, `OLLAMA_EMBEDDING_MODEL`, `CUSTOM_LLM_MODEL`, `CUSTOM_LLM_URL` | Not present |

---

## 9. Security

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| CSRF protection | Required for cookie-based auth | Not required (JWT bearer auth) |
| Cookie flags | Secure, HTTP-only, SameSite required; `COOKIE_SECURE` env var | httpOnly, Secure, SameSite=Strict |
| Session token storage | Tokens hashed before storage in `sessions` collection | JWTs are self-contained; no server-side storage |
| OAuth token storage | Encrypt access/refresh tokens if stored | Not specified |
| Prompt injection | Explicit requirement to guard against injection in product descriptions and support messages | Not specified |
| Mutating tool confirmation | Confirmation tokens required for cart/return mutations | Not specified |
| Custom LLM URL safety | URL must not be hardcoded; configurable | URL validated against allowlist |

---

## 10. Observability and Admin Console

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Admin demo console | Full admin console at `/admin` route: ingestion status, provider config, product/embedding counts, recent AI failures, support tickets, returns, activity funnel, MCP readiness | Not specified |
| Required metrics | Service latency, catalogue latency, search latency, embedding throughput, LLM latency and error rate by provider, cart conversion, checkout success, agent session counts, return creation count, activity event counts, MCP complex-chat success/failure rate | Performance targets table only; no metric collection specified |
| Required logs | Request ID, user/anonymous ID, auth events, cart/order events, activity events, search metadata, embedding metadata, LLM metadata, agent tool calls, MCP usage | No PII to console; structured logging only |
| Python/FastAPI version in health | Required in admin console display | Not specified |

---

## 11. Testing

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| Unit tests | Product normalization, synthetic price/inventory, embedding text, provider selection, cart totals, return eligibility, tool authorization, confirmation logic | Not specified |
| Integration tests | Auth, OAuth, ingestion, semantic search (mocked embeddings), cart merge, checkout, return, ticket, LLM adapter (mocked endpoint) | Not specified |
| E2E tests | 7 critical flows listed explicitly | Not specified |
| Load/scale checks | 44K product paging, ingestion resumption, embedding skip-unchanged, latency targets (keyword <500ms, vector <1200ms, AI first token <5s) | Performance target table only |
| Latency targets (chat) | AI chat first token < 5 seconds when streaming | Codex first token < 3s; Codex full reply < 15s; LLM one-shot < 2s |

---

## 12. Scope

| Dimension | ecommerce-demo-spec.md | stylesense_spec.md |
|---|---|---|
| User roles | Guest shopper, registered customer, support/admin operator (seeded admin account required) | Not specified |
| Admin seed user | Mandatory; separate seeded admin for support/admin console | Not specified |
| Delivery plan | 8 phases with explicit exit criteria per phase | Not specified |
| Acceptance checklist | 30-item checklist | Not specified |
| User activity capture | Required: 14 event types covering search, filters, product views, cart, checkout, orders, returns, tickets | Not specified |
| Availability filter | Listed as a required catalogue filter | Not listed |
| Pagination type | Pagination or infinite scroll (both accepted) | Pagination only |

---

## 13. Recommended Changes to `ecommerce-demo-spec.md`

The current `ecommerce-demo-spec.md` is materially stronger than `stylesense_spec.md` in security, auditability, provider abstraction, MCP safety, observability, and testing. Most differences in this document should remain differences. The recommended changes below are limited to places where the current spec is either ambiguous, operationally underspecified, or missing a useful constraint that appears in the alternate draft.

### A. Close Ambiguities in the Current Spec

1. **Make the backend architecture decision explicit.**  
	The current spec says it is "TypeScript-first" and allows either Next.js route handlers or a separate Node.js service. That flexibility is useful early, but it leaves too much room for implementation drift. Add a short architecture decision section that chooses one of:
	- single deployable Next.js app with route handlers, or
	- split frontend/backend deployment with a separate API service.

2. **Specify the frontend-to-backend integration pattern.**  
	The spec defines routes but not whether the frontend will call them directly, use server actions, or use a BFF layer. Add one explicit rule so auth, cookie handling, and assistant streaming are implemented consistently.

3. **Resolve open questions that materially affect delivery.**  
	The open questions section still leaves key scope items undecided:
	- local vs shared-environment Google OAuth enablement,
	- whether S3 image hosting is phase 1 or deferred,
	- whether a separate admin seed user is mandatory,
	- which MCP transport/command is the expected default.

	These should be converted from open questions into defaults so the implementation and tests have one source of truth.

### B. Add Missing Operational Constraints

4. **Add explicit auth lockout/backoff behavior in addition to rate limits.**  
	The current spec requires rate limiting but does not define behavior after repeated failed logins. Add a deterministic rule such as temporary account or IP/email lockout after a configurable threshold. This is one of the few places where the alternate draft is more concrete.

5. **Add password reset token lifecycle requirements.**  
	Password reset endpoints exist, but the spec should also define:
	- token TTL,
	- one-time-use enforcement,
	- storage as hashed token rather than plaintext,
	- invalidation of existing sessions after successful reset.

6. **Define session lifecycle and device/session management behavior.**  
	The `sessions` collection is specified, but the spec does not state whether users can have multiple active sessions, whether logout is single-session or global, or whether password change/reset revokes all sessions. Add these rules explicitly.

7. **Add deterministic rules for synthetic fields beyond price/inventory.**  
	The spec says synthetic values must be deterministic by `sourceProductId`, but the requirement is listed at a high level. Add the same determinism rule explicitly for rating, tags, brand selection, and any synthesized descriptions so ingestion remains reproducible across environments.

8. **Specify ingestion resumability mechanics, not just the requirement.**  
	The spec requires ingestion to resume after failure, but does not define how progress is tracked. Add a minimal rule such as checkpointing by product ID batch, resumable JSONL artifacts, or idempotent upsert batches with persisted ingestion run state.

### C. Tighten Data Model and Search Semantics

9. **Clarify whether user preferences are intentionally minimal or should support richer personalization.**  
	The current `users.preferences` shape only covers gender, sizes, and colors. If shopping guidance and personalization are expected to grow, add either:
	- optional `budgetRange`, `stylePreferences`, and `favoriteCategories`, or
	- an explicit note that richer preference modeling is deferred from v1.

10. **Define product variant strategy explicitly.**  
	Cart items mention `variantId` and `size`, but the product model does not define whether sizes are true variants, derived options, or demo-only selections. Add one short section that defines the product/variant model and the inventory implications.

11. **Define hybrid search ranking method, not just recommended weights.**  
	The spec currently allows either weighted blending or RRF-style fusion. Narrow this down for v1. Otherwise two implementations can both be "correct" while producing very different results and tests.

12. **Add exact handling for search result explanations.**  
	The API returns `matchReason`, and the assistant must explain matches, but the spec does not say whether these explanations are deterministic templates, LLM-generated text, or a combination. Add a rule so search response quality and testing remain stable.

### D. Tighten AI and Support Workflow Boundaries

13. **Specify when support must bypass the standard LLM path and go straight to MCP.**  
	The routing policy lists examples, but the trigger remains somewhat subjective. Add a crisp rule set for v1, for example:
	- any return creation attempt,
	- any multi-order lookup,
	- any ticket escalation,
	- any workflow needing more than one mutating or policy-check tool call.

14. **Define assistant/session retention policy.**  
	`chatSessions` and `chatMessages` are modeled, but retention and cleanup are not. Add TTL or archival rules, especially since transcripts, token usage, and audit logs can grow quickly in demos.

15. **Add explicit support ticket ownership and admin workflow states.**  
	`supportTickets` includes status and priority, but assignment lifecycle is still light. Add states such as `open`, `triaged`, `in_progress`, `resolved`, `closed`, plus optional `assignedToUserId` if the admin console is expected to demonstrate support operations.

### E. Tighten Testability and Demo Operations

16. **Add explicit test/reset data management requirements.**  
	The spec mentions reset/reseed behavior in the delivery plan and comparison matrix, but there is no canonical test-support section defining required APIs or scripts. Add a small section covering:
	- demo reset command/API,
	- deterministic reseed behavior,
	- minimum fixture accounts and sample orders.

17. **Add provider-failure simulation requirements.**  
	The spec is strong on provider abstraction, but tests should explicitly cover:
	- OpenAI/Grove outage,
	- Ollama/Voyage outage,
	- MCP unavailable/timeouts,
	- partial ingestion failure and retry.

18. **Add admin console access control requirements.**  
	The `/admin` route is required, but the spec should explicitly say whether it is hidden in production, limited to seeded admin/support roles, and blocked from customer sessions by default.

### F. Important Note About This Comparison Document

Several entries in the comparison above no longer match the current `ecommerce-demo-spec.md` and should not be treated as gaps in the spec. In particular:

- The current spec does **not** mandate three Python FastAPI services; it is TypeScript-first and still leaves the backend packaging decision open.
- The current spec does **not** define the product `price` object as including `listAmount`; the comparison table overstates that field.
- The current spec does **not** define attributes like `sizeFit`, `styleNote`, or `articleAttributes`; the comparison table overstates product descriptor coverage.
- The current spec's dataset path is `data/fashion-product-images/`, while the repo currently uses `dataset/fashion-dataset/`; that mismatch should be reconciled separately in implementation planning.

Net: `ecommerce-demo-spec.md` does not need a broad rewrite. It mainly needs a small round of clarification and operational tightening so the implementation team has fewer degrees of freedom and fewer hidden decisions.
