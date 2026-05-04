# Chat Service

FastAPI service for the Codex Shopping Assistant and Returns/Support Agent. Chat Service owns chat sessions, messages, pending assistant actions, LLM routing, mandatory local Codex MCP integration, ecommerce-safe tool orchestration, and agent audit logging.

---

## Architecture Overview

```
Browser / Next.js (port 3000)
        │  cookie forwarding (core_session)
        ▼
  Chat Service (port 4002)
  ┌──────────────────────────────────────────────────────┐
  │  FastAPI + auth middleware                           │
  │                                                      │
  │  ┌────────────────┐   ┌──────────────────────────┐  │
  │  │ ShoppingAgent  │   │   SupportAgent           │  │
  │  │ (keyword-      │   │ (MCP-assisted returns)   │  │
  │  │  routed)       │   └────────────┬─────────────┘  │
  │  └───────┬────────┘                │                 │
  │          │                         │                 │
  │  ┌───────▼─────────────────────────▼─────────────┐  │
  │  │  Tool Layer (Python callables)                 │  │
  │  │  SearchTools  │  CoreTools                     │  │
  │  └───────┬──────────────────┬─────────────────────┘  │
  │          │                  │                        │
  │  ┌───────▼──────┐  ┌────────▼────────┐              │
  │  │  LlmClient   │  │  McpClient      │              │
  │  │  (text only) │  │  (Codex facade) │              │
  │  └──────────────┘  └─────────────────┘              │
  │                                                      │
  │  ┌──────────────────────────────────────────────┐   │
  │  │  ChatStore                                   │   │
  │  │  file: artifacts/chat_service/state.json     │   │
  │  │  (MongoDB Atlas when MONGODB_URI configured) │   │
  │  └──────────────────────────────────────────────┘   │
  └──────────────────────────────────────────────────────┘
        │                         │
        ▼                         ▼
  Search Service (4001)    Core Service (4000)
  hybrid search            cart, orders, returns,
  product facts            auth, support tickets
```

---

## Current Implementation: Deterministic-Routed Agents

The current implementation uses **deterministic Python routing** to dispatch each user turn to the right tool call. The LLM is used only as a **text formatter** — it receives tool results and produces natural-language output, but it does not select or invoke tools. Ecommerce mutations (cart changes, return creation) are always gated behind explicit user confirmation.

`app/tools/registry.py` defines OpenAI-compatible function specs (`SHOPPING_TOOLS`, `SUPPORT_TOOLS`) that describe all agent capabilities. These schemas are not yet wired to the LLM as function-calling tools; they are prepared for that integration in a future iteration.

### ShoppingAgent (`app/agents/shopping.py`)

Handles product discovery, recommendations, outfit pairing, comparison, and cart add proposals.

Routing per user turn (deterministic keyword matching):

| Message signal | Dispatch |
|---|---|
| Contains `"compare"` | `compare_from_context()` — fetches two products side-by-side |
| On product page + `"match"/"pair"/"outfit"` | `matching_products()` — outfit complementing via `find_matching_products` |
| On product page (other questions) | `answer_product_question()` — product facts from Search |
| Everything else | `recommend_with_cart_action()` — hybrid search + pending add-to-cart |

Detailed flow for `recommend_with_cart_action()`:

1. Extracts structured filters from message text (colour, usage, season, price cap, article type) via `filters_from_message()`.
2. Calls `SearchTools.search_products()` → Search `/api/search/hybrid`.
3. Relaxes filters and retries if first search returns empty.
4. Optionally calls `CoreTools.get_cart()` to exclude items already in cart when `cartAware: true`.
5. Creates a `pending add_to_cart` action — never mutates cart directly.
6. Calls `LlmClient.chat_completion()` with recent session history for response wording; falls back to a deterministic string if LLM is unavailable.
7. Persists the assistant message + `suggestedProducts` snapshot + `pendingActionId` to `chatMessages`.

### SupportAgent (`app/agents/support.py`)

Handles return eligibility checks, MCP-assisted return planning, and confirmed return creation.

Flow per user turn:

1. Loads prior session turns from `chatMessages`.
2. Uses explicit `orderId`/`orderItemId` from the request context if provided (e.g., user clicked an order).
3. If IDs are missing, calls `infer_order_context()` which calls `CoreTools.list_user_orders()` and infers the relevant order by matching order number or item title keywords in the user's message, defaulting to the most recent order.
4. Calls `McpClient.plan_support_return()` — returns live MCP plan when `CODEX_MCP_TRANSPORT=http` and endpoint is reachable; otherwise returns a static ecommerce-safe plan.
5. Calls `CoreTools.get_order()`, `CoreTools.check_return_eligibility()`, and `CoreTools.get_return_policy()`.
6. If ineligible: calls LLM to compose a clear ineligibility explanation.
7. If eligible: creates a `pending create_return_request` action and waits for user confirmation.
8. Calls `LlmClient.chat_completion()` for response wording with deterministic fallback.

### Tool Layer

The tool layer is plain Python — each method makes a synchronous HTTP call to Search or Core. Tool functions are invoked directly by the agents, not via LLM function calling.

**SearchTools** (`app/tools/search.py`):

| Method | Search endpoint | Called by |
|---|---|---|
| `search_products()` | `POST /api/search/hybrid` | ShoppingAgent recommend, filter retry |
| `get_product()` | `GET /api/products/{id}` | ShoppingAgent product question, matching reference fetch |
| `get_similar_products()` | `GET /api/products/{id}/similar` | Defined, not yet agent-dispatched |
| `find_matching_products()` | Calls `get_product` + `search_products` | ShoppingAgent outfit matching |
| `compare_products()` | Multiple `get_product` calls | ShoppingAgent compare |

**CoreTools** (`app/tools/core.py`):

| Method | Core endpoint | Called by |
|---|---|---|
| `get_cart()` | `GET /api/cart` | ShoppingAgent when `cartAware: true` |
| `add_to_cart()` | `POST /api/cart/items` | ShoppingAgent on confirm |
| `update_cart_item()` | `PATCH /api/cart/items/{id}` | Defined, not yet agent-dispatched |
| `remove_from_cart()` | `DELETE /api/cart/items/{id}` | Defined, not yet agent-dispatched |
| `list_user_orders()` | `GET /api/orders` | SupportAgent `infer_order_context` |
| `get_order()` | `GET /api/orders/{id}` | SupportAgent eligibility check |
| `check_return_eligibility()` | `POST /api/returns/check-eligibility` | SupportAgent |
| `create_return_request()` | `POST /api/returns` | SupportAgent on confirm |
| `get_return_policy()` | Local constant | SupportAgent |
| `create_support_ticket()` | `POST /api/support/tickets` | Defined, not yet agent-dispatched |
| `get_user_preferences()` | `GET /api/me` | Defined, not yet agent-dispatched |
| `save_user_preference()` | `PATCH /api/me/preferences` | Defined, not yet agent-dispatched |
| `write_activity()` | `POST /api/activity-events` | ShoppingAgent after recommendation |
| `write_audit_log()` | `POST /api/internal/agent-audit-logs` | `audit_tool_call()` helper |

### LLM Client (`app/llm/client.py`)

- OpenAI-compatible Chat Completions adapter.
- Configurable provider, model, base URL, API key, temperature, max tokens, timeout.
- Called only for **response wording** — receives `messages` (system prompt + session history + tool result), returns a text string. Does not use `tools` / function-calling at this time.
- When `LLM_API_KEY` is absent or a placeholder: raises `ServiceHttpError(503)` — agents catch this and use a deterministic fallback string.

### MCP Client (`app/mcp/client.py`)

- `readiness()` checks the configured command (`stdio`) or HTTP endpoint and reports MCP readiness in the health response.
- `plan_support_return()` returns a support return workflow plan:
  - `CODEX_MCP_TRANSPORT=http` and endpoint reachable: calls `POST {CODEX_MCP_URL}/tools/execute` with `planReturnWorkflow`.
  - All other cases: returns the static ecommerce-safe plan (`getOrder → checkReturnEligibility → createReturnRequest`).
- Live MCP transport is wired but the `stdio` command form does not execute actual tool calls at runtime; the static plan is deterministic and sufficient for the demo.

### Pending Action Gate

Cart mutations and return creation always go through a confirmation gate:

```
Agent creates pending action (status=pending, TTL=900s)
    │
    ▼
Frontend shows confirm/cancel button
    │
    ▼
POST /api/assistant/actions/confirm  {actionId, confirmed: true}
    │
    ▼
Agent executes Core mutation, marks action completed
```

Confirmed actions execute `CoreTools.add_to_cart()` or `CoreTools.create_return_request()` and write an audit log entry.

### Persistence (ChatStore — `app/store.py`)

- MongoDB Atlas is the source of truth when `MONGODB_URI` is configured.
- File-backed fallback at `artifacts/chat_service/state.json` for local dev without Atlas.
- `chatSessions`: `type`, `userId`, `context`, `status`, `summary`, `messageCount`, `createdAt`, `updatedAt`.
- `chatMessages`: `sessionId`, `role`, `content`, `metadata` (includes `suggestedProducts`, `pendingActionId`), `createdAt`.
- `pendingActions`: `sessionId`, `userId`, `type`, `payload`, `status`, `expiresAt`, `createdAt`, `updatedAt`.

### Auth

- Every protected endpoint calls `CoreTools.get_me` via `require_user_context(request)`.
- The Core session cookie is forwarded on all downstream Core/Search calls.
- No JWT tokens; all auth is cookie-based.

---

## Planned: LLM Tool-Calling Architecture

The tool registry (`app/tools/registry.py`) is structured to enable full LLM-driven tool orchestration in a future iteration. When this is wired:

```
User message
    │
    ▼
LLM receives: system prompt + session history + SHOPPING_TOOLS/SUPPORT_TOOLS
    │
    ▼
LLM returns tool_calls (e.g. search_products, find_matching_products, compare_products)
    │
    ▼
Python executes the selected tool functions
    │
    ▼
Tool results appended to messages, LLM produces final response
    │
    ▼ (repeat until no more tool_calls)
Confirm mutation (add to cart / create return)
    │
    ▼
Final response + suggestedProducts + pendingAction
```

This would replace the current deterministic keyword-based dispatch, allowing the LLM to decide which tools to call and in what order based on the user's intent.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Service readiness with LLM + MCP metadata |
| `POST` | `/api/assistant/shopping/sessions` | Create a shopping assistant session |
| `GET` | `/api/assistant/shopping/sessions` | Find most recent active shopping session |
| `GET` | `/api/assistant/shopping/sessions/history` | List shopping chat sessions with cursor pagination |
| `POST` | `/api/assistant/shopping/messages` | Send a shopping assistant message |
| `GET` | `/api/assistant/shopping/sessions/{id}/messages` | Retrieve session message history |
| `POST` | `/api/assistant/support/sessions` | Create a support/returns session |
| `GET` | `/api/assistant/support/sessions` | Find most recent active support session |
| `GET` | `/api/assistant/support/sessions/history` | List support chat sessions with cursor pagination |
| `GET` | `/api/assistant/support/sessions/{id}/messages` | Retrieve support session message history |
| `POST` | `/api/assistant/support/messages` | Send a support agent message |
| `POST` | `/api/assistant/actions/confirm` | Confirm or cancel a pending mutating action |

---

## Data Model

### `chatSessions`
```json
{
  "_id": "<hex24>",
  "type": "shopping | returns_support",
  "userId": "<userId>",
  "context": { "entryPoint": "catalogue", "productId": null },
  "status": "active",
  "summary": "Find casual shoes under 3000.",
  "messageCount": 2,
  "createdAt": "<ISO8601>",
  "updatedAt": "<ISO8601>"
}
```

### `chatMessages`
```json
{
  "_id": "<hex24>",
  "sessionId": "<sessionId>",
  "role": "user | assistant",
  "content": "<text>",
  "metadata": {
    "suggestedProducts": [ "<compact product>" ],
    "pendingActionId": "<actionId>",
    "context": {}
  },
  "createdAt": "<ISO8601>"
}
```

### `pendingActions`
```json
{
  "_id": "<hex24>",
  "sessionId": "<sessionId>",
  "userId": "<userId>",
  "type": "add_to_cart | create_return_request",
  "payload": {},
  "status": "pending | completed | cancelled | error",
  "expiresAt": "<ISO8601>",
  "createdAt": "<ISO8601>",
  "updatedAt": "<ISO8601>"
}
```

---

## Run

Start Core and Search first, then Chat Service:

```bash
export CORE_SERVICE_BASE_URL=http://127.0.0.1:4000
export SEARCH_SERVICE_BASE_URL=http://127.0.0.1:4001
export CHAT_SERVICE_INTERNAL_TOKEN=replace-with-chat-service-token
PYTHONPATH=services/chat_service uvicorn app.main:app --host 127.0.0.1 --port 4002
```

Seed Core demo data before exercising assistant flows:

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
| `CORE_SERVICE_BASE_URL` | `http://localhost:4000` | Core Service for auth, carts, orders, returns, support |
| `SEARCH_SERVICE_BASE_URL` | `http://localhost:4001` | Search Service for products |
| `CHAT_SERVICE_INTERNAL_TOKEN` | `` | Internal credential for audit log writes to Core |
| `CHAT_SERVICE_DATA_PATH` | `./artifacts/chat_service/state.json` | File-backed state path |
| `MONGODB_URI` | `` | Atlas URI; enables MongoDB persistence when set |
| `MONGODB_DB` | `ecommerce_demo` | Atlas database name |
| `LLM_PROVIDER` | `openai` | Provider name (display only) |
| `LLM_MODEL` | `gpt-5.4` | Model identifier sent to the API |
| `LLM_API_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `LLM_API_KEY` | `` | Required for live LLM calls; absent → deterministic fallback text |
| `LLM_TIMEOUT_MS` | `60000` | Per-request LLM timeout |
| `LLM_MAX_OUTPUT_TOKENS` | `1200` | Max tokens per LLM response |
| `LLM_TEMPERATURE` | `0.3` | LLM sampling temperature |
| `LLM_STREAMING_ENABLED` | `true` | Streaming flag sent in the request payload |
| `CODEX_MCP_ENABLED` | `true` | Must be `true` for demo readiness gate |
| `CODEX_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `CODEX_MCP_COMMAND` | `codex` | Command for stdio transport |
| `CODEX_MCP_URL` | `http://localhost:9000/mcp` | URL for HTTP/SSE transport |
| `ASSISTANT_ACTION_TTL_SECONDS` | `900` | Pending action expiry window |
| `CHAT_LOG_LEVEL` | `DEBUG` | Log verbosity |

Do not commit real credentials. Use shell exports or a local `.env`.

`CHAT_SERVICE_INTERNAL_TOKEN` must match the same variable loaded by Core Service. Placeholder values such as `replace-with-chat-service-token` are intentionally rejected by Core Service, so use a real local token string for audit-log writes during tests.

---

## Validation

```bash
# Compile check
PYTHONPATH=services/chat_service python3 -m py_compile $(find services/chat_service/app -name '*.py' -print)

# Agent API tests (requires all three services running)
pytest tests/api/test_ai_agents_mcp.py

# Full cross-service suite
pytest tests/api
```
