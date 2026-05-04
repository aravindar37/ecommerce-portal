from tests.helpers.test_client import (
    admin_client,
    chat_client,
    create_placed_order,
    expect_activity,
    expect_ok,
    first_product,
    register_and_login,
    search_client,
    unique_email,
)


def test_health_check_requires_mandatory_local_codex_mcp_readiness() -> None:
    health = expect_ok(admin_client().get("/api/health"))
    assert health["mcp"]["enabled"] is True
    assert health["mcp"]["ready"] is True
    assert health["mcp"]["transport"]


def test_shopping_assistant_retrieves_products_and_proposes_confirmed_cart_action() -> None:
    client, _ = register_and_login(unique_email("shopping-agent"))
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/shopping/sessions", json={"entryPoint": "catalogue"}), 201)
    reply = expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "Find black casual shoes under 3000 and add the best one to my cart.",
                "context": {"cartAware": True},
            },
        )
    )

    assert isinstance(reply["suggestedProducts"], list)
    for product in reply["suggestedProducts"]:
        assert product.get("slug"), "suggestedProducts must include slug for product page links"
        assert product.get("sourceProductId"), "suggestedProducts must include sourceProductId"
    assert reply["pendingAction"]["type"] == "add_to_cart"
    assert "provider" not in reply

    confirmed = expect_ok(
        chat.post(
            "/api/assistant/actions/confirm",
            json={"actionId": reply["pendingAction"]["id"], "confirm": True},
        )
    )
    assert confirmed["status"] == "completed"
    expect_activity("assistant_product_recommended")
    expect_activity("cart_item_added")


def test_shopping_session_history_returns_messages_and_product_snapshots() -> None:
    client, _ = register_and_login(unique_email("shopping-history"))
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/shopping/sessions", json={"entryPoint": "catalogue"}), 201)
    reply = expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "Find casual shoes under 3000.",
                "context": {"cartAware": True},
            },
        )
    )
    assert reply["suggestedProducts"]

    latest = expect_ok(chat.get("/api/assistant/shopping/sessions"))
    assert latest["session"]["_id"] == session["_id"]
    assert latest["session"]["messageCount"] >= 2
    assert latest["session"]["summary"] == "Find casual shoes under 3000."

    history = expect_ok(chat.get("/api/assistant/shopping/sessions/history?limit=5"))
    assert any(item["_id"] == session["_id"] for item in history["items"])

    messages = expect_ok(chat.get(f"/api/assistant/shopping/sessions/{session['_id']}/messages?limit=20"))
    assert [item["role"] for item in messages["items"]] == ["user", "assistant"]
    assistant = messages["items"][1]
    assert assistant["metadata"]["suggestedProducts"]
    assert assistant["metadata"]["suggestedProducts"][0].get("slug")

    expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "Show me one more option.",
                "context": {"cartAware": True},
            },
        )
    )
    latest_after_follow_up = expect_ok(chat.get("/api/assistant/shopping/sessions"))
    assert latest_after_follow_up["session"]["summary"] == "Find casual shoes under 3000."
    assert latest_after_follow_up["session"]["messageCount"] >= 4


def test_shopping_assistant_answers_product_questions_using_product_facts() -> None:
    client, _ = register_and_login(unique_email("shopping-product-q"))
    product = first_product()
    chat = chat_client(client)
    session = expect_ok(
        chat.post(
            "/api/assistant/shopping/sessions",
            json={"entryPoint": "product_detail", "productId": product["_id"]},
        ),
        201,
    )
    reply = expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "What color and usage is this product best for?",
                "context": {"currentProductId": product["_id"]},
            },
        )
    )

    assert product["baseColour"].lower() in reply["message"].lower()
    assert product["usage"].lower() in reply["message"].lower()


def test_shopping_agent_handles_matching_products_request() -> None:
    client, _ = register_and_login(unique_email("shopping-matching"))
    product = first_product()
    chat = chat_client(client)
    session = expect_ok(
        chat.post(
            "/api/assistant/shopping/sessions",
            json={"entryPoint": "product_detail", "productId": product["_id"]},
        ),
        201,
    )
    reply = expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "Find shoes to match this item.",
                "context": {"currentProductId": product["_id"]},
            },
        )
    )

    assert reply["suggestedProducts"]
    assert any("shoe" in (item.get("articleType") or item.get("title") or "").lower() for item in reply["suggestedProducts"])


def test_shopping_agent_compares_two_products() -> None:
    client, _ = register_and_login(unique_email("shopping-compare"))
    products = expect_ok(search_client().get("/api/products?limit=2"))["items"]
    assert len(products) >= 2
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/shopping/sessions", json={"entryPoint": "catalogue"}), 201)
    reply = expect_ok(
        chat.post(
            "/api/assistant/shopping/messages",
            json={
                "sessionId": session["_id"],
                "message": "Compare these two products.",
                "context": {"productIds": [products[0]["_id"], products[1]["_id"]]},
            },
        )
    )

    assert len(reply["suggestedProducts"]) == 2
    assert "compare" in reply["message"].lower() or "compared" in reply["message"].lower()


def test_complex_support_chat_routes_through_local_codex_mcp() -> None:
    client, _ = register_and_login(unique_email("support-agent-mcp"))
    order = create_placed_order(client)
    item = order["items"][0]
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/support/sessions", json={"orderId": order["_id"]}), 201)
    reply = expect_ok(
        chat.post(
            "/api/assistant/support/messages",
            json={
                "sessionId": session["_id"],
                "message": (
                    "I want to return the first item, check whether it is eligible, "
                    "explain the policy, and prepare the return."
                ),
                "context": {"orderId": order["_id"], "orderItemId": item["orderItemId"]},
            },
        )
    )

    assert reply["usedMcp"] is True
    assert reply["pendingAction"]["type"] == "create_return_request"


def test_support_agent_can_find_order_without_explicit_ids() -> None:
    client, _ = register_and_login(unique_email("support-find-order"))
    create_placed_order(client)
    chat = chat_client(client)
    session = expect_ok(chat.post("/api/assistant/support/sessions", json={}), 201)
    reply = expect_ok(
        chat.post(
            "/api/assistant/support/messages",
            json={
                "sessionId": session["_id"],
                "message": "I want to return the first item from my latest order.",
                "context": {},
            },
        )
    )

    assert reply["usedMcp"] is True
    assert reply["pendingAction"]["type"] == "create_return_request"


def test_agent_tool_calls_are_audited() -> None:
    logs = expect_ok(admin_client().get("/api/admin/audit-logs?agentType=returns_support&limit=20"))
    assert logs["items"]
    assert all(log["sessionId"] for log in logs["items"])
    assert all(log["toolName"] for log in logs["items"])
    assert all(log["status"] in {"success", "error", "blocked"} for log in logs["items"])
