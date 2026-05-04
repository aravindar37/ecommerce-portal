# Test Summary

Run timestamp: 2026-05-03 13:40:06 IST

## Environment

- Repo: `/Users/aravind.ar/POC/codex_ecommerce_demo`
- Core Service: `http://127.0.0.1:4000`
- Search Service: `http://127.0.0.1:4001`
- Chat Service: `http://127.0.0.1:4002`
- Web App: `http://127.0.0.1:3000`
- Python: project `.venv`
- Browser: Playwright Chromium

## Results

| Suite | Command | Result |
| --- | --- | --- |
| Core Python compile | `PYTHONPATH=services/core_service .venv/bin/python3 -m py_compile $(find services/core_service/app -name '*.py' -print)` | Passed |
| Search Python compile | `PYTHONPATH=services/search_service .venv/bin/python3 -m py_compile $(find services/search_service/app -name '*.py' -print)` | Passed |
| Frontend typecheck | `npm --prefix apps/web run typecheck` | Passed |
| Frontend production build | `npm --prefix apps/web run build` | Passed |
| API contracts | `.venv/bin/python3 -m pytest tests/api -q` | Passed: 35 passed |
| Browser E2E | `apps/web/node_modules/.bin/playwright test tests/e2e --workers=1` | Passed: 6 passed |

## Fixes Implemented

- Fixed Core auth rate limiting to count only failed login responses, matching the spec requirement for failed login throttling without rate-limiting registration tests.
- Fixed Core product lookup and Search read-model fallback so cart and chat actions can resolve seeded/local products even when Atlas is unavailable or slow.
- Added a Search Atlas circuit-breaker fallback to avoid repeated DNS/timeouts from slowing local tests.
- Made web registration reliable by adding a server-side register-login-merge route that redirects only after session cookies are set.
- Improved frontend error handling for API/network failures in catalogue, product detail, cart checkout, shopping assistant, and support flows.
- Fixed support-agent timing by fetching orders during submit if the initial order load has not completed.
- Reduced brittle accessible-name collisions in the UI while preserving accessible commands for product detail, add-to-cart, checkout, assistant, and admin flows.
- Fixed a production build issue by passing auth page query errors from server page props instead of using `useSearchParams()` in the client form.

## Test Alignment Notes

- The failed API tests were aligned with the spec and exposed real implementation issues: failed-login rate limiting was too broad, and chat/cart product identifiers could diverge from Core product lookup.
- The E2E journeys were aligned with the spec, but several selectors were overly broad for a fashion ecommerce UI with repeated product cards. Examples: `/men/i` can match product titles and "Women"; `/add to cart/i` can match every product card; `/activity|funnel/i` can match copy and headings. I adjusted the UI labels and state visibility to make the app more accessible and deterministic without weakening the feature coverage.
- One transient rerun failure after `next build` was caused by the already-running Next dev server serving stale `.next` chunks. Restarting services with `./scripts/start_all.sh` resolved it; the final E2E run passed.
