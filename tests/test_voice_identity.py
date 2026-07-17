"""Unit tests for caller ANI hints and hard voice verification."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.config import ChatServiceSettings  # noqa: E402
from app.voice.identity import VoiceIdentityResolver  # noqa: E402


def test_ani_match_is_soft_identity_only() -> None:
    """A verified phone lookup seeds a hint but does not authorize account access."""

    resolver = VoiceIdentityResolver(ChatServiceSettings(voice_caller_verification_max_attempts=2))
    with patch("app.voice.identity.core_tools.lookup_verified_user_by_phone", return_value={"userId": "user-1"}):
        identity = resolver.begin("call-1", "+15555550100")

    assert identity.soft_user_id == "user-1"
    assert identity.verified is False
    assert identity.verified_user_id is None


def test_hard_verification_binds_user_and_locks_after_two_failures() -> None:
    """Correct ownership verifies a caller; repeated generic failures lock the call."""

    resolver = VoiceIdentityResolver(ChatServiceSettings(voice_caller_verification_max_attempts=2))
    resolver.begin("call-ok")
    with patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "user-1"}):
        verified = resolver.verify("call-ok", "ORD-1", last_name="Smith")
    assert verified.verified is True
    assert verified.verified_user_id == "user-1"

    resolver.begin("call-failed")
    with patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": False}):
        first = resolver.verify("call-failed", "ORD-1", last_name="Wrong")
        first_locked = first.locked
        second = resolver.verify("call-failed", "ORD-1", last_name="Wrong")
    assert first_locked is False
    assert second.locked is True
    assert second.verified is False
