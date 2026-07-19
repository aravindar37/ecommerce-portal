# ElevenLabs Local API Tester

Development-only HTML diagnostic page for the ElevenLabs realtime STT WebSocket and streaming TTS endpoint.

## Run

From the repository root, run [scripts/run_elevenlabs_api_tester.sh](../../scripts/run_elevenlabs_api_tester.sh), then open `http://127.0.0.1:4010` in a browser. The browser will ask for microphone permission only after **Start microphone** is selected.

## Behavior

- **Realtime STT**: establish the provider WSS connection first, then stream browser microphone audio as mono PCM16 at 16 kHz. The page displays partial and committed transcript events. For `manual` commits, use **Commit turn**; for `vad`, ElevenLabs commits after its configured silence threshold.
- **Streaming TTS**: submit text, voice ID, model, and PCM format. The server uses ElevenLabs' `/stream` endpoint, returns PCM16 to the browser, and the page plays it through the selected system speaker.
- An optional password-style API-key field supports testing a different key. A supplied value is used only for the current local request/session, is forwarded by the localhost proxy as the `xi-api-key` header, and is never logged, returned, or stored. When blank, the tester uses `ELEVENLABS_API_KEY` from the local environment. Debug logs report request metadata and provider/transport failures, without raw microphone frames, transcript text, or credentials.

## Safety boundaries

- The launcher binds to `127.0.0.1` and refuses non-development environments.
- The proxy only accepts `api.elevenlabs.io` upstream URLs, preventing arbitrary outbound proxying.
- Only `pcm_16000` is accepted because the browser microphone converter and speaker playback are explicitly configured for 16 kHz PCM16.

## Confirmed realtime STT model

Use `scribe_v2_realtime` with the realtime WSS endpoint. During validation on 2026-07-19, `scribe_v2` connected at the transport layer but produced an ElevenLabs `invalid_request` event; changing the model to `scribe_v2_realtime` produced the provider `session_started` event. The tester exposes this field so alternate provider-supported models can still be checked explicitly.