from tests.helpers.test_client import (
    ApiClient,
    create_placed_order,
    expect_activity,
    expect_error,
    expect_ok,
    first_product,
    register_and_login,
    unique_email,
)


def test_client_side_browse_activity_accepts_validated_events() -> None:
    client = ApiClient()
    product = first_product(client)
    events = [
        {
            "eventType": "search_performed",
            "metadata": {"query": "black running shoes", "searchMode": "semantic", "resultCount": 12},
        },
        {"eventType": "filter_applied", "metadata": {"filters": {"gender": ["Men"], "baseColour": ["Black"]}}},
        {"eventType": "sort_changed", "metadata": {"sort": "price_asc"}},
        {
            "eventType": "product_card_clicked",
            "metadata": {
                "productId": product["_id"],
                "sourceProductId": product["sourceProductId"],
                "origin": "catalogue_grid",
            },
        },
    ]

    for event in events:
        expect_ok(client.post("/api/activity-events", json=event), 201)
        expect_activity(event["eventType"])


def test_activity_capture_rejects_unknown_events_and_sensitive_metadata() -> None:
    client = ApiClient()
    expect_error(
        client.post("/api/activity-events", json={"eventType": "unknown_event", "metadata": {}}),
        400,
        "INVALID_ACTIVITY_EVENT",
    )
    expect_error(
        client.post(
            "/api/activity-events",
            json={"eventType": "search_performed", "metadata": {"query": "black shoes", "apiKey": "bad"}},
        ),
        400,
        "SENSITIVE_ACTIVITY_METADATA",
    )


def test_server_side_handlers_write_authoritative_activity_events() -> None:
    client, _ = register_and_login(unique_email("activity-authoritative"))
    product = first_product(client)
    item = expect_ok(
        client.post(
            "/api/cart/items",
            json={"productId": product["_id"], "quantity": 1, "size": "M"},
        ),
        201,
    )
    expect_activity("cart_item_added")

    expect_ok(client.patch(f"/api/cart/items/{item['cartItemId']}", json={"quantity": 2}))
    expect_activity("cart_item_updated")

    order = create_placed_order(client)
    expect_activity("checkout_started")
    expect_activity("order_placed")

    first_item = order["items"][0]
    expect_ok(
        client.post(
            "/api/returns",
            json={
                "orderId": order["_id"],
                "items": [
                    {
                        "orderItemId": first_item["orderItemId"],
                        "quantity": 1,
                        "reason": "Size issue",
                        "condition": "Unused",
                        "resolution": "refund",
                    }
                ],
            },
        ),
        201,
    )
    expect_activity("return_requested")

    expect_ok(
        client.post(
            "/api/support/tickets",
            json={
                "category": "returns",
                "priority": "normal",
                "subject": "Activity test support ticket",
                "body": "Please help with my return.",
                "orderId": order["_id"],
            },
        ),
        201,
    )
    expect_activity("support_ticket_created")

