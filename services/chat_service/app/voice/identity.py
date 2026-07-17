"""Caller identity state for a single voice session."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import ChatServiceSettings, settings
from app.tools.core import core_tools


@dataclass
class VoiceIdentity:
    """The minimum server-only identity state retained for one call."""

    call_id: str
    caller_phone_number: str | None = None
    soft_user_id: str | None = None
    verified_user_id: str | None = None
    verification_attempts: int = 0
    locked: bool = False

    @property
    def verified(self) -> bool:
        return bool(self.verified_user_id) and not self.locked


class VoiceIdentityResolver:
    """Resolve ANI hints and hard verification without exposing account facts."""

    def __init__(self, config: ChatServiceSettings = settings) -> None:
        self.config = config
        self._sessions: dict[str, VoiceIdentity] = {}

    def begin(self, call_id: str, caller_phone_number: str | None = None) -> VoiceIdentity:
        """Start a call identity context and optionally use its ANI as a soft hint."""

        identity = VoiceIdentity(call_id=call_id, caller_phone_number=caller_phone_number)
        if caller_phone_number:
            match = core_tools.lookup_verified_user_by_phone(caller_phone_number)
            if isinstance(match, dict) and match.get("userId"):
                identity.soft_user_id = str(match["userId"])
        self._sessions[call_id] = identity
        return identity

    def get(self, call_id: str) -> VoiceIdentity | None:
        """Return current server-only voice identity state."""

        return self._sessions.get(call_id)

    def verify(self, call_id: str, order_number: str, last_name: str | None = None, postal_code: str | None = None) -> VoiceIdentity:
        """Hard-verify ownership with Core and lock after configured failures."""

        identity = self._sessions.get(call_id)
        if not identity:
            identity = self.begin(call_id)
        if identity.locked:
            return identity
        result = core_tools.verify_caller_by_order(order_number, last_name, postal_code, identity.caller_phone_number)
        user_id = result.get("userId") if isinstance(result, dict) and result.get("verified") else None
        if user_id:
            identity.verified_user_id = str(user_id)
            return identity
        identity.verification_attempts += 1
        if identity.verification_attempts >= self.config.voice_caller_verification_max_attempts:
            identity.locked = True
        return identity

    def end(self, call_id: str) -> None:
        """Discard identity state as soon as the call ends."""

        self._sessions.pop(call_id, None)


voice_identity = VoiceIdentityResolver()
