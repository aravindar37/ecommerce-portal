# Codex Ecommerce Demo Architecture

## Runtime Topology

```mermaid
flowchart LR
    Browser[Browser]
    Web[Web App<br/>Next.js / React<br/>:3000]
    Core[Core Service<br/>FastAPI :4000<br/>Identity, carts, checkout,<br/>orders, returns, support]
    Search[Search Service<br/>FastAPI :4001<br/>Catalogue, facets, keyword,<br/>semantic and hybrid search]
    Chat[Chat Service<br/>FastAPI :4002<br/>Shopping, support, and voice agents]

    Atlas[(MongoDB Atlas<br/>Transactional documents<br/>Search and vector indexes)]
    Images[Local product images<br/>Fashion dataset]
    Embeddings[Embedding provider<br/>MongoDB Voyage AI or Ollama]
    LLM[LLM provider<br/>OpenAI-compatible endpoint]
    MCP[Local Codex MCP server]
    ElevenLabs[ElevenLabs<br/>Realtime STT and streaming TTS]
    S3[(Private S3 recordings)]
    VoiceTester[Local Voice Call Tester<br/>:4011, development only]

    Browser --> Web
    Web -->|/api/core/*| Core
    Web -->|/api/search/*| Search
    Web -->|/api/chat/*| Chat

    Core <--> Atlas
    Core --> Images
    Search <--> Atlas
    Search <--> Embeddings
    Chat <--> Atlas
    Chat --> LLM
    Chat <--> MCP
    Chat -->|authenticated service calls| Core
    Chat -->|authenticated retrieval calls| Search
    Search -->|activity events| Core

    Browser <-->|PCM16 WebSocket via local relay| VoiceTester
    VoiceTester <-->|/api/voice/stream| Chat
    Chat <-->|Persistent realtime STT WebSocket| ElevenLabs
    Chat -->|Streaming TTS HTTP| ElevenLabs
    Chat -->|private WAV upload| S3
```

## Service Ownership

| Component | Owns | Collaborates with |
| --- | --- | --- |
| Web App | Ecommerce UI, browser session experience, app-local API proxies | Core, Search, Chat |
| Core Service | Authentication, users, carts, checkout, orders, returns, tickets, images, activity/audit records | MongoDB Atlas; receives trusted calls from Search and Chat |
| Search Service | Catalogue filters, facets, keyword, semantic, hybrid, and similar-product search | MongoDB Atlas; embedding provider; Core activity API |
| Chat Service | Shopping/support sessions, LLM routing, Codex MCP, agent tools, local voice support, recordings/transcripts | Core, Search, MongoDB Atlas, ElevenLabs, S3 |

## Local Voice Call Flow

```mermaid
sequenceDiagram
    participant Caller as Browser microphone/speaker
    participant Relay as Local Voice Call Tester :4011
    participant Chat as Chat Service :4002
    participant STT as ElevenLabs realtime STT
    participant Agent as Voice agent and Core/Search tools
    participant TTS as ElevenLabs streaming TTS
    participant Store as Atlas and private S3

    Caller->>Relay: PCM16 microphone frames
    Relay->>Chat: Authenticated WebSocket /api/voice/stream
    Chat->>STT: Persistent WSS input_audio_chunk frames
    STT-->>Chat: Committed transcript
    Chat->>Agent: Verified caller context and committed turn
    Agent-->>Chat: Spoken reply / confirmed action result
    Chat->>TTS: POST /v1/text-to-speech/{voice-id}/stream
    TTS-->>Chat: PCM16 reply audio
    Chat-->>Relay: Binary PCM16 reply
    Relay-->>Caller: Speaker playback
    Chat->>Store: Persist call state, transcript summary, and WAV recording
```

## Security Boundaries

- Browser traffic is routed through the Next.js app-local proxy; service credentials remain server-side.
- Core owns ecommerce writes. Search reports activity to Core, and Chat calls Core/Search using internal service tokens.
- The local voice stream is limited to development and requires a WebSocket token. The browser relay keeps that token server-side.
- ElevenLabs credentials, LLM credentials, Atlas credentials, and S3 credentials are read from server environment variables only.
- Voice recordings are stored privately; the admin surface exposes recording status, not the bucket, key, caller number, raw audio, or provider secrets.