# Ecommerce Demo Test Suite

This folder contains the acceptance, API contract, and browser E2E tests derived from `ecommerce-demo-spec.md`.

The application is not implemented in this repository yet, so these tests define the expected behavior the implementation should satisfy. They are intentionally written around public routes and API contracts from the spec.

## Test Layers

- `api/test_*.py`: pytest + httpx API contract tests for the three Python FastAPI services covering auth, catalogue, search, cart, checkout, agents, MCP readiness, activity capture, returns, support, ingestion, and provider config.
- `e2e/*.spec.ts`: Playwright browser tests for critical user journeys.
- `helpers/test_client.py`: Shared Python HTTP client, session cookie handling, assertions, and test data helpers.
- `fixtures/test-env.example.env`: Required environment variables for running the suite.

## Expected Commands

Once the application has a Python backend and frontend package setup, wire these commands into the repo scripts:

```bash
pytest tests/api
npx playwright test tests/e2e --workers=1
```

Recommended combined commands:

- Service/API: `pytest tests/api`
- Frontend E2E: `npx playwright test tests/e2e --workers=1`

## Required Environment

```bash
APP_BASE_URL=http://localhost:3000
CORE_SERVICE_BASE_URL=http://localhost:4000
SEARCH_SERVICE_BASE_URL=http://localhost:4001
CHAT_SERVICE_BASE_URL=http://localhost:4002
TEST_ADMIN_TOKEN=dev-admin-token
TEST_USER_PASSWORD=Passw0rd!ForTests
TEST_GOOGLE_OAUTH_ENABLED=false
```

See `fixtures/test-env.example.env` for the full list.

Run the suite serially because the test setup resets and reseeds the shared demo database.

## Test-Only Support Endpoints

The spec defines admin console requirements but not every admin API path. These tests assume the implementation exposes restricted admin/test endpoints protected by `TEST_ADMIN_TOKEN`:

- `GET {CORE_SERVICE_BASE_URL}/api/health`
- `GET {SEARCH_SERVICE_BASE_URL}/api/health`
- `GET {CHAT_SERVICE_BASE_URL}/api/health`
- `GET {CORE_SERVICE_BASE_URL}/api/admin/config`
- `GET {CORE_SERVICE_BASE_URL}/api/admin/ingestion/status`
- `GET {CORE_SERVICE_BASE_URL}/api/admin/activity-events`
- `GET {CORE_SERVICE_BASE_URL}/api/admin/audit-logs`
- `POST {CORE_SERVICE_BASE_URL}/api/test/reset`
- `POST {CORE_SERVICE_BASE_URL}/api/test/seed`

These endpoints should be disabled or separately protected outside demo/test environments.

The suite also expects a public `POST /api/activity-events` endpoint for validated client-side browse events such as filter changes, sort changes, and product-card clicks. Authoritative events such as orders, returns, tickets, and cart mutations should be written by the server-side handlers that perform those actions.
