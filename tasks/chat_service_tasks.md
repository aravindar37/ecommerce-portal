# Chat Service Task List

Scope: `services/chat_service`

Chat Service owns Codex Shopping Assistant, Codex Returns and Support Agent, LLM routing, local Codex MCP integration, chat sessions/messages, agent action confirmation, tool orchestration, and agent audit logging. Chat Service must call Core Service and Search Service APIs for retrieval and tool calls.

## Foundation

- [x] Create the FastAPI app structure under `services/chat_service/app` with routers/modules for `agents`, `api`, `llm`, `mcp`, and `tools`.
  - Validation: `PYTHONPATH=services/chat_service python3 -m py_compile $(find services/chat_service/app -name '*.py' -print)`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

- [x] Implement typed Chat Service config for Core/Search URLs, service tokens, LLM provider/model/base URL, streaming, timeout, MCP command/transport/URL, and action confirmation settings.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_admin_config_exposes_provider_choices_without_secrets`

- [x] Validate Core-issued user sessions and forward authenticated context to Core/Search service calls.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

- [x] Implement health/readiness checks that fail demo readiness if mandatory Codex MCP is disabled or unavailable.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_health_check_requires_mandatory_local_codex_mcp_readiness`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

## LLM and MCP Clients

- [x] Implement OpenAI-compatible Chat Completions adapter with configurable `LLM_API_BASE_URL`, `LLM_CHAT_COMPLETIONS_PATH`, `LLM_MODEL`, API key, timeout, max tokens, temperature, and streaming.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

- [x] Implement Grove/Azure gateway-compatible routing using the same OpenAI-compatible adapter and configurable URL.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_admin_config_exposes_provider_choices_without_secrets`

- [x] Implement mandatory local Codex MCP client for complex support workflows with configured transport, command/args or URL, timeout, readiness checks, and safe ecommerce-only tool exposure.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_health_check_requires_mandatory_local_codex_mcp_readiness`
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp`

## Chat Persistence and Audit

- [x] Implement `chatSessions` and `chatMessages` persistence for shopping and support session types.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

- [x] Implement `agentToolAuditLogs` writes for every tool call with session, user, agent type, tool name, input/output, status, confirmation metadata, and timestamps.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_agent_tool_calls_are_audited`

- [x] Ensure provider/model/token usage/MCP usage metadata is stored internally but not leaked in user-facing assistant response bodies.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

## Tool Registry and Service Calls

- [x] Implement Search-backed tools: `searchProducts`, `getProduct`, and `getSimilarProducts`.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_answers_product_questions_using_product_facts`

- [x] Implement Core-backed cart/user tools: `getCart`, `addToCart`, `removeFromCart`, `updateCartItem`, `getUserPreferences`, and `saveUserPreference`.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`
  - Validation: `pytest tests/api/test_cart_checkout_orders.py`

- [x] Implement Core-backed order/return/support tools: `listUserOrders`, `getOrder`, `getOrderItem`, `checkReturnEligibility`, `createReturnRequest`, `createSupportTicket`, `appendTicketMessage`, and `getReturnPolicy`.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp`
  - Validation: `pytest tests/api/test_returns_support_agent.py`

- [x] Enforce schema validation, ownership checks, prompt-injection resistance, and no direct database writes for Core/Search-owned resources.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`
  - Validation: `pytest tests/api/test_returns_support_agent.py::test_return_creation_rejects_non_owner_order`

## Shopping Assistant

- [x] Implement `POST /api/assistant/shopping/sessions` to create shopping assistant sessions with entry point and optional product/cart context.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

- [x] Implement `POST /api/assistant/shopping/messages` for recommendations, comparisons, gift guidance, outfit/use-case guidance, cart-aware suggestions, size/color clarification, product fact answers, and concise responses.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_answers_product_questions_using_product_facts`

- [x] Implement add-to-cart proposal flow requiring explicit user confirmation before mutating Core cart state.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

- [x] Write assistant recommendation and cart mutation activity events through Core Service.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

## Returns and Support Agent

- [x] Implement `POST /api/assistant/support/sessions` for authenticated support sessions with optional order context.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp`

- [x] Implement `POST /api/assistant/support/messages` for order lookup, return eligibility, policy explanation, refund estimate, exchange recommendation, support ticket escalation, and return preparation.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp`

- [x] Route complex support messages through mandatory Codex MCP and expose only ecommerce-safe Core/Search backed tools.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp`

- [x] Require explicit confirmation before creating returns or support tickets through agent flows.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`
  - Validation: `pytest tests/api/test_returns_support_agent.py`

## Action Confirmation

- [x] Implement `POST /api/assistant/actions/confirm` for pending mutating actions, including add-to-cart and create-return-request, with confirmation tokens and expiration.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

- [x] Ensure checkout/payment/order placement are never exposed as Chat Service tools in v1.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

## Product Links in Chat Responses (Feature D)

Product cards in assistant responses must carry a navigable link to the product detail page. The backend stores product `slug` in the `suggestedProducts` metadata; this feature ensures `slug` and `sourceProductId` are included in the API response so the frontend can build the correct URL.

- [x] Ensure `suggestedProducts` in `ShoppingAgent` assistant reply include `slug` and `sourceProductId` fields.

  **File:** `services/chat_service/app/agents/shopping.py`

  The `compact_product()` helper already includes `slug` and `sourceProductId`. Verify both are present in the returned dict and that no downstream transformation strips them. In `answer_product_question()` and `recommend_with_cart_action()`, the product passed to `compact_product()` comes from Search Service, which includes `slug`. No code change should be required — this is a verification gate.

  Add a targeted assertion to the existing shopping agent test:
  ```python
  # In test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action
  for p in reply["suggestedProducts"]:
      assert p.get("slug"), "suggestedProducts must include slug for product page links"
      assert p.get("sourceProductId"), "suggestedProducts must include sourceProductId"
  ```

  **Validation:**
  ```bash
  pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action -v
  ```

---

## Persistent Chat History with MongoDB (Feature E)

Chat sessions and messages are currently persisted only to a local JSON file. The file is not shared across processes, is wiped on reset, and is inaccessible to the frontend on subsequent page loads. This feature migrates persistence to MongoDB Atlas when configured, adds an API to retrieve session message history, and stores product snapshots in message metadata so the full chat feed can be reconstructed from the database.

---

### E1 — Add MongoDB connection module to Chat Service

- [x] Create `services/chat_service/app/database.py` with a lazy pymongo connection wrapper.

**File to create:** `services/chat_service/app/database.py`

Chat Service currently has no MongoDB client. Add a lazy-connecting wrapper identical in interface to Core Service's `database.py`:

```python
"""MongoDB Atlas connection helpers for Chat Service."""

from __future__ import annotations

from typing import Any
from app.config import ChatServiceSettings, settings


class MongoChatConnection:
    """Lazy MongoDB Atlas connection for chatSessions and chatMessages."""

    def __init__(self, config: ChatServiceSettings) -> None:
        self.config = config
        self._client: Any | None = None
        self._database: Any | None = None

    @property
    def configured(self) -> bool:
        return bool(self.config.mongodb_uri.strip())

    def client(self) -> Any:
        if not self.configured:
            raise RuntimeError("MONGODB_URI is not configured")
        if self._client is None:
            try:
                import certifi
                from pymongo import MongoClient
            except ImportError as exc:
                raise RuntimeError("pymongo and certifi required for MongoDB Atlas") from exc
            self._client = MongoClient(
                self.config.mongodb_uri,
                serverSelectionTimeoutMS=3000,
                tlsCAFile=certifi.where(),
            )
        return self._client

    def database(self) -> Any:
        if self._database is None:
            self._database = self.client()[self.config.mongodb_db]
        return self._database

    def collection(self, name: str) -> Any:
        return self.database()[name]

    def health(self) -> dict[str, object]:
        if not self.configured:
            return {"provider": "file_backed", "ready": True}
        try:
            self.client().admin.command("ping")
        except Exception:
            return {"provider": "mongodb_atlas", "ready": False}
        return {"provider": "mongodb_atlas", "ready": True}


mongo = MongoChatConnection(settings)
```

Add `mongodb_uri` and `mongodb_db` fields to `ChatServiceSettings` if not already present, reading from `MONGODB_URI` and `MONGODB_DB` environment variables.

**Validation:**
```bash
PYTHONPATH=services/chat_service python3 -m py_compile services/chat_service/app/database.py
```

---

### E2 — Extend `ChatStore` to write sessions and messages to MongoDB

- [x] Dual-write `chatSessions` and `chatMessages` to MongoDB when configured; add Atlas indexes on startup; keep file-backed fallback.

**File:** `services/chat_service/app/store.py`

The `ChatStore` file-backed fallback must remain for local dev without Atlas. When `mongo.configured` is `True`, write operations must upsert into MongoDB in addition to (or instead of) the JSON file.

**Implementation approach: dual-write with MongoDB as the source of truth when configured.**

In `create_session()`:
```python
def create_session(self, session_type: str, user_id: str, context: Json) -> Json:
    session = { ... }  # as now
    if mongo.configured:
        mongo.collection("chatSessions").insert_one(dict(session))
    else:
        self.state["chatSessions"].append(session)
        self.save()
    return clone(session)
```

In `add_message()`:
```python
def add_message(self, session_id: str, role: str, content: str, metadata: Json) -> Json:
    message = { ... }  # as now
    if mongo.configured:
        mongo.collection("chatMessages").insert_one(dict(message))
        mongo.collection("chatSessions").update_one(
            {"_id": session_id},
            {"$set": {"updatedAt": message["createdAt"]}},
        )
    else:
        self.state["chatMessages"].append(message)
        for session in self.state["chatSessions"]:
            if session["_id"] == session_id:
                session["updatedAt"] = message["createdAt"]
        self.save()
    return clone(message)
```

In `find_session()`:
```python
def find_session(self, session_id: str, user_id: str, session_type: str | None = None) -> Json | None:
    if mongo.configured:
        query = {"_id": session_id, "userId": user_id}
        if session_type:
            query["type"] = session_type
        doc = mongo.collection("chatSessions").find_one(query)
        if doc:
            doc["_id"] = str(doc["_id"])
        return clone(doc) if doc else None
    # existing file-backed fallback...
```

In `create_action()` and `find_action()` and `complete_action()`:
- Actions are short-lived (TTL = `ASSISTANT_ACTION_TTL_SECONDS`); they may remain file-backed or be stored in a `pendingActions` MongoDB collection with a TTL index. File-backed is acceptable for actions in v1.

Add MongoDB indexes on startup (idempotent `create_index`):
```python
# In a startup function called from main.py lifespan or first-use
if mongo.configured:
    mongo.collection("chatSessions").create_index([("userId", 1), ("type", 1), ("updatedAt", -1)])
    mongo.collection("chatSessions").create_index([("_id", 1)], unique=True)
    mongo.collection("chatMessages").create_index([("sessionId", 1), ("createdAt", 1)])
```

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py -v
# Session and message writes must still succeed in both file-backed and Atlas modes.
```

---

### E3 — Store `suggestedProducts` and user message content in `chatMessages` metadata

- [x] Add `suggestedProducts` list to assistant message metadata in `recommend_with_cart_action()` and `answer_product_question()`.

**File:** `services/chat_service/app/agents/shopping.py`

Currently:
- User messages are stored with `{"context": request_context}` in metadata — no visible content.
- Assistant messages store `{"productId": ..., "llmMetadataStored": True}` or `{"pendingActionId": ...}`.
- Neither message includes the `suggestedProducts` list needed to reconstruct the chat feed from the database.

**Changes:**

In `answer()`, store the user's raw message text alongside the context:
```python
store.add_message(session_id, "user", message, {"context": request_context})
# becomes:
store.add_message(session_id, "user", message, {"context": request_context, "text": message})
# (content is already the first positional arg — "text" in metadata is redundant; verify "content" is stored)
```
The `message` string IS already stored as the `content` field of the message document. No change needed here.

In `recommend_with_cart_action()`, add `suggestedProducts` to the assistant message metadata:
```python
# Current call:
store.add_message(session_id, "assistant", reply, {"pendingActionId": action["_id"], "llmMetadataStored": True})

# Replace with:
store.add_message(
    session_id,
    "assistant",
    reply,
    {
        "pendingActionId": action["_id"],
        "llmMetadataStored": True,
        "suggestedProducts": [compact_product(item) for item in products],
    },
)
```

In `answer_product_question()`, add the product to metadata:
```python
# Current call:
store.add_message(session_id, "assistant", text, {"productId": product["_id"], "llmMetadataStored": True})

# Replace with:
store.add_message(
    session_id,
    "assistant",
    text,
    {
        "productId": product["_id"],
        "llmMetadataStored": True,
        "suggestedProducts": [compact_product(product)],
    },
)
```

**Validation:** After a shopping assistant exchange, inspect a raw message document from the store:
```bash
PYTHONPATH=services/chat_service python3 - <<'PY'
from app.store import store
msgs = [m for m in store.state.get("chatMessages", []) if m["role"] == "assistant"]
print(msgs[-1] if msgs else "no messages")
PY
```
Confirm `suggestedProducts` is present in the `metadata` field of assistant messages.

---

### E4 — Add `GET /api/assistant/shopping/sessions` endpoint to find an active session

- [x] Add `GET /api/assistant/shopping/sessions` and `find_latest_session()` to allow the frontend to resume an existing session without client-side ID storage.

**File:** `services/chat_service/app/api/routes.py`

This endpoint lets the frontend re-attach to an existing active shopping session on page load, without needing to store the session ID client-side across navigations.

```python
@router.get("/assistant/shopping/sessions")
def list_shopping_sessions(request: Request) -> dict[str, object]:
    """Return the most recent active shopping session for the current user."""

    context = require_user_context(request)
    session = store.find_latest_session(context.user["_id"], "shopping")
    return ok({"session": session})
```

Add `find_latest_session()` to `ChatStore`:
```python
def find_latest_session(self, user_id: str, session_type: str) -> Json | None:
    """Return the most recent active session for the user."""

    if mongo.configured:
        doc = mongo.collection("chatSessions").find_one(
            {"userId": user_id, "type": session_type, "status": "active"},
            sort=[("updatedAt", -1)],
        )
        if doc:
            doc["_id"] = str(doc["_id"])
        return clone(doc) if doc else None
    # file-backed fallback:
    matching = [
        item for item in reversed(self.state["chatSessions"])
        if item["userId"] == user_id and item["type"] == session_type and item.get("status") == "active"
    ]
    return clone(matching[0]) if matching else None
```

**Validation:**
```bash
# After creating a session:
curl -s -X POST http://localhost:4002/api/assistant/shopping/sessions \
  -H "cookie: core_session=<token>" \
  -H "content-type: application/json" \
  -d '{"entryPoint":"catalogue"}'
# Then retrieve:
curl -s http://localhost:4002/api/assistant/shopping/sessions \
  -H "cookie: core_session=<token>" | python3 -m json.tool
```
Response must include `{"data": {"session": {... "_id": "<sessionId>" ...}}}`.

---

### E5 — Add `GET /api/assistant/shopping/sessions/{session_id}/messages` endpoint

- [x] Add `GET /api/assistant/shopping/sessions/{session_id}/messages` and `list_messages()` to return the full chronological chat feed for a session.

**File:** `services/chat_service/app/api/routes.py`

Returns all messages for an owned session in chronological order. This is the source of truth for the chat feed.

```python
from app.models import ..., SessionMessagesQuery  # add new query model

@router.get("/assistant/shopping/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    """Return messages for an owned shopping session."""

    context = require_user_context(request)
    session = store.find_session(session_id, context.user["_id"], "shopping")
    if not session:
        fail(404, "CHAT_SESSION_NOT_FOUND", "Shopping session was not found.")
    messages = store.list_messages(session_id, limit)
    return ok({"items": messages, "sessionId": session_id})
```

Add `list_messages()` to `ChatStore`:
```python
def list_messages(self, session_id: str, limit: int = 100) -> list[Json]:
    """Return messages for a session in chronological order."""

    if mongo.configured:
        cursor = (
            mongo.collection("chatMessages")
            .find({"sessionId": session_id}, {"_id": 0})
            .sort("createdAt", 1)
            .limit(limit)
        )
        return [clone(doc) for doc in cursor]
    # file-backed fallback:
    msgs = [
        clone(m)
        for m in self.state["chatMessages"]
        if m["sessionId"] == session_id
    ]
    return msgs[-limit:] if len(msgs) > limit else msgs
```

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py -v
```
Add a new test after the existing shopping assistant test:
```python
def test_shopping_assistant_messages_are_retrievable_from_history() -> None:
    client, _ = register_and_login(unique_email("chat-history"))
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/shopping/sessions", json={"entryPoint": "catalogue"}), 201)
    expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={"sessionId": session["_id"], "message": "Find a black shirt", "context": {}},
        )
    )
    history = expect_ok(chat.get(f"/api/assistant/shopping/sessions/{session['_id']}/messages"))
    assert history["items"], "session messages must be retrievable after a conversation turn"
    roles = [m["role"] for m in history["items"]]
    assert "user" in roles
    assert "assistant" in roles
```

---

---

## Feature F: Fully Agentic Shopping and Support Assistants

The current agents are deterministic workflow scripts. They call tools in a fixed code order using hardcoded string matching for filter extraction. They cannot handle novel requests, multi-step reasoning, outfit pairing, product comparison, or natural-language order lookup.

This feature replaces the hardcoded paths with an LLM-driven tool-use loop (ReAct pattern), exposes all tools as OpenAI function definitions, and adds the tools needed for the full capability set.

---

### F1 — Build a Tool Registry with OpenAI function definitions

- [x] Create `services/chat_service/app/tools/registry.py` defining all agent tools as OpenAI-compatible function schemas.

**File to create:** `services/chat_service/app/tools/registry.py`

Each tool must be described as an OpenAI function definition dict with `name`, `description`, and `parameters` (JSON Schema). The registry is the single source of truth for which tools the LLM can request.

Expose the following tools for the shopping agent:

| Function name | Backing call | Description |
|---|---|---|
| `search_products` | `SearchTools.search_products` | Search by query + structured filters |
| `get_product` | `SearchTools.get_product` | Fetch one product by ID or slug |
| `get_similar_products` | `SearchTools.get_similar_products` | Products visually/semantically similar to a reference |
| `find_matching_products` | `SearchTools.search_products` (with derived filters) | Find accessories/complements for a given product |
| `compare_products` | Multiple `SearchTools.get_product` calls | Fetch two or more products and return side-by-side attributes |
| `get_cart` | `CoreTools.get_cart` | Return current cart contents |
| `add_to_cart` | `CoreTools.add_to_cart` | Propose adding a product (requires confirmation) |
| `remove_from_cart` | `CoreTools.remove_from_cart` | Propose removing a cart item (requires confirmation) |
| `get_user_preferences` | `CoreTools.get_user_preferences` | Retrieve saved size, brand, and style preferences |

Expose the following tools for the support agent:

| Function name | Backing call | Description |
|---|---|---|
| `list_orders` | `CoreTools.list_user_orders` | List the user's orders with status and item summaries |
| `get_order` | `CoreTools.get_order` | Fetch a full order by order number or ID |
| `check_return_eligibility` | `CoreTools.check_return_eligibility` | Check whether an order item is within the return window |
| `create_return_request` | `CoreTools.create_return_request` | Propose a return (requires confirmation) |
| `create_support_ticket` | `CoreTools.create_support_ticket` | Propose opening a support ticket (requires confirmation) |
| `get_return_policy` | `CoreTools.get_return_policy` | Return current demo return window and resolution options |

**Implementation:**

```python
SHOPPING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search for fashion products using a natural language query and optional structured filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural language search query"},
                    "gender": {"type": "string", "enum": ["Men", "Women", "Boys", "Girls", "Unisex"]},
                    "usage": {"type": "array", "items": {"type": "string"}, "description": "Usage categories e.g. Casual, Formal, Sports"},
                    "baseColour": {"type": "string"},
                    "masterCategory": {"type": "string"},
                    "articleType": {"type": "string"},
                    "priceMax": {"type": "number"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    # ... remaining tool definitions
]
```

**Validation:**
```bash
PYTHONPATH=services/chat_service python3 -m py_compile services/chat_service/app/tools/registry.py
```

---

### F2 — Implement the agentic tool-use loop in `ShoppingAgent`

- [x] Replace the two hardcoded methods in `ShoppingAgent` with a tool-routed assistant flow that uses the registry, conversation history, cart context, matching/comparison tools, and deterministic fallback when live LLM tool-calling is unavailable.

**File:** `services/chat_service/app/agents/shopping.py`

**Current flow (hardcoded):**
```
message → if productId → answer_product_question()
         else          → recommend_with_cart_action()
```

**Target flow (agentic):**
```
message + conversation history
    → LLM with function definitions (SHOPPING_TOOLS)
    → LLM responds with tool_calls []
    → execute each tool, collect results
    → send tool results back to LLM
    → repeat until LLM responds with content and no tool_calls
    → extract pendingAction from last tool call that is a mutation
    → return message + suggestedProducts + pendingAction
```

**Key implementation details:**

1. Build conversation history from the last N messages in the session (default: last 12 messages) to give the LLM context of what was discussed.
2. Add a system prompt describing the agent's persona, the store catalogue, confirmation requirements, and what constitutes a mutating action.
3. The loop must have a max iteration cap (e.g. 6 tool-use rounds) to prevent runaway loops.
4. When the LLM requests `add_to_cart`, do NOT call `CoreTools.add_to_cart` directly — instead create a pending action and stop the loop, returning the `pendingAction` in the response.
5. Maintain the deterministic fallback: if `LLM_API_KEY` is not configured, fall back to the existing hardcoded path.

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_answers_product_questions_using_product_facts -v
pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action -v
```
Both existing tests must still pass. Add new tests for multi-tool scenarios (see F7 and F8).

---

### F3 — Add outfit pairing / matching product tool (`find_matching_products`)

- [x] Implement `find_matching_products` tool that takes a reference product and a target article type, derives colour and usage filters from the reference, and calls `search_products` with those derived filters.

**File:** `services/chat_service/app/tools/search.py`

When a user says "find shoes to match this shirt" or "what pants go with this jacket?", the agent should:
1. Fetch the reference product (shirt/jacket) via `get_product`
2. Extract `baseColour`, `usage`, and `gender` from it
3. Search for the target article type with compatible colour/usage filters

```python
def find_matching_products(
    self,
    cookie_header: str,
    reference_product_id: str,
    target_article_type: str,
    limit: int = 5
) -> list[Json]:
    """Search for products that complement a reference item."""

    reference = self.get_product(cookie_header, reference_product_id)
    base_colour = reference.get("baseColour", "")
    usage = reference.get("usage", "")
    gender = reference.get("gender", "")

    # Derive a complementary colour query
    complement_query = f"{base_colour} {target_article_type} {usage}".strip()
    filters: Json = {"articleType": target_article_type}
    if gender:
        filters["gender"] = gender
    if usage:
        filters["usage"] = [usage]

    return self.search_products(cookie_header, complement_query, filters=filters, limit=limit)
```

Register this as a function in the tool registry (F1).

**Validation:**
```bash
# Manual test: get a shirt's product ID, then call the tool with target "Shoes"
# Confirm returned products are shoes in the same gender and usage category
pytest tests/api/test_ai_agents_mcp.py -v -k "matching"
```

---

### F4 — Add product comparison tool (`compare_products`)

- [x] Implement `compare_products` tool that fetches two or more products by ID and returns a structured side-by-side comparison dict.

**File:** `services/chat_service/app/tools/search.py`

When a user says "compare product A and product B" or "which is better between these two?", the agent should:
1. Fetch both products via `get_product`
2. Return a structured comparison with key attributes side by side
3. Pass the comparison to the LLM to generate a natural language summary

```python
def compare_products(
    self,
    cookie_header: str,
    product_ids: list[str],
) -> Json:
    """Fetch multiple products and return a structured comparison."""

    products = [self.get_product(cookie_header, pid) for pid in product_ids]
    fields = ["title", "price", "baseColour", "articleType", "usage", "gender", "ratingAverage", "ratingCount", "tags"]
    comparison = {
        "products": [compact_product(p) for p in products],
        "attributes": {
            field: [p.get(field) for p in products]
            for field in fields
        }
    }
    return comparison
```

The LLM receives this dict as the tool result and generates a natural language comparison (e.g., "Product A is ₹200 cheaper but has a lower rating...").

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py -v -k "compare"
```

---

### F5 — Add occasion/season recommendation system prompt and filter vocabulary

- [x] Add an occasion and season vocabulary to the shopping agent system prompt, and expose `usage`, `season`, and `masterCategory` as first-class filters in the tool registry.

**File:** `services/chat_service/app/agents/shopping.py`

The LLM currently has no guidance on what filters exist in the catalogue. The system prompt should include:

```
Available catalogue filters:
- gender: Men, Women, Boys, Girls, Unisex
- usage: Casual, Formal, Sports, Ethnic, Party, Travel, Smart Casual
- season: Summer, Winter, Fall, Spring
- masterCategory: Apparel, Footwear, Accessories, Personal Care
- articleType: Shirts, Jeans, Dresses, Shoes, Sneakers, Kurtas, Sarees, Watches, ...
- baseColour: Black, White, Blue, Red, Green, ...
- priceMax: numeric INR value

When a user says "for a wedding" → usage: ["Ethnic", "Party"], masterCategory: "Apparel"
When a user says "for the gym" → usage: ["Sports"]
When a user says "summer outfit" → season: "Summer"
When a user says "office wear" → usage: ["Formal", "Smart Casual"]
```

This allows the LLM to correctly populate the `search_products` filter parameters from natural language intent without hardcoded string matching.

**Validation:**
- After this change, sending "find something for a beach vacation" should return products with `usage: ["Sports", "Casual"]` and/or `season: "Summer"` in the search call.
- Manually inspect the `agentToolAuditLogs` in Core to verify the filter payload.

---

### F6 — Implement agentic support agent with natural-language order lookup

- [x] Replace the `SupportAgent.answer()` hardcoded path with a tool-routed support flow that can look up orders, present them to the user, and initiate returns without requiring `orderId`/`orderItemId` to be pre-filled in the request context.

**File:** `services/chat_service/app/agents/support.py`

**Current limitation:** If `orderId` or `orderItemId` is not in the request context, the agent returns: `"Please choose the order and item you want help with."` — it cannot look them up.

**Target behavior:**

When the user says "I want to return the shoes I bought last week":
1. LLM decides to call `list_orders` tool
2. Agent calls `CoreTools.list_user_orders(cookie_header)`
3. LLM receives order list, identifies the most recent order with shoes
4. LLM calls `check_return_eligibility(orderId, orderItemId)`
5. If eligible, creates pending `create_return_request` action
6. Returns message + pendingAction

When the user says "I have an issue with order ORD-20250403-001":
1. LLM identifies the order number from the message
2. Calls `get_order` with the order number
3. Proceeds to return eligibility check

The support agent should use the same tool-use loop structure as the shopping agent (F2), with SUPPORT_TOOLS from the registry.

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp -v
```
Add new test: `test_support_agent_can_find_order_without_explicit_ids`.

---

### F7 — Add multi-turn conversation context (session history in agent loop)

- [x] Load the last N messages from the session store and include them as conversation history in each LLM call, enabling coherent multi-turn exchanges.

**File:** `services/chat_service/app/agents/shopping.py` and `support.py`

Currently, each `answer()` call starts a fresh LLM conversation with no memory of prior turns. The LLM cannot refer back to products it recommended two turns ago.

**Change:** Before each LLM call, load the last 10 messages from `store.list_messages(session_id)` and prepend them to the `messages` list:

```python
def build_history(self, session_id: str) -> list[Json]:
    """Build OpenAI message history from stored session messages."""
    messages = store.list_messages(session_id, limit=10)
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
        if msg["role"] in ("user", "assistant")
    ]
```

The LLM prompt then looks like:
```
[system prompt]
[user: "find black shoes"]          ← from history
[assistant: "I found ..."]          ← from history
[user: "what about something cheaper?"]  ← current message
```

This allows natural follow-up queries ("show me something similar but cheaper", "can you also add the first one to my cart?").

**Validation:**
- Send two messages in the same session. Second message should reference products from first response without re-specifying.
- Existing tests must still pass.

---

### F8 — Add `cart_aware` mode: skip products already in cart

- [x] When `cartAware: true` is set in the session context, call `get_cart` at the start of the loop and pass the cart contents to the LLM so it can avoid recommending items already added.

**File:** `services/chat_service/app/agents/shopping.py`

The `cartAware` flag already exists in the session request model and is forwarded in the request context. Currently it has no effect.

**Change:** At the start of `answer()`, when `request_context.get("cartAware")` is true:
1. Call `CoreTools.get_cart(cookie_header)`
2. Extract product IDs already in the cart
3. Include the cart contents in the LLM system prompt:
   ```
   Current cart: [product A (id: xxx), product B (id: yyy)]
   Do not recommend items already in the cart unless the user explicitly asks.
   ```
4. If the tool-use loop would add an already-carted item, note this in the response instead of creating a duplicate pending action.

**Validation:**
- Add a product to cart via `/api/core/cart/items`
- Send a shopping assistant message with `cartAware: true`
- Confirm the assistant does not recommend the already-carted product

---

### F9 — Add real MCP tool execution to `CodexMcpClient`

- [x] Replace the static `plan_support_return()` dict with live HTTP MCP tool execution when `CODEX_MCP_TRANSPORT=http`, while retaining readiness and static-plan fallback for local/stdout-only demo modes.

**File:** `services/chat_service/app/mcp/client.py`

Currently `plan_support_return()` returns a hardcoded Python dict and makes no network or subprocess call. This is a demo stub.

**Target:** When `codex_mcp_transport == "http"`, call the MCP server's tool-list and tool-execute endpoints to get a real plan. When `codex_mcp_transport == "stdio"`, spawn the subprocess and communicate over stdin/stdout.

**Minimum viable change for HTTP transport:**
```python
def plan_support_return(self, order_id: str, order_item_id: str) -> Json:
    if not self.config.codex_mcp_enabled or not self.http_ready():
        return self._static_plan(order_id, order_item_id)
    # Call MCP server tool endpoint
    payload = {
        "tool": "planReturnWorkflow",
        "input": {"orderId": order_id, "orderItemId": order_item_id}
    }
    try:
        response = request_json("POST", f"{self.config.codex_mcp_url}/tools/execute", payload=payload)
        return response
    except Exception:
        return self._static_plan(order_id, order_item_id)

def _static_plan(self, order_id: str, order_item_id: str) -> Json:
    """Existing hardcoded plan — used as fallback."""
    ...
```

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py::test_health_check_requires_mandatory_local_codex_mcp_readiness
pytest tests/api/test_ai_agents_mcp.py::test_complex_support_chat_routes_through_local_codex_mcp
```
Tests must pass in both stub and live modes.

---

## Feature G: Support UX Overhaul

The current `SupportClient` at `/support` is a minimal form with critical UX gaps:
- Silently auto-selects the first order and first item — user has no visibility into which order is selected
- Shows only the last assistant reply — no message history or feed
- No way for user to browse their orders and choose which one to raise support for
- Session is not persisted — refreshing loses the conversation
- No two-sided chat feed (user messages are not shown)

---

### G1 — Add order picker to `SupportClient` so users can choose which order to get help with

- [x] Render a list of the user's orders in `SupportClient`, let the user click one to set it as the support context, then show the order's items so the user can pick a specific item.

**File:** `apps/web/components/SupportClient.tsx`

**Current:** Auto-picks `orders[0].items[0]` with no UI.

**Target:**
1. Show all orders as a selectable list (reuse `.order-row` CSS)
2. On order selection, expand to show line items within that order
3. User can optionally pick a specific item, or let the agent decide
4. The selected `orderId` and `orderItemId` are passed in the message context
5. The selected order header stays visible at the top while chatting

```tsx
const [selectedOrderId, setSelectedOrderId] = useState("");
const [selectedItemId, setSelectedItemId] = useState("");
const selectedOrder = orders.find((o) => o._id === selectedOrderId);
```

**Validation:** User can see all orders, select one, see its items, and then ask the support agent about it.

---

### G2 — Convert `SupportClient` to a persistent two-sided chat feed

- [x] Refactor `SupportClient` to match the shopping assistant's persistent feed pattern: localStorage session, history loading, user/assistant bubbles, auto-scroll.

**File:** `apps/web/components/SupportClient.tsx`

Apply the same patterns implemented in `AssistantDrawer.tsx` (Feature E):
1. Store `supportSessionId` in `localStorage`
2. On load, call `GET /api/chat/assistant/support/sessions` to find an active session
3. Load message history from `GET /api/chat/assistant/support/sessions/{id}/messages`
4. Render user and assistant messages as `chat-bubble-user` / `chat-bubble-assistant` bubbles
5. Show the support agent's eligibility result and confirmation form inline in the feed

This requires adding:
- `GET /api/assistant/support/sessions` endpoint (analogous to E4 for shopping)
- `GET /api/assistant/support/sessions/{id}/messages` endpoint (analogous to E5)

**Validation:** Support chat persists across page refreshes. All prior messages appear on re-open.

---

### G3 — Show return confirmation form inline in the support chat feed

- [x] Move the return confirmation form (reason, condition, resolution) from a separate section into an inline card within the chat feed, appearing immediately after the eligibility message.

**File:** `apps/web/components/SupportClient.tsx`

**Current:** The confirmation form appears as a detached `<section class="panel">` below the reply. If the user scrolls, they lose context.

**Target:** The confirmation form card appears as a `FeedEntry` with `role: "action"` inside the chat feed, directly below the eligibility assistant bubble. When confirmed, the card is replaced by a success bubble showing the return number.

```tsx
interface FeedEntry {
  id: string;
  role: "user" | "assistant" | "action";
  text: string;
  pendingAction?: PendingAction;
  returnNumber?: string;
}
```

**Validation:** After the agent reports eligibility, the reason/condition/confirmation form appears inside the chat feed. Confirming shows the return number in the feed.

---

## Chat and Support Completion Gates (Feature F + G)

- [x] Shopping agent handles outfit pairing request via multi-tool call.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py -k "matching"`

- [x] Shopping agent correctly compares two products in a single response.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py -k "compare"`

- [x] Support agent can initiate a return from a natural language message with no pre-filled order IDs.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py -k "support_find_order"`

- [x] Multi-turn conversation coherence: follow-up references prior recommendations correctly.
  - Validation: manual session test with 3+ turns

- [x] Support UX shows all orders and lets user select one before chatting.
  - Validation: `npx playwright test tests/e2e --workers=1`

- [x] Support UX chat feed persists across page refreshes.
  - Validation: `npx playwright test tests/e2e --workers=1`

---

---

## Feature H: Paginated Conversation History in MongoDB

Feature E migrates a single active session to MongoDB and lets the frontend resume it. Feature H extends this with a **conversation list**: a paginated API returning all of the user's past sessions ordered by most-recent-first, a `summary` field on each session so the UX can display a preview without fetching all messages, and "load more" pagination so the frontend can request batches beyond the default 5.

This builds directly on top of E1 (MongoDB module) and E2 (ChatStore dual-write), which must be completed first.

---

### H1 — Store a `summary` field on each session, updated on every new message

- [x] When a session's first user message arrives, write a `summary` string to the session document so the conversation list can display a preview without fetching all messages.

**File:** `services/chat_service/app/store.py`

Each session document should gain a `summary` field containing the trimmed first user message (up to 80 characters). This is set on first write and never overwritten.

In `add_message()`, after writing the message, if `role == "user"` and the session has no `summary` yet, update the session summary:

```python
def add_message(self, session_id: str, role: str, content: str, metadata: Json) -> Json:
    message = { ... }  # existing creation logic

    # set summary on first user message
    if role == "user":
        summary_text = content.strip()[:80]
        if mongo.configured:
            mongo.collection("chatSessions").update_one(
                {"_id": session_id, "summary": {"$exists": False}},
                {"$set": {"summary": summary_text, "updatedAt": message["createdAt"]}},
            )
        else:
            for session in self.state["chatSessions"]:
                if session["_id"] == session_id and "summary" not in session:
                    session["summary"] = summary_text
                    session["updatedAt"] = message["createdAt"]
    # existing write logic continues ...
```

Also add `summary` and `messageCount` to the session document created in `create_session()` as empty defaults:

```python
session = {
    "_id": new_id(),
    "type": session_type,
    "userId": user_id,
    "context": clone(context),
    "status": "active",
    "summary": "",          # ← filled on first user message
    "messageCount": 0,      # ← incremented on each add_message
    "createdAt": now_iso(),
    "updatedAt": now_iso(),
}
```

Increment `messageCount` inside `add_message()` via `$inc` in MongoDB or in-memory for file-backed mode:

```python
if mongo.configured:
    mongo.collection("chatSessions").update_one(
        {"_id": session_id},
        {"$inc": {"messageCount": 1}, "$set": {"updatedAt": message["createdAt"]}},
    )
else:
    for session in self.state["chatSessions"]:
        if session["_id"] == session_id:
            session["messageCount"] = session.get("messageCount", 0) + 1
            session["updatedAt"] = message["createdAt"]
```

**Validation:**
```bash
# Start a conversation, then inspect the session document:
PYTHONPATH=services/chat_service python3 - <<'PY'
from app.store import store
sessions = store.state.get("chatSessions", [])
print(sessions[-1] if sessions else "no sessions")
PY
# Confirm "summary" is the first user message and "messageCount" increments.
```

---

### H2 — Add `list_sessions()` to `ChatStore` with cursor-based pagination

- [x] Add `list_sessions(user_id, session_type, limit, before_id)` to `ChatStore` to return sessions in reverse-chronological order with cursor pagination.

**File:** `services/chat_service/app/store.py`

The method returns the `limit` most recent sessions updated before `before_id` (if provided), enabling "load more" without offset-based pagination that drifts as new sessions are created.

```python
def list_sessions(
    self,
    user_id: str,
    session_type: str,
    limit: int = 5,
    before_id: str | None = None,
) -> tuple[list[Json], bool]:
    """Return sessions in reverse-chronological order.

    Returns (sessions, has_more) where has_more signals whether
    another page exists beyond the returned batch.
    """
    if mongo.configured:
        query: Json = {"userId": user_id, "type": session_type}
        if before_id:
            # find the updatedAt of the cursor session, then fetch older ones
            cursor_doc = mongo.collection("chatSessions").find_one(
                {"_id": before_id}, {"updatedAt": 1}
            )
            if cursor_doc:
                query["updatedAt"] = {"$lt": cursor_doc["updatedAt"]}
        docs = list(
            mongo.collection("chatSessions")
            .find(query)
            .sort("updatedAt", -1)
            .limit(limit + 1)   # fetch one extra to detect has_more
        )
        has_more = len(docs) > limit
        results = docs[:limit]
        for doc in results:
            doc["_id"] = str(doc["_id"])
        return [clone(d) for d in results], has_more

    # file-backed fallback
    all_sessions = [
        item for item in self.state["chatSessions"]
        if item["userId"] == user_id and item["type"] == session_type
    ]
    # sort newest-first
    all_sessions.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    if before_id:
        try:
            cursor_pos = next(i for i, s in enumerate(all_sessions) if s["_id"] == before_id)
            all_sessions = all_sessions[cursor_pos + 1:]
        except StopIteration:
            pass
    has_more = len(all_sessions) > limit
    return [clone(s) for s in all_sessions[:limit]], has_more
```

**Validation:**
```bash
PYTHONPATH=services/chat_service python3 - <<'PY'
from app.store import store
sessions, has_more = store.list_sessions("<userId>", "shopping", limit=5)
print(f"{len(sessions)} sessions, has_more={has_more}")
PY
```

---

### H3 — Add `GET /api/assistant/shopping/sessions/history` paginated list endpoint

- [x] Add `GET /api/assistant/shopping/sessions/history` returning a paginated session list with `summary`, `messageCount`, `updatedAt`, and a `hasMore` cursor.

**File:** `services/chat_service/app/api/routes.py`

This endpoint is distinct from the existing E4 `GET /api/assistant/shopping/sessions` (which returns the single latest session for auto-resume). The history endpoint returns a list for the conversation switcher UI.

```python
from fastapi import Query

@router.get("/assistant/shopping/sessions/history")
def shopping_session_history(
    request: Request,
    limit: int = Query(default=5, ge=1, le=50),
    before: str | None = Query(default=None),
) -> dict[str, object]:
    """Return paginated conversation history for the current user."""

    context = require_user_context(request)
    sessions, has_more = store.list_sessions(
        context.user["_id"], "shopping", limit=limit, before_id=before
    )
    return ok({
        "items": sessions,
        "hasMore": has_more,
        "nextCursor": sessions[-1]["_id"] if has_more and sessions else None,
    })
```

Each item in `items` is a session document including `_id`, `summary`, `messageCount`, `status`, `createdAt`, `updatedAt`. Messages are not included — they are fetched separately when the user selects a session (E5).

**Validation:**
```bash
# Create 6+ sessions for the same user, then:
curl -s "http://localhost:4002/api/assistant/shopping/sessions/history?limit=5" \
  -H "cookie: core_session=<token>" | python3 -m json.tool
# Confirm: 5 sessions returned, hasMore=true, nextCursor set.
# Load second page:
curl -s "http://localhost:4002/api/assistant/shopping/sessions/history?limit=5&before=<nextCursor>" \
  -H "cookie: core_session=<token>" | python3 -m json.tool
# Confirm: remaining sessions, hasMore=false.
```

Add pytest test:
```python
def test_session_history_returns_paginated_sessions() -> None:
    client, _ = register_and_login(unique_email("session-history"))
    chat = chat_client(client)
    # create 6 sessions
    for _ in range(6):
        expect_ok(
            chat.post("/api/assistant/shopping/sessions", json={"entryPoint": "catalogue"}), 201
        )
    page1 = expect_ok(chat.get("/api/assistant/shopping/sessions/history?limit=5"))
    assert len(page1["items"]) == 5
    assert page1["hasMore"] is True
    assert page1["nextCursor"]

    page2 = expect_ok(chat.get(f'/api/assistant/shopping/sessions/history?limit=5&before={page1["nextCursor"]}'))
    assert len(page2["items"]) >= 1
    assert page2["hasMore"] is False

    # no duplicate sessions across pages
    ids_p1 = {s["_id"] for s in page1["items"]}
    ids_p2 = {s["_id"] for s in page2["items"]}
    assert ids_p1.isdisjoint(ids_p2)
```

**Validation:**
```bash
pytest tests/api/test_ai_agents_mcp.py::test_session_history_returns_paginated_sessions -v
```

---

### H4 — Add `GET /api/assistant/support/sessions/history` for support session list

- [x] Mirror H3 for the support agent: add `GET /api/assistant/support/sessions/history` using the same `list_sessions(session_type="returns_support")` store method.

**File:** `services/chat_service/app/api/routes.py`

```python
@router.get("/assistant/support/sessions/history")
def support_session_history(
    request: Request,
    limit: int = Query(default=5, ge=1, le=50),
    before: str | None = Query(default=None),
) -> dict[str, object]:
    """Return paginated support conversation history."""

    context = require_user_context(request)
    sessions, has_more = store.list_sessions(
        context.user["_id"], "returns_support", limit=limit, before_id=before
    )
    return ok({
        "items": sessions,
        "hasMore": has_more,
        "nextCursor": sessions[-1]["_id"] if has_more and sessions else None,
    })
```

**Validation:**
```bash
curl -s "http://localhost:4002/api/assistant/support/sessions/history?limit=5" \
  -H "cookie: core_session=<token>" | python3 -m json.tool
```

---

### H5 — Ensure MongoDB Atlas indexes support efficient session list queries

- [x] Add compound indexes on `(userId, type, updatedAt)` and a TTL index on `pendingActions` to the MongoDB startup routine.

**File:** `services/chat_service/app/store.py` (or `main.py` lifespan startup)

The E2 task creates basic indexes. Feature H requires efficient reverse-chronological list queries. Add or confirm these indexes are created on startup:

```python
if mongo.configured:
    # efficient session list by user + type, newest first
    mongo.collection("chatSessions").create_index(
        [("userId", 1), ("type", 1), ("updatedAt", -1)],
        name="sessions_user_type_updated"
    )
    # efficient message fetch by session in order
    mongo.collection("chatMessages").create_index(
        [("sessionId", 1), ("createdAt", 1)],
        name="messages_session_created"
    )
    # auto-expire pending actions after 24 hours
    mongo.collection("pendingActions").create_index(
        "expiresAt",
        expireAfterSeconds=0,
        name="actions_ttl"
    )
```

The TTL index on `pendingActions.expiresAt` removes expired action documents automatically, preventing unbounded growth in the collection.

**Validation:**
```bash
# After startup with MONGODB_URI configured, connect with mongosh and verify:
# db.chatSessions.getIndexes()
# db.chatMessages.getIndexes()
# db.pendingActions.getIndexes()
# Confirm all three indexes are present.
```

---

## Feature H: Completion Gates

- [x] Session history endpoint returns paginated sessions with `summary`, `messageCount`, `hasMore`, and cursor.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_session_history_returns_paginated_sessions`

- [x] `summary` field is populated on the first user message and stable on subsequent turns.
  - Validation: inspect session document after first message

- [x] `messageCount` increments correctly for both MongoDB and file-backed modes.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

- [x] "Load more" cursor returns next 5 sessions with no duplicates across pages.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_session_history_returns_paginated_sessions`

---

## Chat Service Completion Gates

- [x] Chat-only API gate passes.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py`

- [x] Cross-service agent gate passes with Core and Search running.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py tests/api/test_returns_support_agent.py tests/api/test_cart_checkout_orders.py`

- [x] Full API suite passes with all services running.
  - Validation: `pytest tests/api`

- [x] `suggestedProducts` slug verification passes.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action`

- [x] Chat message history API gate passes.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_shopping_assistant_messages_are_retrievable_from_history`

- [x] Browser assistant/support flows pass after frontend is implemented.
  - Validation: `npx playwright test tests/e2e --workers=1`
