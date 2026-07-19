"""Tests for non-PII aggregate voice observability metrics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.observability import VoiceMetrics  # noqa: E402


def test_voice_metrics_report_lifecycle_counts_and_latency_averages() -> None:
    """Health metrics aggregate stages and outcomes without caller or transcript data."""

    metrics = VoiceMetrics()
    metrics.record_call_started()
    metrics.record_call_started()
    metrics.record_call_verified()
    metrics.record_stt_connection_opened()
    metrics.record_stt_partial_transcript()
    metrics.record_stt_partial_transcript()
    metrics.record_stt_committed_transcript()
    metrics.record_stt_connection_failed()
    metrics.record_turn(stt_ms=100, agent_ms=200, tts_ms=300, total_ms=600)
    metrics.record_turn(stt_ms=300, agent_ms=400, tts_ms=500, total_ms=1200)
    metrics.record_call_ended(duration_seconds=60, verified=True, escalated=False, recording_uploaded=True)
    metrics.record_call_ended(duration_seconds=120, verified=False, escalated=True, recording_uploaded=False)

    assert metrics.snapshot() == {
        "callsReceived": 2,
        "callsVerified": 1,
        "callsVerificationFailed": 1,
        "callsEscalated": 1,
        "callsEnded": 2,
        "recordingUploadSucceeded": 1,
        "recordingUploadFailed": 1,
        "averageCallDurationSeconds": 90.0,
        "realtimeStt": {
            "connectionsOpened": 1,
            "connectionsFailed": 1,
            "partialTranscripts": 2,
            "committedTranscripts": 1,
        },
        "turnCount": 2,
        "averageTurnLatencyMs": {"stt": 200.0, "agent": 300.0, "tts": 400.0, "total": 900.0},
    }
