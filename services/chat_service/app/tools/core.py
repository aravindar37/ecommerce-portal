"""Core Service backed ecommerce tools."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.http import ServiceHttpError, build_url, request_json, unwrap_envelope

Json = dict[str, Any]


class CoreTools:
    """Tool wrapper around Core Service APIs."""

    def headers(self, cookie_header: str | None = None, internal: bool = False, on_behalf_user_id: str | None = None) -> dict[str, str]:
        """Build Core request headers."""

        headers: dict[str, str] = {}
        if cookie_header:
            headers["cookie"] = cookie_header
        if internal and settings.chat_service_internal_token:
            headers["x-service-token"] = settings.chat_service_internal_token
        if on_behalf_user_id:
            headers["x-on-behalf-of-user-id"] = on_behalf_user_id
        return headers

    def voice_headers(self, user_id: str) -> dict[str, str]:
        """Build the authenticated server-to-server identity headers for voice."""

        return self.headers(internal=True, on_behalf_user_id=user_id)

    def get_cart(self, cookie_header: str) -> Json:
        """Return current Core cart."""

        return unwrap_envelope(request_json("GET", build_url(settings.core_service_base_url, "/api/cart"), headers=self.headers(cookie_header)))

    def add_to_cart(self, cookie_header: str, product_id: str, quantity: int, size: str | None) -> Json:
        """Add a product to the Core cart."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/cart/items"),
                payload={"productId": product_id, "quantity": quantity, "size": size},
                headers=self.headers(cookie_header),
            )
        )

    def update_cart_item(self, cookie_header: str, cart_item_id: str, quantity: int) -> Json:
        """Update a Core cart item."""

        return unwrap_envelope(
            request_json(
                "PATCH",
                build_url(settings.core_service_base_url, f"/api/cart/items/{cart_item_id}"),
                payload={"quantity": quantity},
                headers=self.headers(cookie_header),
            )
        )

    def remove_from_cart(self, cookie_header: str, cart_item_id: str) -> Json:
        """Remove a Core cart item."""

        return unwrap_envelope(
            request_json(
                "DELETE",
                build_url(settings.core_service_base_url, f"/api/cart/items/{cart_item_id}"),
                headers=self.headers(cookie_header),
            )
        )

    def get_user_preferences(self, cookie_header: str) -> Json:
        """Return current user's preference map."""

        user = unwrap_envelope(request_json("GET", build_url(settings.core_service_base_url, "/api/me"), headers=self.headers(cookie_header)))
        preferences = user.get("preferences") if isinstance(user, dict) else {}
        return preferences if isinstance(preferences, dict) else {}

    def save_user_preference(self, cookie_header: str, key: str, value: Any) -> Json:
        """Persist one user preference through Core."""

        return unwrap_envelope(
            request_json(
                "PATCH",
                build_url(settings.core_service_base_url, "/api/me/preferences"),
                payload={"key": key, "value": value},
                headers=self.headers(cookie_header),
            )
        )

    def list_user_orders(self, cookie_header: str) -> list[Json]:
        """Return the current user's orders."""

        data = unwrap_envelope(request_json("GET", build_url(settings.core_service_base_url, "/api/orders"), headers=self.headers(cookie_header)))
        items = data.get("items") if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def get_order(self, cookie_header: str, order_id: str) -> Json:
        """Return one owned order."""

        return unwrap_envelope(
            request_json("GET", build_url(settings.core_service_base_url, f"/api/orders/{order_id}"), headers=self.headers(cookie_header))
        )

    def get_voice_order(self, user_id: str, order_id: str) -> Json:
        """Fetch an order after voice hard verification established its owner."""

        return unwrap_envelope(
            request_json("GET", build_url(settings.core_service_base_url, f"/api/orders/{order_id}"), headers=self.voice_headers(user_id), timeout_seconds=10)
        )

    def list_voice_orders(self, user_id: str) -> list[Json]:
        """List orders belonging to one verified caller."""

        data = unwrap_envelope(request_json("GET", build_url(settings.core_service_base_url, "/api/orders"), headers=self.voice_headers(user_id), timeout_seconds=10))
        return [item for item in (data.get("items") if isinstance(data, dict) else []) if isinstance(item, dict)]

    def get_payment_details(self, user_id: str, order_id: str) -> Json:
        """Fetch compact, spoken-safe payment details for a verified caller."""

        return unwrap_envelope(
            request_json("GET", build_url(settings.core_service_base_url, f"/api/orders/{order_id}/payment"), headers=self.voice_headers(user_id), timeout_seconds=10)
        )

    def get_shipment_tracking(self, user_id: str, order_id: str) -> Json:
        """Return only the shipment subdocument for a verified caller's order."""

        order = self.get_voice_order(user_id, order_id)
        shipment = order.get("shipment") if isinstance(order, dict) else None
        if not isinstance(shipment, dict):
            raise ServiceHttpError(404, "Shipment tracking was not found")
        return shipment

    def update_voice_order(self, user_id: str, order_id: str, action: str, shipping_address: Json | None = None) -> Json:
        """Perform one constrained, previously confirmed voice order mutation."""

        payload: Json = {"action": action}
        if shipping_address is not None:
            payload["shippingAddress"] = shipping_address
        return unwrap_envelope(
            request_json("PATCH", build_url(settings.core_service_base_url, f"/api/orders/{order_id}"), payload=payload, headers=self.voice_headers(user_id), timeout_seconds=10, retry_safe=False)
        )

    def lookup_verified_user_by_phone(self, phone_number: str) -> Json | None:
        """Resolve a soft ANI hint without granting access to account data."""

        try:
            return unwrap_envelope(
                request_json(
                    "GET",
                    build_url(settings.core_service_base_url, "/api/internal/users/by-phone", {"phone": phone_number}),
                    headers=self.headers(internal=True),
                    timeout_seconds=10,
                )
            )
        except ServiceHttpError as exc:
            if exc.status_code == 404:
                return None
            raise

    def verify_caller_by_order(
        self,
        order_number: str,
        last_name: str | None = None,
        postal_code: str | None = None,
        caller_phone_number: str | None = None,
    ) -> Json:
        """Perform Core's generic hard verification before voice account access."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/internal/callers/verify"),
                payload={
                    "orderNumber": order_number,
                    "lastName": last_name,
                    "postalCode": postal_code,
                    "callerPhoneNumber": caller_phone_number,
                },
                headers=self.headers(internal=True),
                timeout_seconds=10,
                retry_safe=False,
            )
        )

    def get_order_item(self, cookie_header: str, order_id: str, order_item_id: str) -> Json:
        """Return one owned order item."""

        order = self.get_order(cookie_header, order_id)
        item = next((entry for entry in order.get("items", []) if entry.get("orderItemId") == order_item_id), None)
        if not isinstance(item, dict):
            raise ServiceHttpError(404, "Order item was not found")
        return item

    def check_return_eligibility(self, cookie_header: str, order_id: str, order_item_id: str) -> Json:
        """Check return eligibility through Core."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/returns/check-eligibility"),
                payload={"orderId": order_id, "orderItemId": order_item_id},
                headers=self.headers(cookie_header),
            )
        )

    def check_voice_return_eligibility(self, user_id: str, order_id: str, order_item_id: str) -> Json:
        """Check return eligibility as a previously verified voice caller."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/returns/check-eligibility"),
                payload={"orderId": order_id, "orderItemId": order_item_id},
                headers=self.voice_headers(user_id),
                timeout_seconds=10,
            )
        )

    def create_return_request(
        self,
        cookie_header: str,
        order_id: str,
        order_item_id: str,
        reason: str,
        condition: str,
        resolution: str,
    ) -> Json:
        """Create a return request after user confirmation."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/returns"),
                payload={
                    "orderId": order_id,
                    "items": [
                        {
                            "orderItemId": order_item_id,
                            "quantity": 1,
                            "reason": reason,
                            "condition": condition,
                            "resolution": resolution,
                        }
                    ],
                },
                headers=self.headers(cookie_header),
            )
        )

    def create_voice_return_request(
        self,
        user_id: str,
        order_id: str,
        order_item_id: str,
        reason: str,
        condition: str,
        resolution: str,
    ) -> Json:
        """Create a confirmed return as a verified voice caller."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/returns"),
                payload={"orderId": order_id, "items": [{"orderItemId": order_item_id, "quantity": 1, "reason": reason, "condition": condition, "resolution": resolution}]},
                headers=self.voice_headers(user_id),
                timeout_seconds=10,
                retry_safe=False,
            )
        )

    def create_support_ticket(self, cookie_header: str, category: str, priority: str, subject: str, body: str, order_id: str | None) -> Json:
        """Create a support ticket through Core."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/support/tickets"),
                payload={"category": category, "priority": priority, "subject": subject, "body": body, "orderId": order_id},
                headers=self.headers(cookie_header),
            )
        )

    def create_voice_support_ticket(self, user_id: str, category: str, priority: str, subject: str, body: str, order_id: str | None) -> Json:
        """Create an escalation ticket as a verified voice caller."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/support/tickets"),
                payload={"category": category, "priority": priority, "subject": subject, "body": body, "orderId": order_id},
                headers=self.voice_headers(user_id),
                timeout_seconds=10,
                retry_safe=False,
            )
        )

    def append_ticket_message(self, cookie_header: str, ticket_number: str, message: str) -> Json:
        """Append a support ticket message."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, f"/api/support/tickets/{ticket_number}/messages"),
                payload={"message": message},
                headers=self.headers(cookie_header),
            )
        )

    def write_activity(self, event_type: str, metadata: Json) -> Json:
        """Write activity event through Core."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/activity-events"),
                payload={"eventType": event_type, "metadata": metadata},
            )
        )

    def write_voice_activity(self, event_type: str, user_id: str, metadata: Json) -> Json:
        """Write a trusted server-side voice lifecycle event through Core."""

        return unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.core_service_base_url, "/api/internal/voice-activity-events"),
                payload={"eventType": event_type, "userId": user_id, "metadata": metadata},
                headers=self.headers(internal=True),
                timeout_seconds=10,
                retry_safe=False,
            )
        )

    def write_audit_log(self, payload: Json) -> Json | None:
        """Write an agent tool audit log through Core."""

        if not settings.chat_service_internal_token:
            return None
        try:
            return unwrap_envelope(
                request_json(
                    "POST",
                    build_url(settings.core_service_base_url, "/api/internal/agent-audit-logs"),
                    payload=payload,
                    headers=self.headers(internal=True),
                )
            )
        except ServiceHttpError:
            return None

    def get_return_policy(self) -> Json:
        """Return the demo return policy summary."""

        return {"policyCode": "standard-30-day", "windowDays": 30, "resolutions": ["refund", "exchange"]}


core_tools = CoreTools()
