"""Unit tests for service-authenticated voice Core tool wrappers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.tools.core import CoreTools  # noqa: E402


def test_payment_details_uses_verified_voice_identity_and_short_timeout() -> None:
    """Payment reads use trusted on-behalf headers rather than a browser cookie."""

    tools = CoreTools()
    with patch("app.tools.core.request_json", return_value={"data": {"status": "paid", "method": "demo"}, "error": None}) as request:
        payment = tools.get_payment_details("user-1", "ORD-1")

    assert payment == {"status": "paid", "method": "demo"}
    assert request.call_args.kwargs["headers"]["x-on-behalf-of-user-id"] == "user-1"
    assert request.call_args.kwargs["headers"]["x-service-token"]
    assert request.call_args.kwargs["timeout_seconds"] == 10


def test_verify_caller_sends_only_pre_authorization_data() -> None:
    """Hard verification has an explicit timeout and does not use caller cookies."""

    tools = CoreTools()
    response = {"data": {"verified": True, "userId": "user-1"}, "error": None}
    with patch("app.tools.core.request_json", return_value=response) as request:
        result = tools.verify_caller_by_order("ORD-1", last_name="Smith", caller_phone_number="+15555550100")

    assert result["verified"] is True
    assert request.call_args.args[0] == "POST"
    assert request.call_args.kwargs["payload"] == {
        "orderNumber": "ORD-1",
        "lastName": "Smith",
        "postalCode": None,
        "callerPhoneNumber": "+15555550100",
    }
    assert request.call_args.kwargs["timeout_seconds"] == 10
    assert request.call_args.kwargs["retry_safe"] is False


def test_order_update_rejects_unsafe_retry_and_uses_verified_identity() -> None:
    """Confirmed mutations use service authentication and are not retried unsafely."""

    tools = CoreTools()
    with patch("app.tools.core.request_json", return_value={"data": {"_id": "order-1", "status": "cancelled"}, "error": None}) as request:
        updated = tools.update_voice_order("user-1", "ORD-1", "cancel")

    assert updated["status"] == "cancelled"
    assert request.call_args.kwargs["headers"]["x-on-behalf-of-user-id"] == "user-1"
    assert request.call_args.kwargs["retry_safe"] is False
