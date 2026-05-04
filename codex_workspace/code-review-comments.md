# Code Review Comments

**Reference specs:** `ecommerce-demo-spec.md` (authoritative), `stylesense_spec.md`, `README.md`  
**Scope:** All three backend services, Next.js frontend, API/E2E test suites  
**Review pass:** Second pass — reflects all changes made since the first review

---

## Resolved Since First Review

The following issues from the first review are confirmed fixed:

- Real MongoDB credentials removed from `.env.example` (now a safe placeholder)
- Session cookies now use `secure=settings.cookie_secure` and read `COOKIE_SECURE` env var
- `TEST_ADMIN_TOKEN` and service tokens blocked when they match placeholder prefixes via `is_configured_secret()`
- CORS middleware added to all three services
- Rate limiting implemented via `InMemoryRateLimitMiddleware` on all three services
- Frontend BFF proxy no longer auto-injects admin token for admin/test paths (now 404s)
- Password hashing now uses Argon2id when `PASSWORD_HASH_ALGORITHM=argon2id`; `argon2-cffi` declared in core_service dependencies
- MCP client now uses `shutil.which()` for stdio readiness and HTTP probe for HTTP/SSE transport
- LLM client is now called in both shopping and support agents with a deterministic fallback
- Google OAuth now generates state, builds proper parameters, validates credentials, and implements the callback with CSRF state check
- Password reset endpoints are now functional
- `assistant_opened` added to `ALLOWED_EVENT_TYPES`
- Activity event write failures in Search Service are now silently swallowed (no longer 502)
- Return eligibility gates the pending action creation
- Return reason/condition/resolution now collected from user through `ConfirmActionRequest` and `SupportClient`
- All 7 missing frontend pages now exist (cart, checkout, orders, support, admin, and more)
- Product filter panel now has facet-driven dropdowns for category, subcategory, article type, season, usage, and a price input
- Size selector is now a controlled component in `ProductDetailClient`
- Suggested products rendered in `AssistantDrawer`
- React keys use `crypto.randomUUID()` instead of message strings
- Proxy forwards only relevant cookies per service (search gets none; chat gets only `core_session`)
- `find_product()` in Atlas mode now uses a targeted query instead of a full collection scan
- Embedding generation now supports checkpoint/resume
- Double HTML unescape in `clean_text()` fixed (single `html.unescape` call per stage)
- `stable_product_object_id()` now uses SHA-256 instead of SHA-1
- Pagination added to product catalogue with Previous/Next controls

---

## 1. Open Security Issues

### 1.1 `ADMIN_SEED_PASSWORD` is empty by default — admin login requires no password
**File:** `.env.example:33`, `services/core_service/app/store.py:181`
```
ADMIN_SEED_PASSWORD=
```
```python
"passwordHash": hash_password(self.config.admin_seed_password),
```
`hash_password("")` is called when the env var is not set. Anyone can log into the demo admin account (`admin@example.test`) via `POST /api/auth/login` with an empty password. The admin account has `roles: ["admin", "customer"]`. The `.env.example` should require a non-empty value here; `is_configured_secret()` should gate seed user creation.

### 1.2 Google OAuth callback returns JSON instead of redirecting the browser
**File:** `services/core_service/app/auth/routes.py:188-191`
```python
return ok({"user": public_user})
```
A real OAuth callback is a browser GET redirect. After the session cookie is set, the callback must issue a `RedirectResponse` to a frontend route (e.g., `/products`). Returning a JSON body leaves the browser displaying raw JSON after the OAuth handshake. The spec requires "Complete Google OAuth" — this is incomplete.

### 1.3 Google OAuth does not verify `email_verified` before account linking
**File:** `services/core_service/app/auth/routes.py:184`
The spec says "OAuth account records are linked by verified email where safe." `exchange_google_code()` calls the userinfo endpoint but never checks `user_data.get("email_verified")`. A Google account with an unverified email could be used to claim an existing account, creating an account-takeover vector in shared demo environments.

### 1.4 Rate limiting is disabled by default if env vars are not set
**File:** `services/core_service/app/config.py:49`, `services/search_service/app/config.py:41`, `services/chat_service/app/config.py:39`
```python
rate_limit_auth_per_minute: int = Field(default=0)
```
`InMemoryRateLimitMiddleware` skips enforcement when `requests_per_minute <= 0`. The code default is 0, so unless the env var is explicitly set, all three services start with rate limiting disabled. The `.env.example` has the values but they must be sourced; a fresh deployment without `.env` loading has no protection.

### 1.5 `InMemoryRateLimitMiddleware` state is not shared across workers
**File:** `services/core_service/app/security.py:30-61`
The `self.window` dict is per-process. With multiple uvicorn workers (`--workers N`), each worker enforces its own independent limit. The effective per-client rate is `N × requests_per_minute`. For production-grade demo hardening, a shared store (Redis) is needed.

### 1.6 `InMemoryRateLimitMiddleware` window dict grows without eviction
**File:** `services/core_service/app/security.py:37`
```python
self.window: dict[str, tuple[float, int]] = {}
```
Every unique `(client_ip, path)` pair creates a permanent entry. Under sustained traffic, memory usage grows unboundedly. Expired windows are updated in place on the next hit for that key, but keys from clients that stop sending requests are never removed.

### 1.7 Rate limit is per exact path, not per auth prefix
**File:** `services/core_service/app/security.py:46`
```python
key = f"{client_host}:{request.url.path}"
```
`/api/auth/register` and `/api/auth/login` are tracked as separate buckets. A client can exhaust 10 login attempts AND 10 registration attempts independently. The spec's intent is a combined auth budget per client.

---

## 2. Spec Deviations — Backend

### 2.1 MCP client verifies binary existence but never starts or communicates with the process
**File:** `services/chat_service/app/mcp/client.py:37-46`
```python
command_path = shutil.which(self.config.codex_mcp_command)
return {"ready": bool(command_path and self.config.codex_mcp_args.strip()), ...}
```
`shutil.which("codex")` only checks whether `codex` is on `$PATH`. It does not start the process, send a JSON-RPC handshake, or verify that `codex mcp serve` functions correctly. `plan_support_return()` still returns a hardcoded dict — no MCP message is ever sent. The spec says "mandatory local Codex MCP server integration" and health must fail if it is unavailable. The current check would report `ready: True` for any system with `codex` installed, even if the MCP server command fails or the binary is corrupted.

### 2.2 LLM streaming is claimed in config but not implemented
**File:** `services/chat_service/app/llm/client.py:50`, `services/chat_service/app/http.py`
`LLM_STREAMING_ENABLED=true` is sent in the payload to the provider, but `request_json()` reads the full response body synchronously. The spec requires "streaming responses when provider supports it" and a "Chat first token" latency target. No SSE or chunked response is forwarded to the frontend. Responses are always full-blocking, regardless of the streaming flag.

### 2.3 Config still uses manual `os.getenv()` instead of `pydantic-settings` `BaseSettings`
**File:** All three `config.py` files
The spec (stylesense_spec.md §4) specifies `pydantic-settings BaseSettings` with `env_file = ".env"`. All three services use `pydantic.BaseModel` with custom `from_env()` classmethods. `.env` files are not loaded automatically. Env vars must be exported to the shell before startup.

### 2.4 Cart mutation routes do not emit server-side activity events
**File:** `services/core_service/app/carts/routes.py`
The spec (§8.8) requires server-side activity capture for cart mutations: `cart_item_added`, `cart_item_updated`, `cart_item_removed`. The cart routes call `store.add_cart_item()` etc. but do not call `store.add_activity()`. If the store does not emit them internally, the API tests expecting these events will fail.

### 2.5 `validate_dataset()` does not enforce expected dataset counts
**File:** `services/core_service/app/ingestion/pipeline.py:357-378`
The spec (§11.2) specifies exact expected counts: 44,446 `styles.csv` rows, 44,446 JSON files, 44,441 JPGs. The function counts and reports these but does not raise an error when they diverge. A partial dataset is silently accepted and produces no warning in the ingestion report.

### 2.6 Ingestion report `productsInserted`/`productsUpdated` are misleading
**File:** `services/core_service/app/ingestion/pipeline.py:474-476`
```python
productsInserted=products_processed,
productsUpdated=0,
```
The pipeline only writes JSONL files. Atlas upserts happen in a separate step. The report implies records were inserted into MongoDB when they were not. These fields reflect JSONL writes, not database state.

### 2.7 `similar_products` endpoint returns empty list (200) for a non-existent product
**File:** `services/search_service/app/search/read_model.py:218-233`
`similar_products()` calls `find_product()`, and if it returns `None`, returns `[]` silently. The route returns HTTP 200 with an empty list for an invalid product ID, where a 404 would be more correct and useful for debugging.

---

## 3. Anti-patterns and Hardcoded Values

### 3.1 Shopping agent hardcodes `size: "M"` for add-to-cart proposals
**File:** `services/chat_service/app/agents/shopping.py:96`
```python
{"productId": product["_id"], "quantity": 1, "size": "M"},
```
Every cart proposal from the shopping agent uses `"M"` regardless of what the user requested. The spec's cart item identity includes size as a meaningful field.

### 3.2 Support confirmation hardcodes `resolution: "refund"`
**File:** `apps/web/components/SupportClient.tsx:65`
```typescript
body: JSON.stringify({ ..., resolution: "refund" })
```
The resolution is hardcoded to `"refund"`. The spec supports three resolutions: refund, exchange, store credit. There is no UI control for the user to choose.

### 3.3 Checkout hardcodes country as `"IN"`
**File:** `apps/web/components/CheckoutClient.tsx:14`
```typescript
country: "IN"
```
Country is not a user-editable field in the checkout form. For a demo targeting India this is acceptable, but it should be either a visible read-only field or configurable via env.

### 3.4 `FacetSelect` silently truncates to 24 options
**File:** `apps/web/components/ProductsClient.tsx:244`
```typescript
{values.slice(0, 24).map((item) => (
```
Facets with more than 24 values (e.g., `articleType` has many entries in the 44K dataset) are silently truncated. Users cannot filter by values beyond position 24, with no indication that options are hidden.

### 3.5 Admin page shows no error when `TEST_ADMIN_TOKEN` is not configured
**File:** `apps/web/app/admin/page.tsx:17-24`
```typescript
const token = process.env.TEST_ADMIN_TOKEN;
if (!token) return null;
```
`fetchCoreAdmin` returns `null` silently when the token is not set. The admin console renders with empty panels and no explanation. A "Admin token not configured" message would make the failure obvious.

### 3.6 `confirm_action` route mutates action payload directly without saving
**File:** `services/chat_service/app/api/routes.py:96-104`
```python
if payload.reason:
    action["payload"]["reason"] = payload.reason
```
`store.find_action()` returns a direct mutable reference. The in-memory mutation is applied but `save()` is only called from `complete_action()`. If an exception occurs between the mutation and completion, the updated reason/condition would be lost on a server restart. `find_action()` should return a clone, or the mutation should go through a dedicated store method.

---

## 4. Frontend Issues

### 4.1 Checkout skips the quote step — totals are not shown before placing order
**File:** `apps/web/components/CheckoutClient.tsx:27-31`
The checkout page calls `POST /api/core/checkout/place-order` directly without first calling `POST /api/core/checkout/quote`. The spec requires an "Order review" step where calculated totals are shown before confirmation. The user sees no price breakdown before placing the order.

### 4.2 Cart page does not trigger cart merge on initial load
**File:** `apps/web/components/CartClient.tsx`
`CartClient` fetches the cart and shows items. It does not check whether an anonymous cart needs to be merged into the authenticated cart after login. The merge call (`POST /api/core/cart/merge`) is only in `AuthForms.tsx` immediately after login. A user who logs in from a different page and then navigates to `/cart` will see the authenticated cart without the anonymous items merged.

### 4.3 Support page always uses the most recent order's first item — no order/item selection
**File:** `apps/web/components/SupportClient.tsx:33-36`
```typescript
const order = orders[0];
const item = order?.items[0];
```
The first order and first item are always used without user input. The spec requires the agent to let users "choose the order and item they want help with." A user with multiple orders cannot return an item from any order other than the most recent.

### 4.4 No quantity selector in cart or product pages
**File:** `apps/web/components/CartClient.tsx`, `apps/web/components/ProductDetailClient.tsx`
The cart page shows quantities but provides no controls to update or remove items. The product detail add-to-cart always sends `quantity: 1` with no selector. The spec requires "Update quantity, Remove item" cart controls.

### 4.5 `HeaderNav` fires two API calls on every page load — no caching
**File:** `apps/web/components/HeaderNav.tsx:12-16`
`/api/core/me` and `/api/core/cart` are called on every mount, including non-interactive page loads. The responses are not cached. A user browsing multiple product pages generates two uncached requests per navigation.

### 4.6 Auth state not shown on header sign-in/sign-out navigation
**File:** `apps/web/components/HeaderNav.tsx`
While `HeaderNav` conditionally renders the username or sign-in/register links based on the user state, there is no "Sign out" button. A logged-in user has no way to log out from the header. The spec requires "User can sign out."

### 4.7 No page exists for `/account/returns`
**File:** `apps/web/app/`
The spec (§13.1) requires a Returns page at `/account/returns`. The current routes include `/orders` but no returns history page. A user who created a return through the support agent has no way to view it.

### 4.8 Pagination hardcodes page size at 12 with no user control
**File:** `apps/web/components/ProductsClient.tsx:68`
```typescript
params.set("limit", "12");
```
Page size is hardcoded at 12 and not user-configurable. The pagination `Math.ceil(total / 12)` also hardcodes 12 for the page count calculation, so if the server limit is changed the page count would be wrong.

---

## 5. Performance and Scalability

### 5.1 `atlas_products()` loads all 44K products on every search, facets, and similar-products call
**File:** `services/search_service/app/search/read_model.py:101-110`
`search_products()`, `active_products()`, `facets()`, and `similar_products()` all call `all_products()` → `atlas_products()` which runs `list(collection.find(...))` with no `limit`, `skip`, or cursor batching. With 44,446 products, every search or facets request fetches and deserializes the entire collection into Python memory. Only `find_product()` uses a targeted Atlas query.

### 5.2 `similar_products()` still performs an O(n) attribute-scoring pass in local mode
**File:** `services/search_service/app/search/read_model.py:218-233`
When Atlas is not configured, `similar_products()` loads all active products and scores each by attribute overlap in Python. At 44K products this is an O(n) pass per request. The spec requires Atlas Vector Search for similar products.

### 5.3 File-backed stores have no concurrency protection
**File:** `services/core_service/app/store.py:129-136`, `services/chat_service/app/store.py:64-71`
Both stores write the entire state JSON with `path.write_text()`. Under concurrent async requests with a single uvicorn worker, two simultaneous requests can each read the old state and one will overwrite the other's write. There is no file locking or in-memory mutex.

---

## 6. Test Gaps

### 6.1 MCP health test passes trivially — does not verify live process
**File:** `tests/api/test_ai_agents_mcp.py:13-17`
```python
assert health["mcp"]["ready"] is True
```
This test will pass whenever `codex` is on `$PATH`. It does not verify that the MCP process can be started or that a JSON-RPC exchange succeeds. The spec requires that the health check fails when MCP is actually unavailable. A test with `CODEX_MCP_ENABLED=false` or a missing binary should assert `ready: False`.

### 6.2 MCP routing test asserts a hardcoded response field
**File:** `tests/api/test_ai_agents_mcp.py:96`
```python
assert reply["usedMcp"] is True
```
`usedMcp: True` is always set in `support_agent.answer()` when order and item IDs are present, regardless of whether the MCP process was invoked. The test does not verify real MCP invocation.

### 6.3 `test_ingestion_status_reports_kaggle_dataset...` requires the full dataset
**File:** `tests/api/test_provider_config_ingestion.py:54-58`
```python
assert status["stylesCsvRows"] == 44446
assert status["localImageFiles"] == 44441
```
These assertions require the full 44K-product dataset to have been pre-loaded. The `seeded_demo_data` fixture only seeds 25 products via `fashion-minimal`. This test will fail on any fresh dev environment and is not appropriate as a module-scoped unit test.

### 6.4 No test verifying `ADMIN_SEED_PASSWORD` cannot be empty
No test asserts that the admin seed user cannot be created with a blank password or that login is rejected with an empty password.

### 6.5 No test for `email_verified` enforcement on Google OAuth account linking
The Google OAuth callback test only verifies the disabled-state 404. There is no test that an account with `email_verified: false` is rejected or handled safely.

### 6.6 No test for LLM fallback behavior
`ShoppingAgent.llm_text()` and `SupportAgent.llm_text()` fall back to a deterministic string when the LLM call fails. No test verifies the fallback message is used when `LLM_API_KEY` is invalid.

### 6.7 No test for the return ineligibility path in the support agent
All return tests use freshly placed orders (which are immediately eligible). No test sends an ineligible item (expired window, already returned, final sale) and verifies the agent responds with the ineligibility reason without creating a pending action.

### 6.8 E2E support test expects `/support` to collect reason and condition via labels
**File:** `tests/e2e/ecommerce-demo.spec.ts:115-117`
```typescript
await page.getByLabel(/reason/i).fill("Size issue");
await page.getByLabel(/condition/i).selectOption({ label: "Unused" });
```
`SupportClient` uses `aria-label="Reason"` and `aria-label="Condition"`. `getByLabel(/reason/i)` matches ARIA labels, which should resolve correctly, but `getByLabel(/condition/i)` looks for a label element. The Condition field uses `aria-label` on a `<select>`, not a `<label>` element. This selector may not match in Playwright.

### 6.9 `conftest.py` fixture does not restore state between tests in the same module
**File:** `tests/api/conftest.py`
State is reset once at module start. Tests that mutate state (place orders, create returns) affect subsequent tests. If ordering changes, tests may fail intermittently.

### 6.10 No test for `secure` cookie flag
No assertion checks that the `core_session` cookie is set with `Secure=True` in non-development environments.

### 6.11 No test for rate limiting behavior
The spec requires rate limiting on auth, search, and chat. No test sends more than `RATE_LIMIT_AUTH_PER_MINUTE` requests and asserts a 429 response.
