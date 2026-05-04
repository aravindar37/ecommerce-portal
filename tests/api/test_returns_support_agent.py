from tests.helpers.test_client import (
    create_placed_order,
    expect_activity,
    expect_error,
    expect_ok,
    register_and_login,
    unique_email,
)


def test_return_eligibility_checks_policy_and_ownership() -> None:
    client, _ = register_and_login(unique_email("return-eligible"))
    order = create_placed_order(client)
    item = order["items"][0]

    eligibility = expect_ok(
        client.post(
            "/api/returns/check-eligibility",
            json={"orderId": order["_id"], "orderItemId": item["orderItemId"]},
        )
    )
    assert eligibility["eligible"] is True
    assert eligibility["policyCode"] == "standard-30-day"


def test_customer_can_create_return_request() -> None:
    client, _ = register_and_login(unique_email("return-create"))
    order = create_placed_order(client)
    item = order["items"][0]

    return_request = expect_ok(
        client.post(
            "/api/returns",
            json={
                "orderId": order["_id"],
                "items": [
                    {
                        "orderItemId": item["orderItemId"],
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
    assert return_request["returnNumber"].startswith("RET-")
    assert return_request["status"] == "requested"
    expect_activity("return_requested")


def test_return_creation_rejects_non_owner_order() -> None:
    owner, _ = register_and_login(unique_email("return-owner"))
    other, _ = register_and_login(unique_email("return-other"))
    order = create_placed_order(owner)
    item = order["items"][0]

    expect_error(
        other.post(
            "/api/returns",
            json={
                "orderId": order["_id"],
                "items": [
                    {
                        "orderItemId": item["orderItemId"],
                        "quantity": 1,
                        "reason": "Size issue",
                        "condition": "Unused",
                        "resolution": "refund",
                    }
                ],
            },
        ),
        404,
        "ORDER_NOT_FOUND",
    )


def test_support_tickets_can_be_created_and_messaged_by_owner() -> None:
    client, _ = register_and_login(unique_email("support-ticket"))
    order = create_placed_order(client)

    ticket = expect_ok(
        client.post(
            "/api/support/tickets",
            json={
                "category": "returns",
                "priority": "normal",
                "subject": "Need help with return",
                "body": "I need help returning this item.",
                "orderId": order["_id"],
            },
        ),
        201,
    )
    assert ticket["ticketNumber"].startswith("SUP-")
    assert ticket["status"] == "open"
    expect_activity("support_ticket_created")

    message = expect_ok(
        client.post(
            f"/api/support/tickets/{ticket['ticketNumber']}/messages",
            json={"message": "Can you confirm the return window?"},
        ),
        201,
    )
    assert message["senderType"] == "customer"

