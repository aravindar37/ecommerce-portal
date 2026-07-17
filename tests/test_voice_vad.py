"""Synthetic PCM16 tests for voice utterance segmentation."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.voice.vad import VoiceActivityDetector  # noqa: E402


def frame(amplitude: int, duration_ms: int = 100, sample_rate: int = 16000) -> bytes:
    """Create a mono PCM16 fixture frame with a deterministic loudness."""

    return struct.pack("<h", amplitude) * (sample_rate * duration_ms // 1000)


def test_vad_emits_one_utterance_after_sustained_silence() -> None:
    """Speech separated by brief silence remains one utterance until the final pause."""

    detector = VoiceActivityDetector(sample_rate=16000, silence_threshold_db=-40, silence_duration_ms=600, min_utterance_ms=250)
    emitted = []
    for pcm in [frame(4000), frame(4000), frame(0), frame(0), frame(4000), frame(4000), *[frame(0) for _ in range(6)]]:
        utterance = detector.push(pcm)
        if utterance:
            emitted.append(utterance)

    assert len(emitted) == 1
    assert len(emitted[0]) == 12 * len(frame(0))


def test_vad_discards_short_noise_burst() -> None:
    """A sub-minimum transient does not create an STT request."""

    detector = VoiceActivityDetector(sample_rate=16000, silence_threshold_db=-40, silence_duration_ms=600, min_utterance_ms=250)
    assert detector.push(frame(4000)) is None
    assert detector.push(frame(0, 600)) is None
    assert detector.flush() is None
