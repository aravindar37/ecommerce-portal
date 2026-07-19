"""Fake-model integration coverage for the text-only voice support agent."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "chat_service"))

from app.agentic.agent_specs import VOICE_SUPPORT_AGENT  # noqa: E402
from app.agentic.context import build_run_context  # noqa: E402
from app.agentic.deepagents_harness import DeepAgentsHarness  # noqa: E402
from app.agentic.models import AgentRunInput  # noqa: E402
from app.config import ChatServiceSettings  # noqa: E402
from app.dependencies import ChatContext  # noqa: E402
from app.voice.identity import voice_identity  # noqa: E402


class ToolAwareFakeChatModel(FakeMessagesListChatModel):
    """Deterministic model fixture that accepts the tools bound by LangGraph."""

    def bind_tools(self, tools: object, **kwargs: object) -> "ToolAwareFakeChatModel":
        return self


def tool_call(name: str, args: dict[str, object], call_id: str) -> AIMessage:
    """Build a normalized LangChain tool-call response."""

    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def run_voice_model(call_id: str, responses: list[AIMessage]):
    """Run the real voice spec with a scripted model and no provider access."""

    context = build_run_context(
        ChatContext(user={"_id": "voice-anonymous", "name": "Voice caller", "email": ""}, cookie_header=""),
        session_id="voice-session-1",
        session_type="voice_support",
        agent_id="voice_support",
        request_context={"channel": "voice", "callId": call_id},
        session_context={"callId": call_id},
    )
    harness = DeepAgentsHarness(ChatServiceSettings(agentic_enabled=True, llm_api_key="test-fake-key"))
    model = ToolAwareFakeChatModel(responses=responses)
    agent_input = AgentRunInput(
        message="I need help with my order.",
        history=[],
        summary="",
        relevant_memories=[],
        relevant_episodes=[],
        context=context,
    )
    with (
        patch("langchain_openai.ChatOpenAI", return_value=model),
        patch("app.agentic.deepagents_harness.store.create_agent_run"),
        patch("app.agentic.deepagents_harness.store.complete_agent_run"),
        patch("app.agentic.tools._audit"),
    ):
        return harness.run_message_with_spec(agent_input, VOICE_SUPPORT_AGENT)


def test_voice_spec_verifies_then_reads_order_in_same_run() -> None:
    """An order lookup cannot run until hard verification has bound the caller identity."""

    call_id = "voice-spec-order"
    voice_identity.begin(call_id)
    responses = [
        tool_call("verify_caller_by_order", {"order_number": "ORD-1", "last_name": "Smith"}, "verify-1"),
        tool_call("get_order", {"order_id": "order-1"}, "order-1"),
        AIMessage(content="Your order is confirmed and is being prepared."),
    ]
    with (
        patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "verified-user"}),
        patch("app.agentic.tools.core_tools.get_voice_order", return_value={"_id": "order-1", "orderNumber": "ORD-1"}) as get_order,
    ):
        result = run_voice_model(call_id, responses)

    assert result.message == "Your order is confirmed and is being prepared."
    get_order.assert_called_once_with("verified-user", "order-1")
    voice_identity.end(call_id)


def test_voice_spec_routes_shipment_question_to_tracking_tool() -> None:
    """A verified caller's shipment question invokes the voice tracking wrapper."""

    call_id = "voice-spec-shipment"
    voice_identity.begin(call_id)
    responses = [
        tool_call("verify_caller_by_order", {"order_number": "ORD-1", "postal_code": "10001"}, "verify-1"),
        tool_call("get_shipment_tracking", {"order_id": "order-1"}, "shipment-1"),
        AIMessage(content="Your package is in transit with the carrier."),
    ]
    with (
        patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "verified-user"}),
        patch("app.agentic.tools.core_tools.get_shipment_tracking", return_value={"status": "in_transit"}) as shipment,
    ):
        result = run_voice_model(call_id, responses)

    assert result.message == "Your package is in transit with the carrier."
    shipment.assert_called_once_with("verified-user", "order-1")
    voice_identity.end(call_id)


def test_voice_spec_checks_return_eligibility_before_proposing_return() -> None:
    """Return handling runs eligibility first, then creates one pending confirmation action."""

    call_id = "voice-spec-return"
    voice_identity.begin(call_id)
    action = {"_id": "return-action", "type": "create_return_request", "expiresAt": "2099-01-01T00:00:00Z", "payload": {"requiresDetails": False}}
    responses = [
        tool_call("verify_caller_by_order", {"order_number": "ORD-1", "last_name": "Smith"}, "verify-1"),
        tool_call("check_return_eligibility", {"order_id": "order-1", "order_item_id": "item-1"}, "eligibility-1"),
        tool_call(
            "request_create_return_confirmation",
            {"order_id": "order-1", "order_item_id": "item-1", "reason": "too small", "condition": "new", "resolution": "refund"},
            "return-1",
        ),
        AIMessage(content="Your return is eligible. Say yes to submit the return request."),
    ]
    with (
        patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "verified-user"}),
        patch("app.agentic.tools.core_tools.check_voice_return_eligibility", return_value={"eligible": True}) as eligibility,
        patch("app.agentic.tools.store.create_action", return_value=action) as create_action,
    ):
        result = run_voice_model(call_id, responses)

    assert result.pending_action == {"id": "return-action", "type": "create_return_request", "expiresAt": "2099-01-01T00:00:00Z"}
    eligibility.assert_called_once_with("verified-user", "order-1", "item-1")
    create_action.assert_called_once()
    assert create_action.call_args.args[2] == "create_return_request"
    voice_identity.end(call_id)


def test_voice_spec_proposes_one_cancellation_before_spoken_confirmation() -> None:
    """Cancellation is a single pending action; no Core mutation occurs during proposal."""

    call_id = "voice-spec-cancel"
    voice_identity.begin(call_id)
    action = {"_id": "cancel-action", "type": "update_order", "expiresAt": "2099-01-01T00:00:00Z", "payload": {}}
    responses = [
        tool_call("verify_caller_by_order", {"order_number": "ORD-1", "last_name": "Smith"}, "verify-1"),
        tool_call("request_update_order_confirmation", {"order_id": "order-1", "action": "cancel"}, "cancel-1"),
        AIMessage(content="I can cancel that order. Say yes to confirm."),
    ]
    with (
        patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "verified-user"}),
        patch("app.agentic.tools.store.create_action", return_value=action) as create_action,
        patch("app.agentic.tools.core_tools.update_voice_order") as update_order,
    ):
        result = run_voice_model(call_id, responses)

    assert result.pending_action == {"id": "cancel-action", "type": "update_order", "expiresAt": "2099-01-01T00:00:00Z"}
    create_action.assert_called_once()
    update_order.assert_not_called()
    voice_identity.end(call_id)


def test_voice_spec_proposes_ticket_for_unresolved_issue() -> None:
    """An unresolved request becomes a single pending support-ticket action for voice confirmation."""

    call_id = "voice-spec-escalation"
    voice_identity.begin(call_id)
    action = {"_id": "ticket-action", "type": "create_support_ticket", "expiresAt": "2099-01-01T00:00:00Z"}
    responses = [
        tool_call("verify_caller_by_order", {"order_number": "ORD-1", "last_name": "Smith"}, "verify-1"),
        tool_call(
            "request_create_support_ticket_confirmation",
            {"category": "unresolved", "priority": "high", "subject": "Voice escalation", "body": "Caller needs human assistance.", "order_id": "order-1"},
            "ticket-1",
        ),
        AIMessage(content="I can create a support ticket for a human agent. Say yes to confirm."),
    ]
    with (
        patch("app.voice.identity.core_tools.verify_caller_by_order", return_value={"verified": True, "userId": "verified-user"}),
        patch("app.agentic.tools.store.create_action", return_value=action) as create_action,
    ):
        result = run_voice_model(call_id, responses)

    assert result.pending_action == {"id": "ticket-action", "type": "create_support_ticket", "expiresAt": "2099-01-01T00:00:00Z"}
    create_action.assert_called_once()
    assert create_action.call_args.args[2] == "create_support_ticket"
    voice_identity.end(call_id)
