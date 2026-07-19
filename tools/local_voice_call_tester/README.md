# Local Voice Call Tester

Development-only browser tool for a live local mock telephony call:

```text
browser microphone → localhost relay → Chat Service /api/voice/stream
→ ElevenLabs real-time STT → voice_support agent → ElevenLabs TTS → browser speaker
```

## Run

1. Run [scripts/start_voice_demo_services.sh](../../scripts/start_voice_demo_services.sh).
2. Run [scripts/run_local_voice_call_tester.sh](../../scripts/run_local_voice_call_tester.sh).
3. Open `http://127.0.0.1:4011`, start a call, and explicitly allow microphone access.
4. Follow the verification, order/return, and escalation prompts in the page. Hang up and load artifacts.

The page reports whether the final call persisted its voice-call session, chat messages, recording reference, linked escalation ticket, and null Twilio SID. It renders the restricted persisted transcript but never exposes credentials, caller phone values, or S3 object locations.

The relay writes detailed structured request/response traces to its terminal: authenticated Chat Service WebSocket connection, start/stop controls, each audio frame's byte count and cumulative count, agent-audio byte counts, Chat Service controls/errors, and the restricted artifact-read request/response shape. It deliberately redacts tokens and caller identity and logs counts/metadata instead of raw PCM, transcript content, or full response bodies.

## Safety

- Restricted to `APP_ENV=development` and binds to `127.0.0.1`.
- The relay retains the Chat Service stream token and admin token; neither reaches browser JavaScript.
- A browser microphone test requires user interaction and OS/browser permission.
