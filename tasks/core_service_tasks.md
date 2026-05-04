# Core Service Task List

Scope: `services/core_service`

Core Service owns account creation and login, users, sessions, carts, checkout, orders, returns, support tickets, product ingestion, product records, local product images, user activity events, admin/test endpoints, and service health/config APIs.

## Foundation

- [x] Create the FastAPI app structure under `services/core_service/app` with routers for `api`, `auth`, `carts`, `checkout`, `ingestion`, `orders`, `products`, `returns`, `support`, and admin/test endpoints.
  - Validation: `PYTHONPATH=services/core_service python3 -m py_compile $(find services/core_service/app -name '*.py' -print)`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

- [x] Implement shared Core config loading from `.env.example` variables, with typed Pydantic settings and no hardcoded secrets.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_admin_config_exposes_provider_choices_without_secrets`

- [x] Implement MongoDB Atlas connection management, collection helpers, indexes, startup checks, request IDs, error envelopes, and service health metadata.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_all_three_fastapi_services_report_health`

- [x] Implement restricted test/admin support endpoints: `POST /api/test/reset`, `POST /api/test/seed`, `GET /api/admin/config`, `GET /api/admin/ingestion/status`, `GET /api/admin/activity-events`, and `GET /api/admin/audit-logs`.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py`

## Product Ingestion and Product Records

- [x] Implement local dataset ingestion from `./dataset`, including `styles.csv`, `images.csv`, `styles/<id>.json`, local images, normalized product JSONL output, and ingestion report generation.
  - Validation: `./scripts/ingest_products.sh --limit 10`

- [x] Persist normalized products into MongoDB Atlas `products` collection with unique `source/sourceProductId`, slug, filter indexes, image metadata, JSON-derived price/brand/description, deterministic inventory/ratings/tags, and return policy hints.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_ingestion_status_reports_kaggle_dataset_local_filesystem_and_embeddings`
  - Validation: `pytest tests/api/test_catalog_search_activity.py::test_catalogue_lists_active_products_with_dataset_and_ecommerce_fields`

- [x] Serve local product images from `PRODUCT_IMAGE_LOCAL_ROOT` through a Core Service image route and provide fallback behavior for missing image IDs.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_ingestion_status_reports_kaggle_dataset_local_filesystem_and_embeddings`

## Authentication and Identity

- [x] Implement password registration, duplicate-email handling, secure password hashing, and safe user response bodies.
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_email_password_registration_creates_safe_identity`
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_duplicate_email_registration_is_rejected`

- [x] Implement email/password login, secure HTTP-only session cookies, session hashing/persistence, `/api/me`, and logout.
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_login_accepts_valid_credentials_and_me_returns_current_user`
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_invalid_login_is_rejected_and_does_not_create_session`
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_logout_invalidates_active_session`

- [x] Implement local-development Google OAuth disabled behavior and shared-demo OAuth callback support.
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_google_oauth_is_disabled_for_local_development`

- [x] Implement password reset request/confirm safe-response semantics and account-linking-ready schema.
  - Validation: `pytest tests/api/test_auth_and_identity.py::test_password_reset_request_uses_safe_response_semantics`

- [x] Seed a separate admin user for support/admin console access.
  - Validation: `pytest tests/api/test_provider_config_ingestion.py::test_admin_config_exposes_provider_choices_without_secrets`

## Cart, Checkout, and Orders

- [x] Implement anonymous carts, authenticated carts, add/update/remove/clear item operations, server-side cart totals, and cart activity events.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_guest_cart_supports_add_update_remove_and_clear`

- [x] Implement anonymous-to-authenticated cart merge after login.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_anonymous_cart_merges_into_authenticated_cart_after_login`

- [x] Enforce authenticated checkout and reject unauthenticated order placement.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_checkout_requires_authentication`

- [x] Implement checkout quote and demo order placement with server-side INR totals, demo payment status, order numbers, inventory checks, and order activity events.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_checkout_quote_and_place_order_recalculate_totals_in_inr`

- [x] Implement user order list/detail APIs with ownership checks.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_order_history_and_detail_are_visible_only_to_owner`

## Returns and Support

- [x] Implement return policy engine, order-item eligibility checks, and ownership validation.
  - Validation: `pytest tests/api/test_returns_support_agent.py::test_return_eligibility_checks_policy_and_ownership`

- [x] Implement return request creation with statuses, reason, condition, resolution, and activity events.
  - Validation: `pytest tests/api/test_returns_support_agent.py::test_customer_can_create_return_request`
  - Validation: `pytest tests/api/test_returns_support_agent.py::test_return_creation_rejects_non_owner_order`

- [x] Implement support ticket creation, ticket messages, ownership checks, priority/category/status fields, and support activity events.
  - Validation: `pytest tests/api/test_returns_support_agent.py::test_support_tickets_can_be_created_and_messaged_by_owner`

## User Activity and Audit Data

- [x] Implement public validated `POST /api/activity-events` for client-side browse events and reject unknown/sensitive metadata.
  - Validation: `pytest tests/api/test_user_activity_events.py::test_client_side_browse_activity_accepts_validated_events`
  - Validation: `pytest tests/api/test_user_activity_events.py::test_activity_capture_rejects_unknown_events_and_sensitive_metadata`

- [x] Write authoritative server-side events for cart mutations, checkout starts, orders, returns, and support tickets.
  - Validation: `pytest tests/api/test_user_activity_events.py::test_server_side_handlers_write_authoritative_activity_events`

- [x] Expose admin activity-event and agent-audit-log read APIs used by tests and admin console, redacting secrets.
  - Validation: `pytest tests/api/test_ai_agents_mcp.py::test_agent_tool_calls_are_audited`
  - Validation: `pytest tests/api/test_provider_config_ingestion.py`

## Order Detail Response — Frontend Support (Feature A)

These tasks ensure the `GET /api/orders/{orderNumber}` response includes every field required by the new order detail page. The data is already stored; tasks cover verification, a response-shape test, and two data-quality fixes.

- [x] Verify `GET /api/orders/{orderNumber}` response includes all fields required by the order detail page: `status`, `placedAt`, `estimatedDeliveryAt`, `shippingAddress`, `payment`, and per-item `imageUrlSnapshot`, `size`, `unitPrice`.

  **How to verify:**
  ```bash
  # Start Core Service, seed data, place one order, then inspect:
  python3 - <<'PY'
  import httpx, json, os
  base = os.getenv("CORE_SERVICE_BASE_URL", "http://localhost:4000")
  token = os.getenv("TEST_ADMIN_TOKEN", "")
  httpx.post(f"{base}/api/test/reset", headers={"authorization": f"Bearer {token}"})
  httpx.post(f"{base}/api/test/seed", headers={"authorization": f"Bearer {token}"},
             json={"products": "fashion-minimal", "users": True, "orders": True})
  r = httpx.get(f"{base}/api/orders", cookies={"core_session": "<token>"})
  order = r.json()["data"]["items"][0]
  print(json.dumps(order, indent=2, default=str))
  PY
  ```
  Confirm the response contains all required top-level and nested fields.

- [x] Add a pytest test that asserts the order detail response shape.

  **File:** `tests/api/test_cart_checkout_orders.py`

  Add the following test after `test_order_history_and_detail_are_visible_only_to_owner`:
  ```python
  def test_order_detail_includes_all_fields_for_frontend() -> None:
      client, _ = register_and_login(unique_email("order-detail-shape"))
      order = create_placed_order(client)
      detail = expect_ok(client.get(f"/api/orders/{order['orderNumber']}"))

      # Top-level fields
      assert detail["orderNumber"].startswith("ORD-")
      assert detail["status"] in {"confirmed", "placed", "paid"}
      assert detail.get("placedAt")
      assert detail.get("estimatedDeliveryAt")

      # Shipping address
      addr = detail.get("shippingAddress") or {}
      for field in ["name", "line1", "city", "region", "postalCode", "country"]:
          assert field in addr, f"shippingAddress missing {field}"

      # Payment
      payment = detail.get("payment") or {}
      assert payment.get("provider")
      assert payment.get("status")

      # Items
      assert detail["items"]
      item = detail["items"][0]
      assert item.get("titleSnapshot")
      assert item.get("quantity") >= 1
      assert item.get("unitPrice", {}).get("amount") is not None
      assert item.get("unitPrice", {}).get("currency")
  ```

  **Validation:**
  ```bash
  pytest tests/api/test_cart_checkout_orders.py::test_order_detail_includes_all_fields_for_frontend
  ```

- [x] Fix `imageUrlSnapshot` on order items to use the product's public image URL, not an internal path.

  **File:** `services/core_service/app/store.py`

  In `place_order()`, order items are built with:
  ```python
  "imageUrlSnapshot": (self.find_product(item["productId"]) or {"images": [{"url": ""}]})["images"][0]["url"],
  ```
  This stores the raw image URL from the product document (e.g., `/product-images/15970.jpg`). This is the correct public path. Verify it is non-empty for seeded products by logging or asserting during the order detail test:
  ```python
  # In the test above, after the items block:
  assert item.get("imageUrlSnapshot"), "imageUrlSnapshot should be a non-empty URL for seeded products"
  ```
  If `imageUrlSnapshot` is empty for any seeded product, trace back to `seed_products()` and verify that the product document's first image URL is set correctly before order placement.

  **Validation:**
  ```bash
  pytest tests/api/test_cart_checkout_orders.py::test_order_detail_includes_all_fields_for_frontend -v
  ```

- [x] Add `tags` and `ratingAverage`/`ratingCount` to the Search Service product response so the catalogue can display them.

  **Context:** Product documents in the backend store include `tags`, `ratingAverage`, and `ratingCount`. The Search Service's `atlas_products()` and local fallbacks return the raw document, so these fields should already be present in `GET /api/products` responses. Verify they appear:

  ```bash
  curl -s "http://localhost:4001/api/products?limit=1" | python3 -m json.tool | grep -E "tags|rating"
  ```

  If missing, check `ProductsClient` in Search Service and confirm these fields are not stripped during normalization. No code change should be required — this is a verification gate.

  **Validation:**
  ```bash
  pytest tests/api/test_catalog_search_activity.py::test_catalogue_lists_active_products_with_dataset_and_ecommerce_fields -v
  ```
  Add `"tags"` and `"ratingAverage"` to the field assertions in that test if not already present.

---

## Core Service Completion Gates

- [x] Core-only API gate passes.
  - Validation: `pytest tests/api/test_auth_and_identity.py tests/api/test_cart_checkout_orders.py tests/api/test_returns_support_agent.py tests/api/test_user_activity_events.py`

- [x] Order detail response-shape test passes.
  - Validation: `pytest tests/api/test_cart_checkout_orders.py::test_order_detail_includes_all_fields_for_frontend`

- [x] Cross-service API gate passes with Search and Chat running.
  - Validation: `pytest tests/api`

- [x] Browser critical flows involving Core Service pass after frontend is implemented.
  - Validation: `npx playwright test tests/e2e --workers=1`
