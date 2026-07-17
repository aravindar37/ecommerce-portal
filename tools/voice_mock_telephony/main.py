"""Development-only microphone/speaker relay for the local voice WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _websocket_url(raw_url: str, token: str) -> str:
    """Attach the shared stream token without logging either the URL or token."""

    parsed = urlsplit(raw_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["token"] = token
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def _settings() -> tuple[str, str, int]:
    """Read the minimum local-only transport settings."""

    if os.getenv("APP_ENV", "development") != "development":
        raise RuntimeError("Voice mock telephony is available only when APP_ENV=development.")
    if os.getenv("VOICE_TELEPHONY_PROVIDER", "local") != "local":
        raise RuntimeError("VOICE_TELEPHONY_PROVIDER must be local; real telephony is not implemented.")
    target_url = os.getenv("VOICE_MOCK_TELEPHONY_TARGET_WS_URL", "").strip()
    token = os.getenv("VOICE_STREAM_WS_AUTH_TOKEN", "").strip()
    if not target_url or not token:
        raise RuntimeError("VOICE_MOCK_TELEPHONY_TARGET_WS_URL and VOICE_STREAM_WS_AUTH_TOKEN are required.")
    sample_rate = int(os.getenv("VOICE_MOCK_TELEPHONY_SAMPLE_RATE", "16000"))
    if sample_rate != 16000 or os.getenv("VOICE_MOCK_TELEPHONY_AUDIO_FORMAT", "pcm16").lower() != "pcm16":
        raise RuntimeError("The local voice pipeline requires pcm16 audio at 16000 Hz.")
    return target_url, token, sample_rate


async def _run(caller_phone_number: str | None) -> None:
    """Capture 100 ms PCM16 microphone frames and play agent PCM16 responses."""

    try:
        import pyaudio
        import websockets
    except ImportError as exc:
        raise RuntimeError("Install the voice-mock dependencies before running this tool.") from exc

    target_url, token, sample_rate = _settings()
    chunk_frames = sample_rate // 10
    audio = pyaudio.PyAudio()
    input_stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        input=True,
        frames_per_buffer=chunk_frames,
    )
    output_stream = audio.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=sample_rate,
        output=True,
        frames_per_buffer=chunk_frames,
    )
    stop_requested = asyncio.Event()

    def request_stop(*_: object) -> None:
        stop_requested.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            pass

    try:
        async with websockets.connect(_websocket_url(target_url, token), max_size=None) as websocket:
            await websocket.send(json.dumps({"type": "start", "callerPhoneNumber": caller_phone_number}))
            started = await websocket.recv()
            if not isinstance(started, str):
                raise RuntimeError("Voice server did not acknowledge session start.")
            control = json.loads(started)
            if control.get("type") != "started":
                raise RuntimeError(f"Voice server refused session start: {control.get('code', 'unknown error')}")
            print("Voice session started. Speak normally; press Ctrl+C to hang up.")

            async def receive_audio() -> None:
                async for message in websocket:
                    if isinstance(message, bytes):
                        await asyncio.to_thread(output_stream.write, message)
                    else:
                        response = json.loads(message)
                        if response.get("type") == "error":
                            print(f"Voice server error: {response.get('code', 'unknown')}", file=sys.stderr)

            receiver = asyncio.create_task(receive_audio())
            try:
                while not stop_requested.is_set():
                    frame = await asyncio.to_thread(input_stream.read, chunk_frames, False)
                    await websocket.send(frame)
            finally:
                await websocket.send(json.dumps({"type": "stop"}))
                await receiver
    finally:
        input_stream.stop_stream()
        input_stream.close()
        output_stream.stop_stream()
        output_stream.close()
        audio.terminate()


def main() -> int:
    """Run the local relay with an optional development ANI hint."""

    parser = argparse.ArgumentParser(description="Stream microphone PCM16 audio to the local Chat Service voice endpoint.")
    parser.add_argument("--caller-phone", help="Optional E.164 test caller number used only as a soft ANI hint.")
    args = parser.parse_args()
    try:
        asyncio.run(_run(args.caller_phone))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Voice mock telephony failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
