# UX Design Review

**Scope:** `apps/web/` — Next.js frontend, component design, navigation, layout, visual style  
**Requirements evaluated:**
1. Guest nav = product search + Sign In only
2. Unauthenticated add-to-cart → redirect to login
3. Logged-in nav = Catalogue · Account · Orders (+ Admin Dashboard for admins)
4. Filters on the left side of the page
5. Style review — page should dazzle

---

## 1. Navigation — Critical Gaps

### 1.1 Guests see the full nav bar — violates the stated requirement
**File:** `apps/web/components/HeaderNav.tsx:20-33`

Current output for an unauthenticated visitor:
```
Catalogue  |  Bag (0)  |  Support  |  Account orders  |  Admin  |  Sign in  |  Join
```

Required output:
```
Catalogue  |  Sign In
```

Bag, Support, Account orders, and Admin should all be hidden from guests. The Admin link is visible to every visitor including anonymous users, which is both a UX and a security concern.

**Fix:** Conditionally render nav items based on `user` state. Until `user` resolves from `/api/me`, render only Catalogue and Sign In.

### 1.2 Admin Dashboard is not role-gated — shown to all users
**File:** `apps/web/components/HeaderNav.tsx:25`, `apps/web/lib/types.ts:86-90`

The `User` type has no `roles` field:
```typescript
export interface User {
  _id: string;
  email: string;
  name: string;
}
```
The nav always renders `<Link href="/admin">Admin</Link>` unconditionally. The `GET /api/core/me` endpoint does return a `roles` array on the user document. The `User` type must include `roles: string[]` and the nav must only show Admin Dashboard when `user.roles.includes("admin")`.

### 1.3 Logged-in nav structure does not match the requirement
**File:** `apps/web/components/HeaderNav.tsx:21-27`

Current logged-in nav:
```
Catalogue | Bag (n) | Support | Account orders | Admin | Aravind Kumar
```

Required logged-in nav:
```
Catalogue | Account | Orders | Admin Dashboard (admins only)
```

Specific gaps:
- **Account** link to `/account` is missing entirely; user profile and preferences are unreachable
- The link says "Account orders" — it should be "Orders"
- The logged-in user's name is a `<span>`, not a link or dropdown — no way to reach profile settings
- **Sign out** is absent; users cannot end their session from the UI

### 1.4 No sign-out action anywhere in the application
No component calls `POST /api/core/auth/logout`. Once logged in, the session persists until the 7-day cookie expires. A sign-out option must be added — either as a nav item for logged-in users or as a button on the Account page.

### 1.5 "Join" is an ambiguous label for registration
**File:** `apps/web/components/HeaderNav.tsx:31`
The registration link reads "Join". Standard conventions for fashion retail are "Sign up", "Create account", or "Register". "Join" reads as a membership program, not an account creation action.

---

## 2. Unauthenticated Add-to-Cart — Not Redirected to Login

### 2.1 Guests who click "Add item" see a raw error code instead of a login prompt
**File:** `apps/web/components/ProductsClient.tsx:146-157`, `apps/web/components/ProductDetailClient.tsx:33-39`

When a guest clicks "Add item", `apiFetch()` receives a 401 from Core Service and throws `ApiError("UNAUTHENTICATED", ...)`. The error is caught and rendered as inline status text:
```typescript
setError(caught instanceof Error ? caught.message : "Unable to add item to cart");
```
The user sees the word "UNAUTHENTICATED" on the page — not a redirect, not a helpful message, not a call to action. The required behavior is:
```typescript
if (caught instanceof ApiError && caught.status === 401) {
  window.location.assign("/login");
  return;
}
```
`ApiError` already carries a `status` field (added in `lib/api.ts`), so this fix is straightforward.

### 2.2 Same issue in the ProductDetail add-to-cart path
**File:** `apps/web/components/ProductDetailClient.tsx:33-39`

`addToCart()` in the detail page also sets the error string on a 401. Same redirect fix applies.

---

## 3. Filter Layout — Horizontal Bar Instead of Left Sidebar

### 3.1 Filters are a collapsible horizontal panel above the product grid
**File:** `apps/web/components/ProductsClient.tsx:182-202`, `apps/web/app/globals.css:350-377`

Current layout:
```
[Search toolbar: search field | Filter button | Semantic search button]
[Filter bar: flex-wrap row of dropdowns — only when filterOpen=true]
[Results status bar]
[Product grid — full width, 4 columns]
```

Required layout:
```
[Search toolbar: search field | Semantic search button]
[Left filter sidebar (240px, always visible) | Product grid]
```

The current `.filters` class uses `display: flex; flex-wrap: wrap` — a horizontal row below the search bar that appears only when the "Filter" button is clicked. Filters should be in a left sidebar that is always visible.

**Required CSS additions:**
```css
.catalogue-layout {
  display: grid;
  grid-template-columns: 240px 1fr;
  gap: 32px;
  align-items: start;
}
.filter-sidebar {
  position: sticky;
  top: 80px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
  padding: 20px;
  display: grid;
  gap: 20px;
}
@media (max-width: 760px) {
  .catalogue-layout { grid-template-columns: 1fr; }
  .filter-sidebar { position: static; }
}
```

**Required component change:** Remove the `filterOpen` toggle state and the "Filter" button. The filter sidebar renders unconditionally alongside the product grid.

### 3.2 Mobile: left sidebar must collapse to an off-canvas drawer
On screens ≤ 760px, the filter sidebar should collapse to an off-canvas slide-in panel triggered by a floating "Filter" button. Simply stacking it above the grid on mobile reduces the above-the-fold product count to zero.

### 3.3 Filter dropdowns silently truncate at 24 options
**File:** `apps/web/components/ProductsClient.tsx:244`
```typescript
{values.slice(0, 24).map(...)}
```
For facets with many values (e.g., Article type has 50+ types across 44K products), options beyond 24 are hidden with no disclosure. In a sidebar layout with a scrollable section per facet group, this truncation is unnecessary.

---

## 4. Style Review — What Works

The design system has a strong, coherent foundation worth keeping:

- **Palette** — Warm terra-cotta (`#b6534a`) on cream (`#fbf8f5`) is on-trend for fashion editorial and wellness. It reads as considered rather than generic.
- **Typography** — Georgia serif for display headings + Inter sans-serif for body is a classic editorial pairing. The `clamp(2.2rem, 4.5vw, 4.4rem)` scaling on the page title is responsive and shows craft.
- **Product cards** — Lift on hover (`translateY(-3px)`) + shadow growth + image scale (`scale(1.035)`) is a polished micro-interaction trifecta.
- **Size chips** — Pill-shaped, toggleable, using `aria-pressed` — both accessible and visually clean.
- **Sticky topbar** — `backdrop-filter: blur(12px)` with a semi-transparent background is a contemporary detail that reads as premium.
- **Focus rings** — Amber `rgba(209, 139, 95, 0.36)` focus outline is on-brand and visible without being harsh.
- **Button behaviour** — `translateY(-1px)` on hover is subtle and premium-feeling. The disabled state at `opacity: 0.55` is correct.
- **Overall system** — CSS custom properties are well-named, covering the full range of ink, muted, surface, line, and accent states without any magic numbers scattered through the components.

---

## 5. Style Review — What Needs Work

### 5.1 Home page has no product imagery — the first impression is entirely textual
**File:** `apps/web/app/page.tsx`

The hero section shows a heading, one paragraph, a CTA link, and three text-only description panels. There is no photograph, illustration, or product showcase. Fashion retail lives and dies by visual impact. A full-bleed editorial hero image behind the headline, or a curated product grid showing the top arrivals, would transform the landing page from a developer placeholder into a shopping destination.

**Recommendation:** Add a hero image route that lazy-loads a featured product image, or use a `background-image` hero with a dark overlay and white headline text. The `--band` background alone is not enough.

### 5.2 Loading state is a blank grid with a text line — feels broken
**File:** `apps/web/components/ProductsClient.tsx:55-56`

When `loading = true`, the product grid is empty. Users see nothing for up to several hundred milliseconds. A skeleton grid (12 placeholder cards with shimmer animation) communicates progress and eliminates the perception of a broken page.

```css
.skeleton-card {
  background: linear-gradient(90deg, var(--line) 25%, var(--band) 50%, var(--line) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  border-radius: 14px;
  height: 360px;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
```

### 5.3 Product cards don't show ratings — a core trust signal is absent
**File:** `apps/web/components/ProductCard.tsx`

Products have `ratingAverage` and `ratingCount` in the backend, but the `Product` TypeScript type doesn't include these fields and neither does the product card. Ratings are one of the strongest purchase-decision signals in fashion ecommerce. Adding `★ 4.2 (128)` below the price requires:
1. Adding `ratingAverage?: number` and `ratingCount?: number` to the `Product` interface in `types.ts`
2. Rendering five pip-stars or a single numeric rating in the card body

### 5.4 Cart items show no product image — the cart reads as a plain invoice
**File:** `apps/web/components/CartClient.tsx:31-36`

Fashion cart UX almost universally shows a product thumbnail alongside each item. The cart schema in the backend stores only `titleSnapshot` and `priceSnapshot`, not an image URL. The fix requires:
1. Adding `imageUrlSnapshot: string` to the cart item in the backend `store.py`
2. Storing the item image when adding to cart
3. Adding `imageUrlSnapshot?: string` to the `CartItem` type in `types.ts`
4. Rendering the thumbnail in `CartClient`

### 5.5 No toast notification system — cart success feedback is easy to miss
**File:** `apps/web/components/ProductsClient.tsx:152-153`

`setStatus("Added to cart")` updates a small text element in the results bar positioned far from the "Add item" button that was clicked. There is no animation, no transience, and no visual connection to the action. A corner toast notification that appears, holds for 2 seconds, and slides out is the expected pattern:

```typescript
// Simple toast: append to a fixed overlay, auto-remove after 2s
function showToast(message: string) {
  // Append a div to document.body, remove after 2000ms
}
```

### 5.6 Register form is broken — submits to a non-existent route
**File:** `apps/web/components/AuthForms.tsx:47-50`

```tsx
action={mode === "register" ? "/api/auth/register-session" : undefined}
method={mode === "register" ? "post" : undefined}
onSubmit={mode === "login" ? (event) => void submit(event) : undefined}
```

When `mode === "register"`, `onSubmit` is `undefined` and the form submits natively to `/api/auth/register-session`. That route does not exist in the Next.js app. Registering a new account will result in a 404. The client-side `submit()` handler must be active for both modes, or a Route Handler must be created at `app/api/auth/register-session/route.ts`.

### 5.7 Colour palette is warm but not visually bold — it reads as pleasant rather than dazzling
**File:** `apps/web/app/globals.css:1-16`

Current accent colours:
- `--accent: #b6534a` (muted terra-cotta)
- `--accent-strong: #8e3c35` (dark rust)
- `--paper: #fbf8f5` (warm off-white)

Recommendations to add drama without losing the brand identity:
- **Hero section:** Near-black background (`#140d0a` or deep navy `#0f1c2e`) behind editorial imagery with headlines in white or champagne. High contrast = instant luxury signal.
- **Accent saturation:** Push the primary CTA to a richer, more saturated tone. `#c23b32` (vivid red-terracotta) or `#c8893d` (warm amber-gold) reads as more decisive.
- **Surface card refinement:** A subtle warm gradient on product card backgrounds (`linear-gradient(160deg, #fdf6f0, #f5e8df)`) adds depth over flat `var(--surface)`.
- **Topbar:** Consider a dark topbar that transitions to transparent-scrolled on the home page — a widely used technique in fashion and luxury retail that signals premium brand positioning immediately.

### 5.8 Product detail page has no breadcrumb navigation
**File:** `apps/web/components/ProductDetailClient.tsx`

Users who arrive at a product detail page have no visual path back to the category they were browsing. A breadcrumb (`Apparel / Topwear / Shirts`) with each segment linking to the filtered catalogue, or a simple `← Back to results` link, is standard in fashion retail and significantly reduces bounce rate from detail pages.

### 5.9 Two-button search architecture is confusing — keyword vs AI search are not differentiated visually
**File:** `apps/web/components/ProductsClient.tsx:175-180`

The toolbar presents:
- Enter key / form submit → keyword search
- "Semantic search" button → AI vector search

These are presented at equal visual weight with no explanation. Most users will not understand the difference and will default to one or the other. Recommended patterns:
- A single search bar with a mode pill toggle ("Keyword | AI") inside or adjacent to the input
- Or a single unified search with a ✦ icon to trigger AI mode, with the keyword search happening on Enter

### 5.10 Empty search results render a plain text line with no CTA
**File:** `apps/web/components/ProductsClient.tsx:211`

```tsx
<p className="meta">No matching products found.</p>
```

An empty state at this size is a critical UX moment. A designed empty state should include:
- An icon or small illustration
- A headline: "No products match these filters"
- A "Clear all filters" button that resets the filter state

### 5.11 Assistant drawer has no visual differentiation from a generic popup
**File:** `apps/web/components/AssistantDrawer.tsx`, `apps/web/app/globals.css:415-429`

The drawer is a plain white box with a shadow. No avatar, no brand header bar, no distinct colour treatment. Giving the assistant a brand identity (an avatar icon, a header bar using `var(--accent)`, a name like "StyleSense AI") would make it feel like a real product feature rather than a developer test widget. The drawer also has no enter/exit animation — it appears and disappears instantly.

### 5.12 "Add item" and "Bag" are inconsistent — terminology should be unified
**File:** `apps/web/components/ProductCard.tsx:48`, `apps/web/components/HeaderNav.tsx:22`

The header says "Bag" but the add button says "Add item". In fashion, "bag" is a common and appropriate metaphor. If "Bag" is the chosen term, the button should read "Add to bag". If "Cart" is preferred, the header link should say "Cart". The current mix undercuts the brand's sense of coherence.

---

## 6. Summary — Prioritised Action List

### P0 — Broken functionality or direct requirement violations
| # | Issue | File |
|---|---|---|
| 1 | Register form submits to non-existent `/api/auth/register-session` — registration is broken | `AuthForms.tsx:47-50` |
| 2 | Guest nav shows Bag, Support, Account orders, Admin — must show Catalogue + Sign In only | `HeaderNav.tsx` |
| 3 | No sign-out action anywhere in the UI | `HeaderNav.tsx` |
| 4 | Unauthenticated add-to-cart shows "UNAUTHENTICATED" text — must redirect to login | `ProductsClient.tsx`, `ProductDetailClient.tsx` |
| 5 | Admin link visible to all users; `User` type missing `roles` field | `HeaderNav.tsx`, `types.ts` |
| 6 | Logged-in nav missing Account link and wrong Orders label | `HeaderNav.tsx` |

### P1 — Layout and information architecture
| # | Issue | File |
|---|---|---|
| 7 | Filters are a horizontal collapsible bar — must move to a persistent left sidebar | `ProductsClient.tsx`, `globals.css` |
| 8 | Cart items have no product image | `CartClient.tsx`, backend store |
| 9 | No header-level search bar — search is buried inside the products page | `layout.tsx` |
| 10 | Product detail has no breadcrumb or back navigation | `ProductDetailClient.tsx` |
| 11 | No Account page — user profile and preferences are unreachable | Missing page |

### P2 — Visual quality and first impression
| # | Issue |
|---|---|
| 12 | Home page has no product imagery — hero is text-only |
| 13 | No loading skeleton — product grid is blank during fetch |
| 14 | Ratings not displayed on product cards |
| 15 | No toast notification for cart success/failure |
| 16 | Two unlabelled search modes confuse users — unify or differentiate clearly |
| 17 | Empty results state is a plain text line with no illustration or clear CTA |
| 18 | Palette is warm but not bold enough to "dazzle" — hero needs high contrast editorial treatment |
| 19 | "Add item" vs "Bag" terminology inconsistency |
| 20 | Assistant drawer has no brand identity or enter/exit animation |
