"""Small, retrying clients for ElevenLabs standalone speech APIs."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from app.agentic.resilience import with_retry
from app.config import ChatServiceSettings, settings
from app.http import ServiceHttpError
from app.observability import logger, redact

Json = dict[str, Any]


class ElevenLabsSpeechClient:
    """Call ElevenLabs STT and TTS without exposing credentials to callers."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config

    def readiness(self) -> Json:
        """Return non-sensitive dependency status for health checks."""

        api_key = self.config.elevenlabs_api_key.strip()
        return {
            "sttConfigured": bool(api_key and self.config.elevenlabs_stt_api_url.strip()),
            "ttsConfigured": bool(api_key and self.config.elevenlabs_voice_id.strip() and self.config.elevenlabs_tts_api_url.strip()),
            "sttModel": self.config.elevenlabs_stt_model,
            "ttsModel": self.config.elevenlabs_tts_model,
            "ttsOutputFormat": self.config.elevenlabs_tts_output_format,
        }

    def _headers(self) -> dict[str, str]:
        if not self.config.elevenlabs_api_key.strip():
            raise ServiceHttpError(503, "ElevenLabs API key is not configured")
        return {"xi-api-key": self.config.elevenlabs_api_key, "accept": "application/json"}

    def transcribe_pcm16(self, audio: bytes, sample_rate: int = 16000) -> str:
        """Send raw PCM16 audio and return a non-empty transcript string."""

        if not audio:
            raise ServiceHttpError(400, "Audio is required for transcription")
        return with_retry("elevenlabs_stt", lambda: self._transcribe_once(audio, sample_rate), idempotent=True)

    def _transcribe_once(self, audio: bytes, sample_rate: int) -> str:
        boundary = f"----stylesense-{uuid.uuid4().hex}"
        fields = [
            ("model_id", self.config.elevenlabs_stt_model),
            ("file_format", "pcm_s16le"),
            ("sample_rate", str(sample_rate)),
        ]
        body = bytearray()
        for name, value in fields:
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="file"; filename="utterance.pcm"\r\n')
        body.extend(b"Content-Type: audio/L16\r\n\r\n")
        body.extend(audio)
        body.extend(f"\r\n--{boundary}--\r\n".encode())
        headers = {**self._headers(), "content-type": f"multipart/form-data; boundary={boundary}"}
        payload = self._request(self.config.elevenlabs_stt_api_url, bytes(body), headers)
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ServiceHttpError(502, "ElevenLabs STT returned invalid JSON") from exc
        transcript = decoded.get("text") if isinstance(decoded, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            raise ServiceHttpError(502, "ElevenLabs STT returned no transcript")
        return transcript.strip()

    def synthesize_pcm16(self, text: str) -> bytes:
        """Synthesize short agent text as raw PCM16 in the configured format."""

        if not text.strip():
            raise ServiceHttpError(400, "Text is required for speech synthesis")
        return with_retry("elevenlabs_tts", lambda: self._synthesize_once(text), idempotent=True)

    def _synthesize_once(self, text: str) -> bytes:
        if not self.config.elevenlabs_voice_id.strip():
            raise ServiceHttpError(503, "ElevenLabs voice ID is not configured")
        base_url = f"{self.config.elevenlabs_tts_api_url.rstrip('/')}/{urllib.parse.quote(self.config.elevenlabs_voice_id)}"
        url = f"{base_url}?{urllib.parse.urlencode({'output_format': self.config.elevenlabs_tts_output_format})}"
        payload = json.dumps({"text": text, "model_id": self.config.elevenlabs_tts_model}).encode("utf-8")
        audio = self._request(url, payload, {**self._headers(), "content-type": "application/json", "accept": "audio/pcm"})
        if not audio:
            raise ServiceHttpError(502, "ElevenLabs TTS returned no audio")
        return audio

    def _request(self, url: str, data: bytes, headers: dict[str, str]) -> bytes:
        request = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=max(self.config.voice_turn_max_latency_ms / 1000, 1)) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            logger.warning("voice.elevenlabs.http_error status=%s error=%s", exc.code, redact(exc.reason))
            raise ServiceHttpError(exc.code, "ElevenLabs speech request failed") from exc
        except urllib.error.URLError as exc:
            logger.warning("voice.elevenlabs.unavailable error=%s", redact(str(exc)))
            raise ConnectionError("ElevenLabs speech service is unavailable") from exc


elevenlabs_speech = ElevenLabsSpeechClient()
