"""Local browser tester for ElevenLabs realtime STT and streaming TTS.

The browser never receives the ElevenLabs API key. This server is intentionally
development-only and must be bound to loopback through the launcher script.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import certifi
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, SecretStr
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static" / "index.html"
LOGGER = logging.getLogger("elevenlabs_api_tester")
SAMPLE_RATE = 16_000
ALLOWED_HOSTS = {"api.elevenlabs.io"}


class SttConfig(BaseModel):
	"""The safe realtime STT options exposed by the local diagnostic UI."""

	api_key: SecretStr | None = None
	model_id: str = Field(default="scribe_v2_realtime", min_length=1, max_length=100)
	audio_format: str = "pcm_16000"
	commit_strategy: str = "vad"
	vad_silence_threshold_secs: float = Field(default=1.5, gt=0, le=10)
	no_verbatim: bool = True
	include_timestamps: bool = True


class TtsRequest(BaseModel):
	"""Streaming TTS request forwarded by the local diagnostic proxy."""

	api_key: SecretStr | None = None
	voice_id: str = Field(min_length=1, max_length=100)
	model_id: str = Field(default="eleven_flash_v2_5", min_length=1, max_length=100)
	text: str = Field(min_length=1, max_length=5_000)
	output_format: str = "pcm_16000"
	endpoint: str = "https://api.elevenlabs.io/v1/text-to-speech"


def _api_key(provided_key: SecretStr | None = None) -> str:
	"""Prefer a user-supplied local credential, otherwise use the server environment."""

	if os.getenv("APP_ENV", "development") != "development":
		raise HTTPException(403, "The ElevenLabs API tester is development-only.")
	api_key = provided_key.get_secret_value().strip() if provided_key else ""
	api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "").strip()
	if not api_key or api_key.startswith("replace-with-"):
		raise HTTPException(503, "ELEVENLABS_API_KEY is not configured.")
	return api_key


def _approved_url(raw_url: str, *, websocket: bool) -> str:
	"""Allow only ElevenLabs production endpoints to avoid turning this into an SSRF proxy."""

	parsed = urllib.parse.urlsplit(raw_url)
	allowed_scheme = "wss" if websocket else "https"
	if parsed.scheme != allowed_scheme or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
		raise HTTPException(400, "Only the official api.elevenlabs.io endpoint is allowed.")
	return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def _stt_url(config: SttConfig) -> str:
	"""Build the documented realtime STT WSS request query."""

	endpoint = _approved_url(
		os.getenv("ELEVENLABS_STT_REALTIME_WS_URL", "wss://api.elevenlabs.io/v1/speech-to-text/realtime"),
		websocket=True,
	)
	if config.audio_format != "pcm_16000":
		raise HTTPException(400, "This tester streams mono PCM16 at 16000 Hz only.")
	if config.commit_strategy not in {"vad", "manual"}:
		raise HTTPException(400, "commit_strategy must be vad or manual.")
	query = urllib.parse.urlencode(
		{
			"model_id": config.model_id,
			"audio_format": config.audio_format,
			"commit_strategy": config.commit_strategy,
			"vad_silence_threshold_secs": str(config.vad_silence_threshold_secs),
			"no_verbatim": str(config.no_verbatim).lower(),
			"include_timestamps": str(config.include_timestamps).lower(),
		}
	)
	return f"{endpoint}?{query}"


def _event_summary(message: dict[str, Any]) -> dict[str, Any]:
	"""Log/send useful metadata while avoiding microphone audio and transcript text."""

	return {
		"message_type": message.get("message_type"),
		"textLength": len(message.get("text", "")) if isinstance(message.get("text"), str) else 0,
		"wordCount": len(message.get("words", [])) if isinstance(message.get("words"), list) else 0,
	}


async def _receive_upstream(upstream: Any, browser: WebSocket) -> None:
	"""Forward provider JSON messages as-is; the UI renders transcript events."""

	async for raw_message in upstream:
		if isinstance(raw_message, bytes):
			LOGGER.warning("stt_upstream_binary_message bytes=%s", len(raw_message))
			await browser.send_json({"type": "debug", "level": "warning", "message": "Provider sent an unexpected binary event."})
			continue
		try:
			message = json.loads(raw_message)
		except json.JSONDecodeError:
			LOGGER.warning("stt_upstream_invalid_json length=%s", len(raw_message))
			await browser.send_json({"type": "debug", "level": "warning", "message": "Provider sent invalid JSON."})
			continue
		if not isinstance(message, dict):
			continue
		LOGGER.debug("stt_upstream_event %s", _event_summary(message))
		await browser.send_json({"type": "provider_event", "event": message})


app = FastAPI(title="ElevenLabs Local API Tester", docs_url=None, redoc_url=None)


@app.get("/", include_in_schema=False)
async def page() -> FileResponse:
	"""Serve the single-page local diagnostic UI."""

	return FileResponse(STATIC)


@app.get("/api/config")
async def configuration() -> dict[str, str]:
	"""Expose non-sensitive defaults only."""

	return {
		"sttEndpoint": os.getenv("ELEVENLABS_STT_REALTIME_WS_URL", "wss://api.elevenlabs.io/v1/speech-to-text/realtime"),
		"sttModel": os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2_realtime"),
		"ttsEndpoint": os.getenv("ELEVENLABS_TTS_API_URL", "https://api.elevenlabs.io/v1/text-to-speech"),
		"ttsModel": os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"),
		"voiceId": os.getenv("ELEVENLABS_VOICE_ID", ""),
	}


@app.post("/api/tts")
async def text_to_speech(payload: TtsRequest, request: Request) -> Response:
	"""Request streaming ElevenLabs TTS and return the full PCM response to the UI."""

	api_key = _api_key(payload.api_key)
	if payload.output_format != "pcm_16000":
		raise HTTPException(400, "This tester supports pcm_16000 output only.")
	endpoint = _approved_url(payload.endpoint, websocket=False)
	url = f"{endpoint}/{urllib.parse.quote(payload.voice_id)}/stream?{urllib.parse.urlencode({'output_format': payload.output_format})}"
	body = json.dumps({"text": payload.text, "model_id": payload.model_id}).encode("utf-8")
	headers = {"xi-api-key": api_key, "accept": "audio/pcm", "content-type": "application/json"}
	LOGGER.debug("tts_request model=%s voice_id_length=%s text_length=%s", payload.model_id, len(payload.voice_id), len(payload.text))

	def send_request() -> tuple[int, bytes]:
		http_request = urllib.request.Request(url, data=body, headers=headers, method="POST")
		with urllib.request.urlopen(http_request, timeout=60, context=ssl.create_default_context(cafile=certifi.where())) as result:
			return result.status, result.read()

	try:
		status_code, audio = await asyncio.to_thread(send_request)
	except urllib.error.HTTPError as exc:
		LOGGER.warning("tts_http_error status=%s", exc.code)
		raise HTTPException(exc.code, "ElevenLabs TTS request failed; inspect the local server console for status metadata.") from exc
	except urllib.error.URLError as exc:
		LOGGER.warning("tts_transport_error type=%s", exc.reason.__class__.__name__)
		raise HTTPException(502, "ElevenLabs TTS is unavailable; inspect the local server console.") from exc
	except TimeoutError as exc:
		LOGGER.warning("tts_timeout")
		raise HTTPException(504, "ElevenLabs TTS timed out.") from exc
	LOGGER.debug("tts_response status=%s pcm_bytes=%s client=%s", status_code, len(audio), request.client.host if request.client else "unknown")
	return Response(content=audio, media_type="audio/L16", headers={"X-Audio-Sample-Rate": str(SAMPLE_RATE)})


@app.websocket("/ws/stt")
async def speech_to_text(browser: WebSocket) -> None:
	"""Relay browser PCM16 audio to a newly-established upstream realtime STT WSS session."""

	await browser.accept()
	upstream = None
	receiver: asyncio.Task[None] | None = None
	try:
		first_message = await asyncio.wait_for(browser.receive_json(), timeout=15)
		if not isinstance(first_message, dict) or first_message.get("type") != "connect":
			raise HTTPException(400, "The first WebSocket message must be a connect configuration.")
		config = SttConfig.model_validate(first_message.get("config", {}))
		url = _stt_url(config)
		api_key = _api_key(config.api_key)
		LOGGER.debug("stt_connect_requested model=%s commit_strategy=%s", config.model_id, config.commit_strategy)
		upstream = await connect(
			url,
			additional_headers={"xi-api-key": api_key},
			open_timeout=15,
			close_timeout=10,
			ssl=ssl.create_default_context(cafile=certifi.where()),
		)
		await browser.send_json({"type": "connected", "sampleRate": SAMPLE_RATE})
		LOGGER.info("stt_connected")
		receiver = asyncio.create_task(_receive_upstream(upstream, browser))

		while True:
			incoming = await browser.receive()
			if incoming["type"] == "websocket.disconnect":
				break
			if incoming.get("bytes") is not None:
				frame = incoming["bytes"]
				if not frame:
					continue
				await upstream.send(
					json.dumps(
						{
							"message_type": "input_audio_chunk",
							"audio_base_64": base64.b64encode(frame).decode("ascii"),
							"commit": False,
							"sample_rate": SAMPLE_RATE,
						},
						separators=(",", ":"),
					)
				)
				LOGGER.debug("stt_pcm_forwarded bytes=%s", len(frame))
				continue
			if incoming.get("text"):
				control = json.loads(incoming["text"])
				if control.get("type") == "stop":
					break
				if control.get("type") == "commit" and config.commit_strategy == "manual":
					await upstream.send(json.dumps({"message_type": "input_audio_chunk", "audio_base_64": "", "commit": True, "sample_rate": SAMPLE_RATE}))
					LOGGER.debug("stt_manual_commit_sent")
	except (HTTPException, ValueError, json.JSONDecodeError) as exc:
		detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
		LOGGER.warning("stt_configuration_error detail=%s", detail)
		await browser.send_json({"type": "error", "message": str(detail)})
	except ConnectionClosed as exc:
		LOGGER.warning("stt_provider_closed code=%s reason=%s", exc.code, exc.reason)
		await browser.send_json({"type": "error", "message": f"ElevenLabs closed the connection ({exc.code}: {exc.reason or 'no reason'})."})
	except WebSocketDisconnect:
		LOGGER.info("stt_browser_disconnected")
	except Exception as exc:
		LOGGER.exception("stt_relay_failed type=%s", exc.__class__.__name__)
		await browser.send_json({"type": "error", "message": f"STT relay failed: {exc.__class__.__name__}. Inspect the local server console."})
	finally:
		if receiver:
			receiver.cancel()
			await asyncio.gather(receiver, return_exceptions=True)
		if upstream:
			await upstream.close()
		LOGGER.info("stt_closed")
