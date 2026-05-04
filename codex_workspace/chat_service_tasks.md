# Chat Service — Codex MCP Integration Tasks

Source reference: `stylesense_spec.md` sections 7.5, 7.6, and the AI & Embedding Layer section.  
Target files: `services/chat_service/app/`

---

## Context: What Is Already Built

| Layer | Status |
|---|---|
| `config.py` — `CODEX_MCP_COMMAND`, `CODEX_MCP_ARGS`, `CODEX_MCP_TRANSPORT`, `CODEX_MCP_TIMEOUT_MS` | Done |
| `mcp/client.py` — `CodexMcpClient.readiness()` (checks `which codex` for stdio) | Done |
| `mcp/client.py` — `plan_support_return()` (returns a static stub plan, no real I/O) | Stub only |
| `agents/support.py` — eligibility check, LLM text, pending action — calls `mcp_client.plan_support_return()` | Done for non-MCP path |
| `agents/shopping.py` — keyword filtering, LLM text, pending cart action | Done for non-MCP path |
| `store.py` — file-backed JSON store for sessions/messages/actions | Done (for file backend) |
| Routes — session create, message send, action confirm endpoints | Done |

**Not yet built:** real subprocess lifecycle, JSON-RPC stdio transport, `codex` / `codex-reply` tool calls, MongoDB-backed thread persistence, SSE streaming, action-tag detection.

---

## Task 1 — Async subprocess manager for the Codex MCP process

**File:** `services/chat_service/app/mcp/process.py` (new)

**What to build:**  
A module that spawns `codex mcp-server` (or the configured command/args) as a single shared async subprocess when the chat service starts, keeps it alive, and restarts it automatically if it crashes.

**Detailed requirements:**

- Spawn using `asyncio.create_subprocess_exec` with `stdin=PIPE`, `stdout=PIPE`, `stderr=PIPE`.
- Pass `**os.environ` to the subprocess so `OPENAI_API_KEY` (or `LLM_API_KEY`) reaches Codex automatically.
- Parse `CODEX_MCP_ARGS` from the config as a comma-separated string (e.g. `mcp,serve`) into a list of arguments before passing to `create_subprocess_exec`.
- Expose a module-level singleton `codex_process` with:
  - `async start()` — spawns the process, waits for the MCP initialization JSON line on stdout, logs it, and marks the manager ready.
  - `async stop()` — terminates the process gracefully; used on app shutdown.
  - `is_alive() → bool` — returns `True` when the subprocess is running.
  - `auto_restart_on_next_request() → None` — clears the dead process handle so the next call to `send()` (Task 2) spawns a fresh process. On a current-request crash, the current request must return a 502.
- Startup/restart must write a structured log line: `{"event": "codex_mcp_started", "pid": ..., "command": ..., "args": ...}`.
- Use the FastAPI lifespan hook in `main.py` to call `await codex_process.start()` on startup and `await codex_process.stop()` on shutdown.
- The subprocess must only be started when `CODEX_MCP_TRANSPORT=stdio` and `CODEX_MCP_ENABLED=true`.

**Config reference:**
```
CODEX_MCP_COMMAND=codex
CODEX_MCP_ARGS=mcp,serve
CODEX_MCP_TIMEOUT_MS=120000
```

---

## Task 2 — JSON-RPC stdio transport for MCP tool calls

**File:** `services/chat_service/app/mcp/transport.py` (new)

**What to build:**  
A thin async JSON-RPC client that sends MCP protocol messages to the Codex subprocess over stdio and reads the response.

**Detailed requirements:**

- Implement `async send(method: str, params: dict) -> dict` which:
  - Serialises `{"jsonrpc": "2.0", "id": <uuid>, "method": method, "params": params}` as a newline-terminated UTF-8 JSON line to the subprocess stdin.
  - Reads newline-delimited JSON from stdout, matching the response by `id`.
  - Raises `CodexMcpError` (define in this module) on timeout, process death, or JSON-RPC `error` response.
- Use `asyncio.wait_for` bounded by `CODEX_MCP_TIMEOUT_MS` in seconds.
- Do not read stderr in the hot path; drain stderr in a background task and log each line at DEBUG level.
- Acquire a per-process `asyncio.Lock` before writing so concurrent requests do not interleave stdio frames.
- If the process is dead when `send()` is called, trigger `codex_process.auto_restart_on_next_request()` and raise `CodexMcpError("codex_mcp_subprocess_unavailable")` so the caller can surface a 502.

---

## Task 3 — `codex` and `codex-reply` tool calls in `CodexMcpClient`

**File:** `services/chat_service/app/mcp/client.py`

**What to build:**  
Replace the stub `plan_support_return()` method with real MCP tool-call methods for starting and continuing Codex threads.

**Detailed requirements:**

Add two async methods to `CodexMcpClient`:

```python
async def call_codex(
    self,
    user_message: str,
    system_prompt: str,
) -> tuple[str, str]:
    """Start a new Codex thread. Returns (reply_text, thread_id)."""

async def call_codex_reply(
    self,
    thread_id: str,
    user_message: str,
    system_prompt: str,
) -> str:
    """Continue an existing Codex thread. Returns reply_text."""
```

- `call_codex` sends a `tools/call` JSON-RPC message with:
  ```json
  {
    "name": "codex",
    "arguments": {
      "prompt": "<user_message>",
      "approval_mode": "never",
      "config": {
        "model": "<LLM_MODEL from settings>",
        "instructions": "<system_prompt>"
      }
    }
  }
  ```
  Extract `threadId` from `result["structuredContent"]["threadId"]`.

- `call_codex_reply` sends a `tools/call` message with:
  ```json
  {
    "name": "codex-reply",
    "arguments": {
      "threadId": "<thread_id>",
      "prompt": "<user_message>",
      "config": { "instructions": "<system_prompt>" }
    }
  }
  ```
  Extract the reply text from `result["content"][0]["text"]` (or the equivalent MCP response shape).

- Both methods delegate to `transport.send()` from Task 2.
- Keep `plan_support_return()` as a deprecated internal helper used only as a fallback if MCP is unavailable, but stop calling it in the agent path once Task 4 is done.
- Update `readiness()` so the `ready` flag is `True` only when `codex_process.is_alive()` returns `True` (not just `which codex`).

---

## Task 4 — MongoDB-backed Codex thread persistence

**File:** `services/chat_service/app/mcp/sessions.py` (new)

**What to build:**  
A MongoDB repository for `codex_sessions` and `codex_messages` collections that stores thread IDs per user and logs all messages.

**Detailed requirements:**

- Connect to MongoDB using `MONGODB_URI` and `MONGODB_DB` from config (reuse the `pymongo` client already used by other services or add it to chat service config).
- `codex_sessions` schema (one document per user per session type, upserted):
  ```json
  {
    "user_id": "string",
    "session_type": "shopping" | "support",
    "thread_id": "string",
    "created_at": "ISODate",
    "updated_at": "ISODate"
  }
  ```
  - Create unique compound index on `user_id` + `session_type`.
  - Create TTL index on `updated_at` with `expireAfterSeconds: 2592000` (30 days).

- `codex_messages` schema (one document per message):
  ```json
  {
    "user_id": "string",
    "thread_id": "string",
    "role": "user" | "assistant",
    "content": "string",
    "timestamp": "ISODate"
  }
  ```
  - Create index on `user_id` + `timestamp` (descending).
  - Create TTL index on `timestamp` with `expireAfterSeconds: 7776000` (90 days).

- Expose:
  - `upsert_thread(user_id, session_type, thread_id)` — upsert `codex_sessions`.
  - `get_thread_id(user_id, session_type) -> str | None` — look up existing thread.
  - `log_messages(user_id, thread_id, user_message, assistant_reply)` — insert two documents into `codex_messages`.

- If `MONGODB_URI` is not configured, fall back to the existing file-backed `ChatStore` for thread ID storage (store thread IDs in session context) so the service still works locally without Atlas.

---

## Task 5 — Wire real MCP calls into the Shopping Agent

**File:** `services/chat_service/app/agents/shopping.py`

**What to build:**  
Replace the LLM `chat_completions` path in `recommend_with_cart_action()` and `answer_product_question()` with real Codex MCP calls for multi-turn conversations.

**Detailed requirements:**

- Build the shopping system prompt dynamically per request:
  ```
  You are a StyleSense shopping assistant. You have access to the following product data.
  AVAILABLE CATEGORIES: Apparel, Footwear, Accessories, Bags, Beauty
  CURRENT PRODUCTS: <compact product list from search results>
  CART: <cart item summary if cartAware=true>
  USER PREFERENCES: <user preferences from Core Service>
  Rules:
  - Recommend no more than 5 products at once.
  - Reference specific products by name.
  - Do NOT invent prices or stock levels.
  - For cart mutations, summarise the item and ask for confirmation.
  ```
- On first message for a user session (`get_thread_id` returns `None`): call `mcp_client.call_codex(user_message, system_prompt)`, save the returned `thread_id` via `sessions.upsert_thread()`.
- On subsequent messages: call `mcp_client.call_codex_reply(thread_id, user_message, system_prompt)`.
- After a successful reply: call `sessions.log_messages(user_id, thread_id, user_message, reply)`.
- Keep the existing `add_to_cart` pending-action creation path — it should trigger when the Codex reply contains an add-to-cart intent. For now a simple keyword check (`"add to cart"` / `"would you like me to add"`) is sufficient; a regex or structured action tag is better.
- If `call_codex` / `call_codex_reply` raises `CodexMcpError`, fall back to the existing `self.llm_text()` path and log a warning with `usedMcp: False` in the stored message metadata.
- Set `usedMcp: True` in the response and stored message metadata when the MCP path succeeds.

---

## Task 6 — Wire real MCP calls into the Support Agent

**File:** `services/chat_service/app/agents/support.py`

**What to build:**  
Replace the current LLM + stub MCP plan path with real Codex MCP calls and structured action-tag detection.

**Detailed requirements:**

- Build the support system prompt dynamically, including the authenticated user's orders:
  ```python
  def build_support_prompt(user, orders, active_ticket) -> str:
      order_detail = format_orders_for_prompt(orders)   # human-readable order summary
      return f"""
  You are a support agent. CUSTOMER: {user['name']} ({user['email']})
  ORDER HISTORY (most recent first):
  {order_detail}
  ACTIVE TICKET: {active_ticket or 'None'}
  CAPABILITIES:
  1. Lookup and explain order status.
  2. Initiate a return: respond with [ACTION: RETURN_INITIATED order_id=<id>]
  3. Escalate: respond with [ACTION: ESCALATE reason=<reason>]
  4. Resolve: respond with [ACTION: RESOLVED ticket_id=<id>]
  RESOLUTION GUIDE:
  - Late < 7 days: apologise and share tracking.
  - Late > 7 days or wrong item or damaged: [ACTION: RETURN_INITIATED].
  - Unknown: ask one clarifying question.
  Do NOT invent tracking numbers. Be brief and empathetic.
  """
  ```
- Session type key: `"support"` (separate from `"shopping"` in `codex_sessions`).
- Follow the same new-thread / continue-thread pattern as Task 5.
- After receiving the Codex reply, run action-tag detection:
  ```python
  ACTION_PATTERN = re.compile(r'\[ACTION:\s*(\w+)(.*?)\]', re.DOTALL)
  ```
  - `RETURN_INITIATED` → set `pendingAction.type = "create_return_request"` and initiate the existing `store.create_action()` flow so the user still confirms before Core Service is called.
  - `ESCALATE` → call `core_tools` to update the support ticket status to `escalated` and include `escalation_reason` in the metadata.
  - `RESOLVED` → call `core_tools` to update the support ticket status to `resolved`.
  - Strip action tags from the reply before returning it to the user.
- Audit every action-tag execution via `audit_tool_call()`.
- If `CodexMcpError`, fall back to current LLM path and log `usedMcp: False`.

---

## Task 7 — SSE streaming endpoint for chat responses

**File:** `services/chat_service/app/api/routes.py`

**What to build:**  
Add a streaming variant of the shopping and support message endpoints using Server-Sent Events.

**Detailed requirements:**

- Add `GET /api/assistant/shopping/stream` and `GET /api/assistant/support/stream` (or use the same POST paths with `Accept: text/event-stream` detection).
- Use FastAPI `StreamingResponse` with `media_type="text/event-stream"`.
- Stream partial Codex output as SSE events: `data: <chunk>\n\n`.
- Send a final `data: [DONE]\n\n` event when streaming completes.
- Support `EventSource` clients from the frontend.
- If Codex MCP does not support incremental streaming over stdio (current `codex mcp-server` returns complete replies), emit the full reply as a single SSE event — do not block the response until the complete reply arrives, so the frontend timeout does not fire.
- Log `usedMcp`, `provider`, `model`, and token usage (if available from Codex reply metadata) on each streaming response.

---

## Task 8 — MCP readiness as a hard health-check gate

**File:** `services/chat_service/app/api/routes.py` and `services/chat_service/app/mcp/client.py`

**What to build:**  
Make the `/api/health` endpoint report `ready: false` when the Codex subprocess is dead or was never started, and make the demo treat that state as a blocking error.

**Detailed requirements:**

- Update `CodexMcpClient.readiness()` to use `codex_process.is_alive()` (from Task 1) for the `ready` field instead of `shutil.which()`. A binary being on `PATH` is not sufficient — the process must be running.
- `ready: true` requires: `CODEX_MCP_ENABLED=true` AND subprocess is alive AND initialization JSON was received.
- The health route already returns `"ready": mcp["ready"]`. No change needed there.
- Add a `POST /api/test/mcp-restart` route (admin token protected, only in `app_env != "production"`) that calls `codex_process.stop()` then `codex_process.start()`. This is used in tests and demo reset flows.
- The test `test_health_check_requires_mandatory_local_codex_mcp_readiness` in `tests/api/test_ai_agents_mcp.py` must pass with the live subprocess after Task 1.

---

## Task 9 — Integration tests for the MCP path

**File:** `tests/api/test_ai_agents_mcp.py`

**What to build:**  
Add tests that cover the real MCP call path (with a local Codex process running) and the fallback path (with MCP unavailable).

**Detailed requirements:**

- `test_health_check_requires_mandatory_local_codex_mcp_readiness` — already exists; verify it passes end-to-end with the subprocess running.
- `test_shopping_assistant_uses_mcp_for_new_thread` — verify that a first shopping message:
  - returns `usedMcp: true`.
  - creates a `codex_sessions` document in MongoDB.
  - logs two `codex_messages` documents.
- `test_shopping_assistant_continues_existing_thread` — verify that a second message on the same session reuses the stored `thread_id`.
- `test_support_agent_action_tag_triggers_return_pending_action` — send a multi-step support message designed to produce `[ACTION: RETURN_INITIATED ...]` and verify `pendingAction.type == "create_return_request"` is returned.
- `test_mcp_unavailable_falls_back_to_llm` — stop the Codex subprocess via `/api/test/mcp-restart` (or a mock), verify the reply is non-empty, `usedMcp: false`, and the health endpoint reports `ready: false`.
- `test_complex_support_chat_routes_through_local_codex_mcp` — already exists; verify it passes with the real subprocess and the action-tag path wired.

---

## Task 10 — Update `.env.example` and README for MCP subprocess usage

**Files:** `.env.example`, `README.md`, `services/chat_service/README.md`

**What to build:**  
Document the exact local Codex MCP setup steps so any developer can reproduce the environment from scratch.

**Detailed requirements:**

- Add a "Codex MCP Setup" section to the root `README.md`:
  - Install: `npm install -g @openai/codex` (or confirm `npx` path).
  - Smoke test: `codex mcp serve` — should print an MCP initialization JSON object and wait.
  - Set `OPENAI_API_KEY` (or `LLM_API_KEY`) in `.env` — required for Codex to reach the LLM.
  - The chat service will auto-spawn the Codex process on startup; no separate terminal needed.
- Add a "Verifying MCP readiness" subsection:
  ```bash
  curl http://127.0.0.1:4002/api/health | jq '.data.mcp'
  # expected: { "enabled": true, "ready": true, "transport": "stdio", ... }
  ```
- Update `.env.example` with the correct default args for the installed `codex` CLI:
  ```env
  CODEX_MCP_ENABLED=true
  CODEX_MCP_TRANSPORT=stdio
  CODEX_MCP_COMMAND=codex
  CODEX_MCP_ARGS=mcp,serve
  CODEX_MCP_TIMEOUT_MS=120000
  ```
- Note the `approval_mode: never` safety requirement: Codex MCP must not be configured with shell or filesystem tools for this demo. Document how to verify this in the README.

---

## Dependency Order

```
Task 1 (subprocess manager)
  └── Task 2 (JSON-RPC transport)
        ├── Task 3 (call_codex / call_codex_reply in client)
        │     ├── Task 4 (MongoDB thread persistence)
        │     │     ├── Task 5 (Shopping Agent wiring)
        │     │     └── Task 6 (Support Agent wiring)
        │     │           └── Task 7 (SSE streaming)
        │     └── Task 8 (health-check gate)
        └── Task 9 (integration tests — after Tasks 1–8)
Task 10 (docs — can be done in parallel with any task)
```
