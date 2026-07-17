"""Deterministic PCM16 voice-activity segmentation for the local voice channel."""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field


@dataclass
class VoiceActivityDetector:
    """Buffer PCM16 audio and emit an utterance after sustained silence."""

    sample_rate: int
    silence_threshold_db: float
    silence_duration_ms: int
    min_utterance_ms: int
    _frames: list[bytes] = field(default_factory=list)
    _speech_seen: bool = False
    _speech_bytes: int = 0
    _silence_ms: int = 0

    @property
    def bytes_per_ms(self) -> float:
        return self.sample_rate * 2 / 1000

    def _duration_ms(self, frame: bytes) -> int:
        return max(1, round(len(frame) / self.bytes_per_ms))

    def _is_silent(self, frame: bytes) -> bool:
        if not frame:
            return True
        samples = tuple(struct.iter_unpack("<h", frame))
        rms = math.sqrt(sum(sample[0] * sample[0] for sample in samples) / len(samples))
        if rms <= 0:
            return True
        db = 20 * math.log10(rms / 32768)
        return db < self.silence_threshold_db

    def push(self, frame: bytes) -> bytes | None:
        """Add one PCM16 frame and return a completed utterance when available."""

        if len(frame) % 2:
            raise ValueError("PCM16 frames must contain an even number of bytes")
        if not frame:
            return None
        duration_ms = self._duration_ms(frame)
        silent = self._is_silent(frame)
        if not self._speech_seen:
            if silent:
                return None
            self._speech_seen = True
        self._frames.append(frame)
        if silent:
            self._silence_ms += duration_ms
        else:
            self._speech_bytes += len(frame)
            self._silence_ms = 0
        if self._speech_seen and self._silence_ms >= self.silence_duration_ms:
            utterance = b"".join(self._frames)
            speech_duration_ms = round(self._speech_bytes / self.bytes_per_ms)
            self.reset()
            return utterance if speech_duration_ms >= self.min_utterance_ms else None
        return None

    def flush(self) -> bytes | None:
        """Emit a remaining utterance when a caller closes the stream."""

        if not self._frames:
            return None
        utterance = b"".join(self._frames)
        speech_duration_ms = round(self._speech_bytes / self.bytes_per_ms)
        self.reset()
        return utterance if speech_duration_ms >= self.min_utterance_ms else None

    def reset(self) -> None:
        """Discard buffered frames and reset speech detection."""

        self._frames.clear()
        self._speech_seen = False
        self._speech_bytes = 0
        self._silence_ms = 0
