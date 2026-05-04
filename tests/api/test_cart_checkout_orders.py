from tests.helpers.test_client import (
    TEST_USER_PASSWORD,
    ApiClient,
    create_placed_order,
    demo_address,
    expect_activity,
    expect_error,
    expect_ok,
    first_product,
    register_and_login,
    unique_email,
)


def test_guest_cart_supports_add_update_remove_and_clear() -> None:
    client = ApiClient()
    product = first_product(client)
    item = expect_ok(
        client.post(
            "/api/cart/items",
            json={"productId": product["_id"], "quantity": 1, "size": "M"},
        ),
        201,
    )
    expect_activity("cart_item_added")

    updated = expect_ok(client.patch(f"/api/cart/items/{item['cartItemId']}", json={"quantity": 2}))
    assert updated["quantity"] == 2
    expect_activity("cart_item_updated")

    expect_ok(client.delete(f"/api/cart/items/{item['cartItemId']}"))
    expect_activity("cart_item_removed")
    expect_ok(client.delete("/api/cart"))


def test_checkout_requires_authentication() -> None:
    expect_error(
        ApiClient().post(
            "/api/checkout/place-order",
            json={"shippingAddress": demo_address(), "paymentMethod": "demo"},
        ),
        401,
        "UNAUTHENTICATED",
    )


def test_anonymous_cart_merges_into_authenticated_cart_after_login() -> None:
    client = ApiClient()
    product = first_product(client)
    expect_ok(
        client.post(
            "/api/cart/items",
            json={"productId": product["_id"], "quantity": 1, "size": "M"},
        ),
        201,
    )

    email = unique_email("cart-merge")
    expect_ok(
        client.post(
            "/api/auth/register",
            json={"email": email, "password": TEST_USER_PASSWORD, "name": "Cart Merge Test"},
        ),
        201,
    )
    expect_ok(client.post("/api/auth/login", json={"email": email, "password": TEST_USER_PASSWORD}))
    expect_ok(client.post("/api/cart/merge"))

    cart = expect_ok(client.get("/api/cart"))
    assert any(str(item["productId"]) == str(product["_id"]) for item in cart["items"])


def test_checkout_quote_and_place_order_recalculate_totals_in_inr() -> None:
    client, _ = register_and_login(unique_email("checkout"))
    product = first_product(client)
    expect_ok(
        client.post(
            "/api/cart/items",
            json={
                "productId": product["_id"],
                "quantity": 1,
                "size": "M",
                "price": {"amount": 1, "currency": "INR"},
            },
        ),
        201,
    )

    quote = expect_ok(
        client.post(
            "/api/checkout/quote",
            json={"shippingAddress": demo_address(), "clientTotals": {"grandTotal": 1}},
        )
    )
    assert quote["totals"]["grandTotal"] != 1
    assert quote["totals"]["currency"] == "INR"
    expect_activity("checkout_started")

    order = expect_ok(
        client.post(
            "/api/checkout/place-order",
            json={
                "shippingAddress": demo_address(),
                "paymentMethod": "demo",
                "clientTotals": {"grandTotal": 1},
            },
        ),
        201,
    )
    assert order["orderNumber"].startswith("ORD-")
    assert order["totals"]["currency"] == "INR"
    assert order["payment"]["provider"] == "demo"
    assert order["payment"]["status"] in {"authorized", "paid"}
    expect_activity("order_placed")


def test_order_history_and_detail_are_visible_only_to_owner() -> None:
    owner, _ = register_and_login(unique_email("order-owner"))
    other, _ = register_and_login(unique_email("order-other"))
    product = first_product(owner)
    expect_ok(
        owner.post(
            "/api/cart/items",
            json={"productId": product["_id"], "quantity": 1, "size": "M"},
        ),
        201,
    )
    order = expect_ok(
        owner.post(
            "/api/checkout/place-order",
            json={"shippingAddress": demo_address(), "paymentMethod": "demo"},
        ),
        201,
    )

    orders = expect_ok(owner.get("/api/orders"))
    assert any(item["orderNumber"] == order["orderNumber"] for item in orders["items"])
    expect_ok(owner.get(f"/api/orders/{order['orderNumber']}"))
    expect_error(other.get(f"/api/orders/{order['orderNumber']}"), 404, "ORDER_NOT_FOUND")


def test_order_detail_includes_all_fields_for_frontend() -> None:
    client, _ = register_and_login(unique_email("order-detail-shape"))
    order = create_placed_order(client)
    detail = expect_ok(client.get(f"/api/orders/{order['orderNumber']}"))

    assert detail["orderNumber"].startswith("ORD-")
    assert detail["status"] in {"confirmed", "placed", "paid"}
    assert detail.get("placedAt")
    assert detail.get("estimatedDeliveryAt")

    address = detail.get("shippingAddress") or {}
    for field in ["name", "line1", "city", "region", "postalCode", "country"]:
        assert field in address, f"shippingAddress missing {field}"

    payment = detail.get("payment") or {}
    assert payment.get("provider")
    assert payment.get("status")

    assert detail["items"]
    item = detail["items"][0]
    assert item.get("titleSnapshot")
    assert item.get("quantity") >= 1
    assert item.get("imageUrlSnapshot"), "imageUrlSnapshot should be a non-empty URL for seeded products"
    assert item.get("size")
    assert item.get("unitPrice", {}).get("amount") is not None
    assert item.get("unitPrice", {}).get("currency")
