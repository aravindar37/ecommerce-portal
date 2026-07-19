# Chat Service

FastAPI service for StyleSense shopping and returns/support assistants. Chat Service owns authenticated chat sessions, assistant messages, pending human confirmations, Deep Agents-oriented orchestration, ecommerce-safe tool wrappers, token-aware context assembly, transient retry handling, memory/run records, LLM provider routing, local Codex MCP readiness metadata, and agent audit logging.

---

## Current Architecture

```text
Browser / Next.js (port 3000)
        │  cookie forwarding (core_session)
        ▼
  Chat Service (port 4002)
  ┌───────────────────────────────────────────────────────────┐
  │ FastAPI routes + Core session validation                  │
  │                                                           │
  │ AgentService                                             │
  │   ├─ DeepAgentsHarness                                   │
  │   │   ├─ token-budgeted context                          │
  │   │   ├─ retry policy / safe failure handling             │
  │   │   ├─ ecommerce tools as LangChain StructuredTool      │
  │   │   ├─ HITL confirmation tool policy                    │
  │   │   └─ memory + episodic retrieval                      │
  │   └─ deterministic fallback agents                        │
  │                                                           │
  │ Tool Layer                                                │
  │   ├─ SearchTools -> Search Service                        │
  │   └─ CoreTools   -> Core Service                          │
  │                                                           │
  │ ChatStore                                                 │
  │   ├─ chatSessions / chatMessages / pendingActions         │
  │   ├─ agentRuns / agentToolCalls / agentInterrupts         │
  │   └─ chatMemories / chatEpisodes                          │
  └───────────────────────────────────────────────────────────┘
        │                                  │
        ▼                                  ▼
  Search Service (4001)             Core Service (4000)
  product search/facts              auth, cart, orders,
                                    returns, support, audit
```

The production target is `deepagents.create_deep_agent` with ecommerce-only tools. The current implementation attempts the Deep Agents path first when dependencies and `LLM_API_KEY` are available, then safely falls back to the existing deterministic assistant behavior when the live agent runtime is unavailable. Fallback responses do not claim Deep Agents or MCP execution.

---

## Features

- Authenticated shopping and support chat sessions.
- Deep Agents-oriented harness wrapper with `AGENT_HARNESS=deepagents`.
- Ecommerce tool wrappers for product search, product detail, similar products, matching, comparison, cart reads, user preferences, orders, return eligibility, return policy, and confirmation-producing mutation proposals.
- Human-in-the-loop pending actions for cart additions, return requests, and support tickets.
- Token-aware context assembly:
  - keeps recent messages,
  - uses session summaries,
  - retrieves scoped memories/episodes,
  - prunes older low-relevance records,
  - caps large tool results before sending them back to the model.
- Transient retry policy:
  - retries read-only/idempotent model/tool/downstream failures,
  - classifies non-retriable auth/validation/ownership/policy errors,
  - avoids blind retries for mutating operations,
  - records retry metadata in run/tool records.
- MongoDB Atlas persistence with file-backed local fallback.
- Agent run, tool call, memory, and episode records.
- Local Codex MCP readiness metadata retained for demo compatibility.

---

## Runtime Behavior

### Message Flow

```text
POST /api/assistant/{shopping|support}/messages
  -> validate Core session
  -> persist user message
  -> build AgentRunContext
  -> retrieve summary, recent messages, memories, and episodes
  -> assemble token-budgeted context
  -> try Deep Agents run
      -> LLM selects ecommerce tools
      -> tool executor validates args and applies retry policy
      -> confirmation tools create pending actions instead of Core writes
      -> final assistant text is normalized
  -> if Deep Agents cannot run, use deterministic fallback
  -> persist assistant message, run metadata, tool/audit metadata
```

### Fallback Rules

Deep Agents is skipped when:

- `AGENTIC_ENABLED=false`.
- `deepagents` / LangChain packages are not installed.
- `LLM_API_KEY` is empty or placeholder-like.
- the Deep Agents invocation fails.

In those cases, the service continues using the previous deterministic shopping/support flows so local demos and tests still work. The fallback is explicit in run metadata via `fallbackReason`, and public responses include `usedDeepAgents: false` only when the Deep Agents path actually returns a message.

### Human Confirmation

Mutation proposals create `pendingActions` first:

```text
Agent/tool proposes mutation
    │
    ▼
pendingActions record created
    │
    ▼
Frontend shows confirm/cancel
    │
    ▼
POST /api/assistant/actions/confirm
    │
    ▼
Core mutation executes only after confirmation
```

Supported confirmed actions:

- `add_to_cart`
- `create_return_request`
- `create_support_ticket`

---

## Local Voice Support Demo

Voice support is a development-only, local microphone/speaker flow in v1. It uses the MacBook microphone and speaker through `tools/voice_mock_telephony`; it does not provide a published phone number, Twilio/SIP ingress, or real PSTN calls.

### Prerequisites

- Core Service, Search Service, and Chat Service running locally.
- A configured ElevenLabs realtime Speech-to-Text API key and Text-to-Speech voice ID in `.env`.
- A configured private S3 recordings bucket if recording persistence is required for the session.
- PortAudio installed on macOS:

```bash
brew install portaudio
```

- Voice mock dependencies installed into the selected local Python environment:

```bash
python3 -m pip install -e tools/voice_mock_telephony
```

### Run a local call

Set `APP_ENV=development` and `VOICE_TELEPHONY_PROVIDER=local`. Ensure the Chat Service has the same `VOICE_STREAM_WS_AUTH_TOKEN` as the mock tool, then start the relay from the repository root:

```bash
scripts/run_voice_mock_telephony.sh --caller-phone +15555550100
```

The optional caller number is only a soft ANI hint. It never authorizes account access: callers must still verify an order number plus a last name or postal code before the agent may reveal or change order-specific data. The local tool sends PCM16/16 kHz mono frames to `ws://localhost:4002/api/voice/stream`; Chat Service opens one persistent ElevenLabs real-time STT WebSocket for that call, base64-encodes and forwards frames, runs the `voice_support` agent only for a `committed_transcript`, synthesizes TTS, and records both directions.

The upstream STT connection uses `ELEVENLABS_STT_REALTIME_WS_URL` with `model_id=scribe_v2_realtime`, `audio_format=pcm_16000`, `commit_strategy=vad`, `vad_silence_threshold_secs=1.5`, `no_verbatim=true`, and `include_timestamps=true`. `partial_transcript` packets are ephemeral: Chat Service neither persists them nor sends them to the agent, tools, or TTS. ElevenLabs VAD commits are the authoritative turn boundary; the local VAD/utterance buffer is not used. Word-end timestamps on each committed transcript trim the replay buffer, so reconnect replay includes only PCM later than the committed session-relative audio boundary.

Use Ctrl+C to stop the local call. The server finalizes the call record and attempts the recording upload even if a turn fails.

### Safeguards and limitations

- The launcher refuses to run outside `APP_ENV=development`.
- `VOICE_TELEPHONY_PROVIDER=elevenlabs_twilio` is reserved for Phase F and fails fast; there is no Twilio, SIP, tunnel, or real phone-number implementation in v1.
- No tunnel is needed for local use: the mock tool connects to Chat Service over localhost and Chat Service makes outbound secure WSS calls for STT plus HTTPS calls for TTS.
- Voice mutations require an explicit spoken `yes`, `yes please`, `please do`, or `confirm`. Other replies—including `no` and `cancel`—leave pending actions unexecuted.
- S3 retention/lifecycle hardening remains deferred. The current implementation stores only the private bucket/key in call metadata and never exposes recording URLs to the frontend.

---

## Prerequisites

- Python 3.11 or newer.
- Core Service running on `CORE_SERVICE_BASE_URL`.
- Search Service running on `SEARCH_SERVICE_BASE_URL`.
- MongoDB Atlas URI if durable persistence is desired.
- OpenAI-compatible LLM credentials for live Deep Agents execution.
- Chat Service Python dependencies installed with:

```bash
python3 -m pip install -e services/chat_service
```

This installs `deepagents`, `langchain`, `langgraph`, and `langchain-openai` in addition to FastAPI and MongoDB dependencies.

Quick dependency check:

```bash
PYTHONPATH=services/chat_service python3 - <<'PY'
from app.agentic.service import agent_service
print(agent_service.metadata())
PY
```

---

## Configuration

Core service access:

| Variable | Default | Description |
|---|---|---|
| `CORE_SERVICE_BASE_URL` | `http://localhost:4000` | Core Service for auth, cart, orders, returns, support |
| `SEARCH_SERVICE_BASE_URL` | `http://localhost:4001` | Search Service for products |
| `CHAT_SERVICE_INTERNAL_TOKEN` | `` | Internal credential for audit-log writes to Core |
| `SEARCH_SERVICE_INTERNAL_TOKEN` | `` | Token sent by Chat when calling Search |

Persistence:

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `` | Enables MongoDB Atlas persistence when set |
| `MONGODB_DB` | `ecommerce_demo` | Atlas database name |
| `CHAT_SERVICE_DATA_PATH` | `./artifacts/chat_service/state.json` | File-backed fallback path |

LLM provider:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Provider label |
| `LLM_MODEL` | `gpt-5.4` | Model/deployment identifier |
| `LLM_API_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL |
| `LLM_CHAT_COMPLETIONS_PATH` | `/chat/completions` | Legacy chat-completions path used by fallback client |
| `LLM_API_KEY` | `` | Required for live LLM and Deep Agents calls |
| `LLM_TIMEOUT_MS` | `60000` | LLM timeout |
| `LLM_MAX_OUTPUT_TOKENS` | `1200` | Output budget |
| `LLM_TEMPERATURE` | `0.3` | Sampling temperature |
| `LLM_STREAMING_ENABLED` | `true` | Streaming flag for legacy LLM client |

Agent runtime:

| Variable | Default | Description |
|---|---|---|
| `AGENT_HARNESS` | `deepagents` | Production harness selector |
| `AGENTIC_ENABLED` | `true` | Enables Deep Agents attempt before fallback |
| `AGENT_MAX_MODEL_CALLS_PER_RUN` | `8` | Intended model-call limit per run |
| `AGENT_MAX_TOOL_CALLS_PER_RUN` | `12` | Intended tool-call limit per run |
| `AGENT_TOOL_TIMEOUT_MS` | `15000` | Tool timeout budget |
| `AGENT_STREAMING_ENABLED` | `true` | Future streaming toggle |
| `AGENT_MEMORY_ENABLED` | `true` | Enables memory retrieval/write hooks |
| `AGENT_EPISODIC_MEMORY_ENABLED` | `true` | Enables episode retrieval/write hooks |
| `AGENT_HITL_ENABLED` | `true` | Enables interrupt/confirmation policy |
| `AGENT_DEEPAGENTS_ENABLE_SUBAGENTS` | `true` | Enables configured subagent specs |
| `AGENT_DEEPAGENTS_MEMORY_PATHS` | `/memories/preferences.md,/memories/episodes.md` | Deep Agents memory paths |
| `AGENT_DEEPAGENTS_FILESYSTEM_POLICY` | `deny` | Documentation/runtime policy for filesystem access |

Retry policy:

| Variable | Default | Description |
|---|---|---|
| `AGENT_RETRY_MAX_ATTEMPTS` | `3` | Max attempts for retry-safe operations |
| `AGENT_RETRY_BASE_DELAY_MS` | `250` | Initial backoff |
| `AGENT_RETRY_MAX_DELAY_MS` | `3000` | Backoff cap |
| `AGENT_RETRY_JITTER_ENABLED` | `true` | Adds jitter to agent retry helper |
| `AGENT_RETRYABLE_STATUS_CODES` | `408,409,425,429,500,502,503,504` | HTTP statuses treated as transient |

Context-window policy:

| Variable | Default | Description |
|---|---|---|
| `AGENT_CONTEXT_MAX_INPUT_TOKENS` | `24000` | Hard estimated input cap |
| `AGENT_CONTEXT_TARGET_INPUT_TOKENS` | `18000` | Target context size before invoking model |
| `AGENT_CONTEXT_RECENT_MESSAGE_LIMIT` | `12` | Recent raw messages preserved first |
| `AGENT_CONTEXT_RELEVANCE_TOP_K` | `8` | Relevant older messages/memories/episodes |
| `AGENT_CONTEXT_SUMMARY_MAX_TOKENS` | `1200` | Summary token cap |
| `AGENT_CONTEXT_TOOL_RESULT_MAX_TOKENS` | `1600` | Tool-result compaction cap |

Codex MCP compatibility metadata:

| Variable | Default | Description |
|---|---|---|
| `CODEX_MCP_ENABLED` | `true` | Enables MCP readiness metadata |
| `CODEX_MCP_TRANSPORT` | `stdio` | `stdio` or `http` |
| `CODEX_MCP_COMMAND` | `codex` | Command for stdio readiness check |
| `CODEX_MCP_ARGS` | `mcp,serve` | Command args |
| `CODEX_MCP_URL` | `http://localhost:9000/mcp` | HTTP MCP URL |
| `CODEX_MCP_TIMEOUT_MS` | `120000` | MCP timeout |

---

## Persistence

`ChatStore` uses MongoDB Atlas when `MONGODB_URI` is configured and file-backed JSON otherwise.

Collections/state keys:

- `chatSessions`: session owner, type, context, title/summary, status, message count.
- `chatMessages`: user/assistant content and metadata.
- `pendingActions`: confirmation-gated mutations.
- `agentRuns`: Deep Agents/fallback run records, context-window metadata, retry metadata, usage, errors.
- `agentToolCalls`: tool name, redacted inputs, compact outputs, attempts, retryability, latency, confirmation flags.
- `agentInterrupts`: future graph interrupt records.
- `chatMemories`: user-scoped long-term memories.
- `chatEpisodes`: episodic records with outcomes and related entities.

Mongo indexes for the agent/memory collections are created in `mongo.ensure_indexes()`.

---

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Readiness with backend, LLM, agent, MCP, and database metadata |
| `POST` | `/api/assistant/shopping/sessions` | Create a shopping assistant session |
| `GET` | `/api/assistant/shopping/sessions` | Find latest active shopping session |
| `GET` | `/api/assistant/shopping/sessions/history` | List shopping sessions |
| `POST` | `/api/assistant/shopping/messages` | Send shopping assistant message |
| `GET` | `/api/assistant/shopping/sessions/{id}/messages` | Retrieve shopping messages |
| `POST` | `/api/assistant/support/sessions` | Create support session |
| `GET` | `/api/assistant/support/sessions` | Find latest active support session |
| `GET` | `/api/assistant/support/sessions/history` | List support sessions |
| `GET` | `/api/assistant/support/sessions/{id}/messages` | Retrieve support messages |
| `POST` | `/api/assistant/support/messages` | Send support message |
| `POST` | `/api/assistant/actions/confirm` | Confirm or cancel pending action |

---

## Run

Start Core and Search first, then Chat Service:

```bash
set -a
source .env
set +a

PYTHONPATH=services/chat_service \
uvicorn app.main:app --host 127.0.0.1 --port 4002
```

Health check:

```bash
curl http://127.0.0.1:4002/api/health | python3 -m json.tool
```

Important health fields:

- `.data.agent.harness`
- `.data.agent.deepagentsAvailable`
- `.data.agent.context`
- `.data.agent.retry`
- `.data.database`
- `.data.mcp`

---

## Validation

Compile check:

```bash
PYTHONPATH=services/chat_service \
python3 -m py_compile $(find services/chat_service/app -name '*.py' -print)
```

Agent runtime import smoke:

```bash
PYTHONPATH=services/chat_service python3 - <<'PY'
from app.agentic.service import agent_service
meta = agent_service.metadata()
print(meta["harness"], meta["enabled"], "context" in meta, "retry" in meta)
PY
```

Cross-service API tests, with Core/Search/Chat running:

```bash
pytest tests/api/test_ai_agents_mcp.py
pytest tests/api
```

---

## Troubleshooting

Deep Agents path is not used:

- Install Chat Service dependencies again: `python3 -m pip install -e services/chat_service`.
- Confirm `LLM_API_KEY` is not empty or placeholder-like.
- Confirm `AGENTIC_ENABLED=true`.
- Inspect `/api/health`; `agent.deepagentsAvailable` should be `true`.

Chat works but audit writes fail:

- Set the same `CHAT_SERVICE_INTERNAL_TOKEN` in Core and Chat.
- Do not use placeholder values such as `replace-with-chat-service-token`.

Search/Core calls fail transiently:

- Read-only calls are retried according to `AGENT_RETRY_*`.
- Non-retriable auth/ownership/validation/policy errors are not retried.
- Mutating actions remain confirmation-gated and are not blindly retried.

LLM context is too large:

- Lower `AGENT_CONTEXT_TARGET_INPUT_TOKENS`.
- Lower `AGENT_CONTEXT_RECENT_MESSAGE_LIMIT`.
- Check `agentRuns.contextWindow` for messages included/dropped and pruning strategy.

MCP readiness is false:

- The current agentic path does not depend on MCP for normal chat execution.
- MCP metadata remains for demo compatibility; install/configure Codex CLI only if you need MCP readiness checks.
