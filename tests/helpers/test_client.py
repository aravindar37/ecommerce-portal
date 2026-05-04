from __future__ import annotations

import os
import time
import uuid
from typing import Any

import httpx

Json = dict[str, Any]

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")
CORE_SERVICE_BASE_URL = os.getenv("CORE_SERVICE_BASE_URL", "http://localhost:4000")
SEARCH_SERVICE_BASE_URL = os.getenv("SEARCH_SERVICE_BASE_URL", "http://localhost:4001")
CHAT_SERVICE_BASE_URL = os.getenv("CHAT_SERVICE_BASE_URL", "http://localhost:4002")
TEST_ADMIN_TOKEN = os.getenv("TEST_ADMIN_TOKEN", "")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "Passw0rd!ForTests")


class ApiClient:
    def __init__(
        self,
        base_url: str = CORE_SERVICE_BASE_URL,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.client = httpx.Client(
            base_url=base_url,
            headers={"accept": "application/json", **(headers or {})},
            follow_redirects=False,
            timeout=30,
        )

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.client.get(path, **kwargs)

    def post(self, path: str, json: Any | None = None, **kwargs: Any) -> httpx.Response:
        return self.client.post(path, json=json, **kwargs)

    def patch(self, path: str, json: Any | None = None, **kwargs: Any) -> httpx.Response:
        return self.client.patch(path, json=json, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.client.delete(path, **kwargs)


def admin_client() -> ApiClient:
    assert TEST_ADMIN_TOKEN, "TEST_ADMIN_TOKEN is required for admin/test endpoints"
    return ApiClient(headers={"authorization": f"Bearer {TEST_ADMIN_TOKEN}"})


def core_client() -> ApiClient:
    return ApiClient(CORE_SERVICE_BASE_URL)


def search_client() -> ApiClient:
    return ApiClient(SEARCH_SERVICE_BASE_URL)


def chat_client(session_client: ApiClient | None = None) -> ApiClient:
    client = ApiClient(CHAT_SERVICE_BASE_URL)
    if session_client is not None:
        client.client.cookies.update(session_client.client.cookies)
    return client


def expect_ok(response: httpx.Response, status_code: int = 200) -> Any:
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert payload["error"] is None, payload
    assert payload["data"] is not None, payload
    return payload["data"]


def expect_error(
    response: httpx.Response,
    status_code: int,
    code: str | None = None,
) -> Json:
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert payload["error"], payload
    if code:
        assert payload["error"]["code"] == code
    return payload["error"]


def response_meta(response: httpx.Response) -> Json:
    return response.json().get("meta") or {}


def unique_email(prefix: str = "codex-demo") -> str:
    return f"{prefix}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}@example.test"


def reset_and_seed() -> None:
    client = admin_client()
    expect_ok(client.post("/api/test/reset"))
    expect_ok(
        client.post(
            "/api/test/seed",
            json={
                "products": "fashion-minimal",
                "users": True,
                "orders": True,
                "embeddings": True,
            },
        )
    )


def register_and_login(email: str | None = None) -> tuple[ApiClient, str]:
    client = ApiClient()
    email = email or unique_email()
    expect_ok(
        client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": TEST_USER_PASSWORD,
                "name": "Codex Test Shopper",
            },
        ),
        201,
    )
    expect_ok(
        client.post(
            "/api/auth/login",
            json={"email": email, "password": TEST_USER_PASSWORD},
        )
    )
    return client, email


def first_product(client: ApiClient | None = None) -> Json:
    client = client or search_client()
    data = expect_ok(client.get("/api/products?limit=1"))
    assert data["items"], "seeded catalogue must contain at least one product"
    return data["items"][0]


def demo_address() -> Json:
    return {
        "name": "Codex Test Shopper",
        "line1": "1 Demo Street",
        "line2": "",
        "city": "Bengaluru",
        "region": "KA",
        "postalCode": "560001",
        "country": "IN",
        "phone": "+919999999999",
    }


def create_placed_order(client: ApiClient) -> Json:
    product = first_product(client)
    expect_ok(
        client.post(
            "/api/cart/items",
            json={"productId": product["_id"], "quantity": 1, "size": "M"},
        ),
        201,
    )
    expect_ok(client.post("/api/checkout/quote", json={"shippingAddress": demo_address()}))
    return expect_ok(
        client.post(
            "/api/checkout/place-order",
            json={"shippingAddress": demo_address(), "paymentMethod": "demo"},
        ),
        201,
    )


def expect_activity(event_type: str) -> None:
    data = expect_ok(
        admin_client().get(
            "/api/admin/activity-events",
            params={"eventType": event_type, "limit": 20},
        )
    )
    assert data["items"], f"expected at least one {event_type} activity event"
