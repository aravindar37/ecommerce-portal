# UX Task List

Scope: `apps/web/` — Next.js frontend

---

## Feature A: Clickable Orders with Full Order Detail Page

Orders currently render as plain, unclickable text rows. Add a detail page reachable by clicking any order row, showing products, quantities, prices, totals, and the delivery address.

---

### A1 — Extend `OrderItem` and `Order` types in `types.ts`

- [x] Extend `OrderItem`, `Order`, and `Address` TypeScript interfaces in `types.ts` to match the full API response.

**File:** `apps/web/lib/types.ts`

The backend `GET /api/core/orders/{orderNumber}` already returns a complete order document. The TypeScript types need to match.

Add the `Address` interface:
```typescript
export interface Address {
  name: string;
  line1: string;
  line2?: string;
  city: string;
  region: string;
  postalCode: string;
  country: string;
  phone: string;
}
```

Extend `OrderItem` to include fields already present in the API response:
```typescript
export interface OrderItem {
  orderItemId: string;
  productId?: string;
  sourceProductId?: string;
  titleSnapshot: string;
  imageUrlSnapshot?: string | null;
  size?: string | null;
  quantity: number;
  unitPrice?: ProductPrice;
  returnStatus?: string;
}
```

Extend `Order` to include fields already returned by the API:
```typescript
export interface Order {
  _id: string;
  orderNumber: string;
  status: string;
  items: OrderItem[];
  shippingAddress?: Address;
  totals: Totals;
  payment?: { provider: string; status: string; transactionId?: string };
  placedAt?: string;
  estimatedDeliveryAt?: string;
}
```

**Validation:** TypeScript compilation passes with no type errors.
```bash
cd apps/web && npx tsc --noEmit
```

---

### A2 — Make each order row in `OrdersClient` a clickable link

- [x] Replace plain `<div>` order rows with `<Link>` elements navigating to `/orders/{orderNumber}`.

**File:** `apps/web/components/OrdersClient.tsx`

Replace the plain `<div>` per order with a `<Link>` to the order detail route. Show additional summary fields (status, placed date, item count) to give the user enough context before clicking.

Current code (replace):
```tsx
<div key={order._id}>
  <strong>{order.orderNumber}</strong> · {money(order.totals.grandTotal, order.totals.currency)}
</div>
```

Replace with:
```tsx
import Link from "next/link";

<Link key={order._id} href={`/orders/${order.orderNumber}`} className="order-row">
  <div className="order-row-meta">
    <strong className="order-number">{order.orderNumber}</strong>
    <span className="status-badge" data-status={order.status ?? "confirmed"}>
      {order.status ?? "confirmed"}
    </span>
  </div>
  <div className="order-row-detail">
    <span className="meta">{order.items.length} item{order.items.length !== 1 ? "s" : ""}</span>
    {order.placedAt ? (
      <span className="meta">{new Date(order.placedAt).toLocaleDateString("en-IN")}</span>
    ) : null}
    <span className="price">{money(order.totals.grandTotal, order.totals.currency)}</span>
  </div>
</Link>
```

**Validation:** Clicking any order row navigates to `/orders/{orderNumber}` and the URL updates in the browser.

---

### A3 — Create the order detail page route

- [x] Create `apps/web/app/orders/[orderNumber]/page.tsx` as a Next.js App Router dynamic route.

**File to create:** `apps/web/app/orders/[orderNumber]/page.tsx`

```tsx
import { OrderDetailClient } from "@/components/OrderDetailClient";

interface PageProps {
  params: Promise<{ orderNumber: string }>;
}

export default async function OrderDetailPage({ params }: PageProps) {
  const { orderNumber } = await params;
  return <OrderDetailClient orderNumber={orderNumber} />;
}
```

**Validation:** Navigating to `/orders/ORD-{date}-{n}` renders the page without a 404.

---

### A4 — Create `OrderDetailClient` component

- [x] Create `OrderDetailClient.tsx` rendering order header, items with thumbnails and unit prices, totals, delivery address, and payment info.

**File to create:** `apps/web/components/OrderDetailClient.tsx`

```tsx
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, money } from "@/lib/api";
import type { Order } from "@/lib/types";
import { ApiError } from "@/lib/api";

interface OrderDetailClientProps {
  orderNumber: string;
}

export function OrderDetailClient({ orderNumber }: OrderDetailClientProps) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Order>(`/api/core/orders/${orderNumber}`)
      .then(setOrder)
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 401) {
          window.location.assign("/login");
          return;
        }
        setError(caught instanceof Error ? caught.message : "Unable to load order");
      });
  }, [orderNumber]);

  if (error) return (
    <main className="main">
      <p className="error">{error}</p>
      <Link href="/orders" className="button secondary" style={{ display: "inline-flex", marginTop: 16 }}>← Back to orders</Link>
    </main>
  );

  if (!order) return <main className="main"><p className="meta">Loading order…</p></main>;

  const addr = order.shippingAddress;

  return (
    <main className="main">
      <Link href="/orders" className="back-link">← Back to orders</Link>

      {/* Header */}
      <div className="order-detail-header">
        <div>
          <h1 className="page-title" style={{ fontSize: "1.6rem" }}>{order.orderNumber}</h1>
          {order.placedAt ? (
            <p className="meta">Placed {new Date(order.placedAt).toLocaleDateString("en-IN", { dateStyle: "long" })}</p>
          ) : null}
          {order.estimatedDeliveryAt ? (
            <p className="meta">Estimated delivery {new Date(order.estimatedDeliveryAt).toLocaleDateString("en-IN", { dateStyle: "long" })}</p>
          ) : null}
        </div>
        <span className="status-badge" data-status={order.status}>{order.status}</span>
      </div>

      <div className="order-detail-grid">
        {/* Items */}
        <section className="panel order-items-section">
          <h2>Items</h2>
          {order.items.map((item) => (
            <div key={item.orderItemId} className="order-item-row">
              {item.imageUrlSnapshot ? (
                <img
                  className="order-item-thumb"
                  src={`/product-images/${item.sourceProductId ?? ""}.jpg`}
                  alt={item.titleSnapshot}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <div className="order-item-thumb-placeholder" />
              )}
              <div className="order-item-info">
                <strong>{item.titleSnapshot}</strong>
                {item.size ? <span className="meta">Size: {item.size}</span> : null}
                <span className="meta">Qty: {item.quantity}</span>
              </div>
              <div className="order-item-price">
                {item.unitPrice ? money(item.unitPrice.amount * item.quantity, item.unitPrice.currency) : null}
              </div>
            </div>
          ))}
        </section>

        <div className="order-detail-sidebar">
          {/* Totals */}
          <section className="panel">
            <h2>Order total</h2>
            <div className="order-totals">
              <span>Subtotal</span><span>{money(order.totals.subtotal, order.totals.currency)}</span>
              {order.totals.tax > 0 ? <><span>Tax (GST)</span><span>{money(order.totals.tax, order.totals.currency)}</span></> : null}
              <span>Shipping</span><span>{order.totals.shipping === 0 ? "Free" : money(order.totals.shipping, order.totals.currency)}</span>
              {order.totals.discount > 0 ? <><span>Discount</span><span>−{money(order.totals.discount, order.totals.currency)}</span></> : null}
              <strong>Total</strong><strong>{money(order.totals.grandTotal, order.totals.currency)}</strong>
            </div>
          </section>

          {/* Shipping address */}
          {addr ? (
            <section className="panel">
              <h2>Delivery address</h2>
              <address className="address-block">
                <span>{addr.name}</span>
                <span>{addr.line1}{addr.line2 ? `, ${addr.line2}` : ""}</span>
                <span>{addr.city}, {addr.region} {addr.postalCode}</span>
                <span>{addr.country}</span>
                {addr.phone ? <span>{addr.phone}</span> : null}
              </address>
            </section>
          ) : null}

          {/* Payment */}
          {order.payment ? (
            <section className="panel">
              <h2>Payment</h2>
              <p className="meta">{order.payment.provider} · {order.payment.status}</p>
            </section>
          ) : null}
        </div>
      </div>
    </main>
  );
}
```

**Validation:**
1. Navigate to `/orders/{orderNumber}` — all sections render without errors.
2. Items show title, size, quantity, and line total.
3. Totals match the order confirmation page.
4. Delivery address matches what was entered at checkout.
5. Unauthenticated access redirects to `/login`.

---

### A5 — Add CSS for order detail layout

- [x] Add `.order-row`, `.status-badge`, `.order-detail-grid`, `.order-item-row`, `.order-totals`, and `.address-block` CSS classes.

**File:** `apps/web/app/globals.css`

Add the following classes:

```css
/* Order list */
.order-row {
  display: grid;
  gap: 6px;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
  text-decoration: none;
  color: inherit;
  transition: background 120ms ease;
}
.order-row:first-child { padding-top: 0; }
.order-row:last-child  { border-bottom: none; padding-bottom: 0; }
.order-row:hover { background: var(--accent-soft); margin: 0 -18px; padding: 14px 18px; border-radius: 8px; }
.order-row-meta   { display: flex; align-items: center; gap: 10px; }
.order-row-detail { display: flex; align-items: center; gap: 16px; }
.order-number     { font-family: var(--font-display); font-size: 1.05rem; }

/* Status badge */
.status-badge {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--band);
  color: var(--muted);
}
.status-badge[data-status="confirmed"],
.status-badge[data-status="paid"] { background: #e6f4ea; color: #2e7d32; }
.status-badge[data-status="placed"]  { background: #fff8e1; color: #f57f17; }
.status-badge[data-status="return_initiated"] { background: #fce4ec; color: #b71c1c; }

/* Order detail page */
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.9rem;
  margin-bottom: 20px;
  transition: color 140ms ease;
}
.back-link:hover { color: var(--ink); }

.order-detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.order-detail-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
  align-items: start;
}

.order-detail-sidebar { display: grid; gap: 16px; }

.order-items-section { display: grid; gap: 0; }

.order-item-row {
  display: grid;
  grid-template-columns: 64px 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
}
.order-item-row:last-child { border-bottom: none; }

.order-item-thumb {
  width: 64px;
  height: 64px;
  object-fit: contain;
  border-radius: 8px;
  background: var(--band);
}
.order-item-thumb-placeholder {
  width: 64px;
  height: 64px;
  border-radius: 8px;
  background: var(--band);
}

.order-item-info  { display: grid; gap: 4px; }
.order-item-price { font-weight: 700; white-space: nowrap; }

.order-totals {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 16px;
  align-items: center;
  font-size: 0.95rem;
}
.order-totals strong { font-size: 1.05rem; padding-top: 8px; border-top: 1px solid var(--line); }

.address-block {
  font-style: normal;
  display: grid;
  gap: 3px;
  font-size: 0.95rem;
  line-height: 1.5;
}

@media (max-width: 760px) {
  .order-detail-grid { grid-template-columns: 1fr; }
}
```

**Validation:** Order detail page lays out correctly at 1280px desktop and 375px mobile widths.

---

## Feature B: Remove Size Picker and Add-to-Bag from Catalogue Page

The catalogue (`/products`) should be a clean browsing grid showing image, product tags, price, and rating only. The add-to-bag interaction moves exclusively to the product detail page.

---

### B1 — Pass `showAdd={false}` to `ProductCard` in `ProductsClient`

- [x] Pass `showAdd={false}` to every `ProductCard` in the catalogue grid and remove the dead `addToCart` function.

**File:** `apps/web/components/ProductsClient.tsx`

Locate the `ProductCard` usage inside the product grid:
```tsx
<ProductCard key={product._id} product={product} onAdd={addToCart} />
```

Change to:
```tsx
<ProductCard key={product._id} product={product} showAdd={false} />
```

Remove or retain the `addToCart` function based on whether any other call site in the same file needs it. If `showAdd={false}` means `onAdd` is never called, delete `addToCart` from `ProductsClient` entirely to avoid dead code.

**Validation:** Catalogue page renders product cards with no size buttons or "Add to bag" button visible.

---

### B2 — Make `onAdd` optional in `ProductCard` when `showAdd={false}`

- [x] Make `onAdd` prop optional and guard its call site so catalogue renders without errors.

**File:** `apps/web/components/ProductCard.tsx`

Change the props interface so `onAdd` is optional:
```typescript
interface ProductCardProps {
  product: Product;
  onAdd?: (productId: string, size: string) => Promise<void>;
  showAdd?: boolean;
}
```

Guard the `onAdd` call site:
```tsx
<button
  className="add-to-cart"
  type="button"
  aria-label="Add to bag"
  onClick={() => onAdd && void onAdd(product._id, size)}
>
  Add to bag
</button>
```

Remove the `size` state initialization when `showAdd` is `false` — use lazy initializer or move `useState("M")` inside the `showAdd` block, to avoid unnecessary state on every catalogue card:
```tsx
// Only maintain size state when the picker is visible
const [size, setSize] = useState<string>("M");
```
This is acceptable as-is (React state is cheap), but the code intent is clearer with a note.

**Validation:** TypeScript compiles without errors. Catalogue renders without size pickers. Product detail page still shows size picker and "Add to bag" (`showAdd` defaults to `true`).

---

## Feature C: 4 × 4 Product Grid with Smaller Cards and 16 Items Per Page

Change the product grid from a fluid auto-fill layout to a fixed 4-column grid. Reduce card visual weight so more products are visible above the fold. Update the page size from 12 to 16.

---

### C1 — Fix the product grid to 4 columns with a tighter gap

- [x] Change `.grid` to `repeat(4, minmax(0, 1fr))` with 16px gap and add responsive breakpoints at 960px and 600px.

**File:** `apps/web/app/globals.css`

Current:
```css
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 24px;
}
```

Replace with:
```css
.grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
```

Add responsive breakpoints so the grid degrades gracefully (place these inside the existing `@media (max-width: 760px)` block and add a new intermediate breakpoint):
```css
@media (max-width: 960px) {
  .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
}
@media (max-width: 600px) {
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
}
```

**Validation:** At 1280px wide, exactly 4 product cards appear per row. At 900px, 3 columns. At 500px, 2 columns.

---

### C2 — Reduce product image aspect ratio and card body padding

- [x] Change image `aspect-ratio` to `3/4`, reduce card body padding and gap, and shrink title `min-height`.

**File:** `apps/web/app/globals.css`

Current image ratio:
```css
.product-media {
  aspect-ratio: 4 / 5;
  ...
}
```

Change to a squarer ratio that fits more cards on screen without losing the fashion framing:
```css
.product-media {
  aspect-ratio: 3 / 4;
  ...
}
```

Reduce internal padding to keep cards compact in a 4-column layout:
```css
/* current */
.product-media-link { margin: 12px 12px 0; }
.card-body { padding: 14px; gap: 10px; }

/* replace with */
.product-media-link { margin: 8px 8px 0; }
.card-body { padding: 10px; gap: 6px; }
```

Reduce the product title minimum height so short titles don't leave an oversized gap:
```css
/* current */
.product-title { min-height: 2.5em; ... }

/* replace with */
.product-title { min-height: 2em; font-size: 0.92rem; }
```

**Validation:** Cards in a 4-column layout show the image, tags, price, and rating without excessive vertical whitespace. No card truncates its title at normal browser zoom levels.

---

### C3 — Update page size constant and pagination labels

- [x] Extract `const PAGE_SIZE = 16` and update all three hardcoded `12` references in `ProductsClient`.

**File:** `apps/web/components/ProductsClient.tsx`

Introduce a named constant at the top of the file to avoid the magic number `12` scattered in three places:
```typescript
const PAGE_SIZE = 16;
```

Update all three occurrences:
```typescript
// 1. Product fetch
params.set("limit", String(PAGE_SIZE));

// 2. Show pager only when more than one page of results
{total > PAGE_SIZE ? (
  <div className="pager" ...>
    ...
    <span className="meta">Page {page} of {Math.ceil(total / PAGE_SIZE)}</span>
    <button ... disabled={page >= Math.ceil(total / PAGE_SIZE)} ...>
```

**Validation:**
1. The `/products` page fetches 16 products on first load (confirmed in Network tab or server logs).
2. The pager shows correct page count — for 44,446 products: `Math.ceil(44446 / 16) = 2778`.
3. Navigating to page 2 shows the next 16 products.

---

### C4 — Update semantic search to also return 16 results

- [x] Replace hardcoded `limit: 12` in the semantic search call with `PAGE_SIZE`.

**File:** `apps/web/components/ProductsClient.tsx`

The semantic search call still hardcodes `limit: 12`:
```typescript
body: JSON.stringify({
  query,
  filters: { ... },
  limit: 12   // ← change to PAGE_SIZE
})
```

Change to:
```typescript
limit: PAGE_SIZE
```

**Validation:** Semantic search returns 16 results when enough products match the query.

---

## Feature D: Product Links in Chat Responses

Each product card shown inside the shopping assistant drawer must link to the product detail page, opening in a new tab so the user stays in the chat.

---

### D1 — Add `tags` field to the `Product` type in `types.ts`

- [x] Add `tags?: string[]` to the `Product` interface in `types.ts`.

**File:** `apps/web/lib/types.ts`

The product document from the Search Service API includes a `tags` array. Add it to the interface so the chat product card can display it:

```typescript
export interface Product {
  // ... existing fields ...
  tags?: string[];
}
```

**Validation:** TypeScript compiles without errors (`cd apps/web && npx tsc --noEmit`).

---

### D2 — Add a "View product" link to each product card inside the chat drawer

- [x] Wrap each chat product card in a `<a href="/products/{slug}" target="_blank">` link and add a "View ↗" button.

**File:** `apps/web/components/AssistantDrawer.tsx`

Current product card block (inside `reply.products.slice(0, 2).map(...)`):
```tsx
<div key={product._id} className="panel" style={{ marginTop: 8, padding: 10 }}>
  <strong>{product.title}</strong>
  <span className="meta">
    {product.baseColour} · {product.usage ?? product.articleType}
  </span>
  <span>{money(product.price.amount, product.price.currency)}</span>
</div>
```

Replace with a chat product card that includes:
- Product image thumbnail
- Title linked to the product page (opens in new tab)
- Colour and usage tags
- Price
- A prominent "View product" link

```tsx
<div key={product._id} className="chat-product-card">
  {product.images[0]?.url ? (
    <img
      className="chat-product-thumb"
      src={product.images[0].url}
      alt={product.title}
    />
  ) : null}
  <div className="chat-product-body">
    <a
      href={`/products/${product.slug}`}
      target="_blank"
      rel="noopener noreferrer"
      className="chat-product-title"
    >
      {product.title}
    </a>
    <span className="meta">
      {product.baseColour} · {product.usage ?? product.articleType}
    </span>
    <div className="chat-product-footer">
      <span className="price">{money(product.price.amount, product.price.currency)}</span>
      <a
        href={`/products/${product.slug}`}
        target="_blank"
        rel="noopener noreferrer"
        className="button secondary"
        style={{ fontSize: "0.82rem", minHeight: 32, padding: "0 12px" }}
        aria-label={`View ${product.title} in new tab`}
      >
        View ↗
      </a>
    </div>
  </div>
</div>
```

**Validation:**
1. After sending a message to the shopping assistant, each product card shows a "View ↗" link.
2. Clicking the link opens `/products/{slug}` in a new browser tab.
3. The parent drawer remains open and the conversation is not interrupted.

---

### D3 — Add CSS for chat product cards

- [x] Add `.chat-product-card`, `.chat-product-thumb`, `.chat-product-body`, `.chat-product-footer`, and `.chat-product-title` CSS classes.

**File:** `apps/web/app/globals.css`

```css
.chat-product-card {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 10px;
  align-items: start;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
}

.chat-product-thumb {
  width: 64px;
  height: 64px;
  object-fit: contain;
  border-radius: 8px;
  background: var(--band);
}

.chat-product-body {
  display: grid;
  gap: 4px;
}

.chat-product-title {
  font-weight: 700;
  font-size: 0.92rem;
  line-height: 1.3;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.chat-product-title:hover { color: var(--accent-strong); }

.chat-product-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
}
```

**Validation:** Chat product cards render with a thumbnail on the left and title + price + "View ↗" link on the right.

---

## Feature E: Persistent Chat Feed Loaded from Database

The shopping assistant chat is currently held in React component state and is lost on page refresh, navigation, or when the drawer is closed and reopened. This feature makes the chat feed persistent by:

1. Storing each session ID in `localStorage` so the same session is resumed on return.
2. Loading the full message history from the Chat Service API on drawer open.
3. Displaying both sides of the conversation (user messages and assistant responses) as a proper two-sided chat feed.

---

### E1 — Update `AssistantReply` and add `ChatMessage` type to `types.ts`

- [x] Add `ChatMessage` interface to `types.ts` matching the history API response shape.

**File:** `apps/web/lib/types.ts`

Add a `ChatMessage` interface that matches the message document returned by `GET /api/assistant/shopping/sessions/{sessionId}/messages`:

```typescript
export interface ChatMessage {
  _id?: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    suggestedProducts?: Product[];
    pendingActionId?: string;
    context?: Record<string, unknown>;
  };
  createdAt: string;
}
```

**Validation:** TypeScript compiles without errors.

---

### E2 — Persist and resume the session ID via `localStorage`

- [x] Read/write session ID from `localStorage`; update `ensureSession()` to try `GET /sessions` before creating a new one.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Current:** `sessionId` is a React state string that resets to `""` when the component unmounts (drawer closes).

**Change:** Read and write the session ID from `localStorage` so it survives re-opens and page refreshes.

Replace:
```typescript
const [sessionId, setSessionId] = useState<string>("");
```

With:
```typescript
const STORAGE_KEY = "styleSenseShoppingSessionId";

const [sessionId, setSessionId] = useState<string>(
  () => (typeof window !== "undefined" ? (localStorage.getItem(STORAGE_KEY) ?? "") : "")
);

function persistSession(id: string): void {
  setSessionId(id);
  localStorage.setItem(STORAGE_KEY, id);
}
```

Update `ensureSession()` to call `persistSession` instead of `setSessionId`:
```typescript
async function ensureSession(): Promise<string> {
  if (sessionId) return sessionId;
  // Try to find an existing active session first
  try {
    const existing = await apiFetch<{ session: { _id: string } | null }>(
      "/api/chat/assistant/shopping/sessions"
    );
    if (existing.session?._id) {
      persistSession(existing.session._id);
      return existing.session._id;
    }
  } catch {
    // No active session found — create a new one
  }
  const session = await apiFetch<{ _id: string }>("/api/chat/assistant/shopping/sessions", {
    method: "POST",
    body: JSON.stringify({ entryPoint: "catalogue" })
  });
  persistSession(session._id);
  return session._id;
}
```

**Validation:**
1. Open the assistant drawer and send a message. Close the drawer.
2. Reload the page and reopen the drawer — the session ID in localStorage must match the previous one.
3. Check browser DevTools → Application → Local Storage → `styleSenseShoppingSessionId`.

---

### E3 — Load message history from the API on drawer open

- [x] Add a `useEffect` that calls `GET /sessions/{id}/messages` when the drawer opens and populates the feed from history.

**File:** `apps/web/components/AssistantDrawer.tsx`

Add a `useEffect` that runs once when `open` transitions from `false` to `true`. It fetches the history and populates the message feed.

**Change the `replies` state type** to hold both user and assistant entries:
```typescript
interface FeedEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  products: Product[];
  pendingActionId?: string;
}

const [replies, setReplies] = useState<FeedEntry[]>([]);
```

Add history loader:
```typescript
const [historyLoaded, setHistoryLoaded] = useState(false);

useEffect(() => {
  if (!open || historyLoaded) return;

  async function loadHistory(): Promise<void> {
    const sid = sessionId || localStorage.getItem("styleSenseShoppingSessionId") ?? "";
    if (!sid) return;
    try {
      const data = await apiFetch<{ items: ChatMessage[] }>(
        `/api/chat/assistant/shopping/sessions/${sid}/messages?limit=100`
      );
      const feed: FeedEntry[] = data.items.map((msg) => ({
        id: msg._id ?? crypto.randomUUID(),
        role: msg.role,
        text: msg.content,
        products: msg.metadata?.suggestedProducts ?? [],
        pendingActionId: msg.metadata?.pendingActionId,
      }));
      setReplies(feed);
      setHistoryLoaded(true);
    } catch {
      // History unavailable — start with empty feed, not an error
      setHistoryLoaded(true);
    }
  }

  void loadHistory();
}, [open, historyLoaded, sessionId]);
```

Reset `historyLoaded` when the session changes so a new session's history loads:
```typescript
useEffect(() => {
  setHistoryLoaded(false);
}, [sessionId]);
```

**Validation:**
1. Send two messages, close the drawer, reopen — all messages including user messages appear in the feed without re-sending them.
2. Reload the page, reopen the drawer — message history loads from the server and appears before the user sends anything new.
3. Network tab confirms `GET /api/chat/assistant/shopping/sessions/{id}/messages` is called on drawer open.

---

### E4 — Render user messages as chat bubbles in the feed

- [x] Refactor `replies` state to `FeedEntry[]` holding both user and assistant entries; push user message optimistically before the API returns.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Current:** Only assistant replies are tracked in `replies`. User messages are not shown in the feed.

**Change:** When the user submits a message, push a user entry into the feed immediately (optimistic) before the API response arrives:

```typescript
async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
  event.preventDefault();
  if (!message.trim()) return;
  setStatus("");
  setError("");
  setBusy(true);
  const userEntry: FeedEntry = {
    id: crypto.randomUUID(),
    role: "user",
    text: message,
    products: [],
  };
  setReplies((prev) => [...prev, userEntry]);   // show user message immediately
  const userMessage = message;
  setMessage("");
  try {
    const activeSessionId = await ensureSession();
    const reply = await apiFetch<AssistantReply>("/api/chat/assistant/shopping/messages", {
      method: "POST",
      body: JSON.stringify({ sessionId: activeSessionId, message: userMessage, context: { cartAware: true } })
    });
    const assistantEntry: FeedEntry = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: reply.message,
      products: reply.suggestedProducts ?? [],
      pendingActionId: reply.pendingAction?.id,
    };
    setReplies((prev) => [...prev, assistantEntry]);
    setPendingActionId(reply.pendingAction?.id ?? "");
  } catch (caught) {
    // Remove the optimistic user entry on error
    setReplies((prev) => prev.filter((e) => e.id !== userEntry.id));
    setError(caught instanceof Error ? caught.message : "Unable to reach the shopping assistant");
  } finally {
    setBusy(false);
  }
}
```

**Validation:** In a fresh conversation, sending "Find a black shirt" shows the user's bubble immediately, followed by the assistant's response after the API returns. Both appear in the feed in order.

---

### E5 — Update the feed rendering to show user vs assistant bubbles

- [x] Replace the `replies.map()` block with a two-sided bubble layout using `chat-bubble-user` and `chat-bubble-assistant` classes; add auto-scroll ref.

**File:** `apps/web/components/AssistantDrawer.tsx`

Replace the current `replies.map()` block with a two-sided bubble layout:

```tsx
<div className="messages" ref={messagesEndRef}>
  {replies.map((entry) => (
    <div
      key={entry.id}
      className={`chat-bubble chat-bubble-${entry.role}`}
    >
      <p className="chat-bubble-text">{entry.text}</p>
      {entry.products.map((product) => (
        <div key={product._id} className="chat-product-card">
          {/* ... product card from Task D2 ... */}
        </div>
      ))}
    </div>
  ))}
  {busy ? <div className="chat-bubble chat-bubble-assistant chat-typing"><span /><span /><span /></div> : null}
  {status ? <div className="status">{status}</div> : null}
  {error ? <div className="error">{error}</div> : null}
  <div ref={scrollAnchor} />
</div>
```

Add auto-scroll to latest message:
```typescript
const scrollAnchor = useRef<HTMLDivElement>(null);

useEffect(() => {
  scrollAnchor.current?.scrollIntoView({ behavior: "smooth" });
}, [replies]);
```

**Validation:**
1. User messages appear as right-aligned bubbles (or distinct colour).
2. Assistant messages appear as left-aligned bubbles.
3. After each new message, the feed auto-scrolls to the bottom.

---

### E6 — Add CSS for the two-sided chat bubble layout

- [x] Add `.chat-bubble`, `.chat-bubble-user`, `.chat-bubble-assistant`, `.chat-typing`, and the `chat-bounce` animation; change `.messages` to `flex-direction: column`.

**File:** `apps/web/app/globals.css`

```css
.chat-bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  line-height: 1.45;
  font-size: 0.95rem;
}

.chat-bubble-user {
  background: var(--accent);
  color: white;
  border-bottom-right-radius: 4px;
  align-self: flex-end;
  margin-left: auto;
}

.chat-bubble-assistant {
  background: var(--band);
  color: var(--ink);
  border-bottom-left-radius: 4px;
}

.chat-bubble-text { margin: 0; }

/* Typing indicator */
.chat-typing {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 12px 16px;
}
.chat-typing span {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
  animation: chat-bounce 1.2s ease-in-out infinite;
}
.chat-typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes chat-bounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40%           { transform: scale(1); opacity: 1; }
}

/* Make .messages a flex column so bubbles stack naturally */
.messages {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  max-height: 360px;
  padding: 4px 0;
}
```

**Validation:**
1. User messages appear right-aligned in `var(--accent)` red/terra-cotta background with white text.
2. Assistant messages appear left-aligned in `var(--band)` warm background.
3. The typing indicator (three animated dots) shows while `busy = true`.
4. The message feed scrolls independently without affecting the rest of the drawer.

---

## Feature H: Conversation History Panel in the Chat Drawer

Currently the chat drawer resumes a single active session (Feature E). Feature H adds a conversation history panel so users can browse all their past shopping chats, switch to any of them, and load older ones. The default view shows the 5 most recent conversations.

Depends on: Feature E (session localStorage, message history loading) and chat_service Feature H (session list API with `summary`, `messageCount`, and cursor pagination).

---

### H1 — Add `ChatSession` type to `types.ts`

- [x] Add a `ChatSession` interface to `apps/web/lib/types.ts` matching the session list API response shape.

**File:** `apps/web/lib/types.ts`

```typescript
export interface ChatSession {
  _id: string;
  type: "shopping" | "returns_support";
  summary: string;
  messageCount: number;
  status: string;
  createdAt: string;
  updatedAt: string;
}
```

This is returned by `GET /api/chat/assistant/shopping/sessions/history` and `GET /api/chat/assistant/support/sessions/history`.

**Validation:** `cd apps/web && npx tsc --noEmit`

---

### H2 — Fetch and display conversation history in `AssistantDrawer`

- [x] On drawer open, call `GET /api/chat/assistant/shopping/sessions/history?limit=5` and populate a conversation list panel below the drawer header, above the message feed.

**File:** `apps/web/components/AssistantDrawer.tsx`

Add state for the sessions list:
```typescript
const [sessions, setSessions] = useState<ChatSession[]>([]);
const [sessionsCursor, setSessionsCursor] = useState<string | null>(null);
const [sessionsHasMore, setSessionsHasMore] = useState(false);
const [sessionsLoading, setSessionsLoading] = useState(false);
```

Add a `loadSessions` function that calls the history API and appends results (used for both initial load and "Load more"):
```typescript
async function loadSessions(cursor?: string): Promise<void> {
  setSessionsLoading(true);
  try {
    const url = `/api/chat/assistant/shopping/sessions/history?limit=5${cursor ? `&before=${cursor}` : ""}`;
    const data = await apiFetch<{
      items: ChatSession[];
      hasMore: boolean;
      nextCursor: string | null;
    }>(url);
    setSessions((prev) => cursor ? [...prev, ...data.items] : data.items);
    setSessionsHasMore(data.hasMore);
    setSessionsCursor(data.nextCursor ?? null);
  } catch {
    // history unavailable — show empty list without error
  } finally {
    setSessionsLoading(false);
  }
}
```

Call `loadSessions()` inside the existing drawer-open `useEffect` (alongside message history loading):
```typescript
useEffect(() => {
  if (!open) return;
  void loadSessions();
}, [open]);
```

**Validation:**
1. Open the drawer — the conversation list appears showing up to 5 sessions.
2. Each session row shows its `summary` (first user message) and relative timestamp.
3. Network tab confirms `GET /api/chat/assistant/shopping/sessions/history?limit=5` is called once on drawer open.

---

### H3 — Render the conversation list with session preview rows

- [x] Render the `sessions` list as clickable rows inside the drawer, above the message feed. Each row shows the conversation summary, message count, and relative time.

**File:** `apps/web/components/AssistantDrawer.tsx`

Add the sessions panel between the drawer header and the messages feed:

```tsx
{sessions.length > 0 ? (
  <div className="chat-history-panel">
    <div className="chat-history-header">
      <span className="chat-history-label">Recent chats</span>
      <button
        type="button"
        className="chat-new-btn secondary"
        onClick={startNewSession}
        aria-label="Start new conversation"
      >
        + New
      </button>
    </div>
    {sessions.map((s) => (
      <button
        key={s._id}
        type="button"
        className={`chat-session-row${s._id === sessionId ? " chat-session-row--active" : ""}`}
        onClick={() => void switchSession(s._id)}
        aria-current={s._id === sessionId ? "true" : undefined}
      >
        <span className="chat-session-summary">
          {s.summary || "New conversation"}
        </span>
        <span className="chat-session-meta">
          {s.messageCount} msg · {relativeTime(s.updatedAt)}
        </span>
      </button>
    ))}
    {sessionsHasMore ? (
      <button
        type="button"
        className="chat-load-more secondary"
        onClick={() => void loadSessions(sessionsCursor ?? undefined)}
        disabled={sessionsLoading}
      >
        {sessionsLoading ? "Loading…" : "Load more"}
      </button>
    ) : null}
  </div>
) : null}
```

Add a `relativeTime` helper:
```typescript
function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
```

**Validation:**
1. Drawer shows up to 5 session rows ordered newest-first.
2. The currently active session row is highlighted (`.chat-session-row--active`).
3. Each row shows the summary and relative timestamp.

---

### H4 — Implement session switching and "New conversation" actions

- [x] Clicking a session row loads that session's messages into the feed; "New" button clears the feed and creates a fresh session on next send.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Session switching:**
```typescript
async function switchSession(id: string): Promise<void> {
  if (id === sessionId) return;  // already active
  persistSession(id);
  setFeed([]);
  setHistoryLoaded(false);  // triggers the existing history loader useEffect
  setPendingActionId("");
  setStatus("");
  setError("");
}
```

The existing `useEffect` on `[open, historyLoaded, sessionId]` will fire after `setHistoryLoaded(false)`, fetching the messages for the newly selected session.

**New conversation:**
```typescript
function startNewSession(): void {
  persistSession("");           // clear stored session ID
  localStorage.removeItem(STORAGE_KEY);
  setFeed([]);
  setHistoryLoaded(true);       // no history to load for a new session
  setPendingActionId("");
  setStatus("");
  setError("");
}
```

On the next message send, `ensureSession()` will see an empty `sessionId` and create a new session via `POST /sessions`.

**Validation:**
1. Clicking a past session row loads that session's messages without page reload.
2. "New" button clears the feed; the next message creates a fresh session.
3. After switching sessions, the `styleSenseShoppingSessionId` in localStorage matches the selected session.
4. The session list row highlights the active session correctly after switching.

---

### H5 — Add CSS for the conversation history panel

- [x] Add `.chat-history-panel`, `.chat-history-header`, `.chat-session-row`, `.chat-session-summary`, `.chat-session-meta`, `.chat-load-more`, and `.chat-new-btn` CSS classes.

**File:** `apps/web/app/globals.css`

```css
/* Conversation history panel inside the chat drawer */
.chat-history-panel {
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 2px;
  display: grid;
  gap: 2px;
}

.chat-history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 2px 0 6px;
}

.chat-history-label {
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
}

.chat-new-btn {
  font-size: 0.8rem;
  min-height: 26px;
  padding: 0 10px;
  border-radius: 999px;
}

.chat-session-row {
  display: grid;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 8px;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink);
  min-height: auto;
  cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
  font-weight: normal;
}

.chat-session-row:hover:not(:disabled) {
  background: var(--band);
  border-color: var(--line);
  transform: none;
}

.chat-session-row--active {
  background: var(--accent-soft);
  border-color: var(--accent);
}

.chat-session-row--active:hover:not(:disabled) {
  background: var(--accent-soft);
}

.chat-session-summary {
  font-size: 0.88rem;
  font-weight: 600;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}

.chat-session-meta {
  font-size: 0.78rem;
  color: var(--muted);
}

.chat-load-more {
  margin-top: 4px;
  font-size: 0.82rem;
  min-height: 30px;
  padding: 0 12px;
  width: 100%;
  border-radius: 8px;
}
```

**Validation:**
1. Session rows are visually distinct from the chat feed.
2. Active session row has a coloured border matching the accent palette.
3. Long summaries truncate with ellipsis; they do not overflow the drawer width.
4. "Load more" button spans the full width of the panel.

---

### H6 — Collapse history panel and add toggle for compact mode

- [x] Add a toggle that collapses the conversation history panel to save space once the user is actively chatting. Re-opening it shows the full list.

**File:** `apps/web/components/AssistantDrawer.tsx`

Add a `historyOpen` state defaulting to `true` when the drawer opens with no active session, `false` when a session is already active:

```typescript
const [historyOpen, setHistoryOpen] = useState<boolean>(!sessionId);
```

Wrap the sessions list in a collapsible:
```tsx
<div className="chat-history-panel">
  <div className="chat-history-header">
    <button
      type="button"
      className="chat-history-toggle"
      onClick={() => setHistoryOpen((v) => !v)}
      aria-expanded={historyOpen}
    >
      <span className="chat-history-label">
        {historyOpen ? "▾ Recent chats" : "▸ Recent chats"}
      </span>
    </button>
    <button type="button" className="chat-new-btn secondary" onClick={startNewSession}>
      + New
    </button>
  </div>
  {historyOpen ? (
    <>
      {/* session rows and load more button */}
    </>
  ) : null}
</div>
```

When the user sends a message, collapse the history panel automatically:
```typescript
// inside submit(), after setting busy = true:
setHistoryOpen(false);
```

**Validation:**
1. On fresh drawer open (no session): history panel is expanded showing past sessions.
2. On drawer open with existing session: panel is collapsed showing only "▸ Recent chats" toggle.
3. Sending a message collapses the panel automatically.
4. Clicking "▸ Recent chats" re-expands the panel without losing the message feed.

---

## Feature I: Shopping Assistant Drawer — Conversation UX Fixes

These three issues were identified in the code review of `AssistantDrawer.tsx`. They are independent of the agentic backend work (Features F/G) and can be implemented against the current deterministic agent.

---

### I1 — Replace the floating Confirm button with an inline cart confirmation card

- [x] Remove the standalone `Confirm` button rendered below the message form and replace it with a card embedded directly in the chat feed, immediately after the assistant's recommendation bubble, showing the specific product being confirmed.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Problem:** The current confirm button appears outside the feed after the textarea, with no context about which product will be added:
```tsx
{pendingActionId ? (
  <button type="button" aria-label="Confirm add to cart" onClick={() => void confirm()} disabled={busy}>
    Confirm
  </button>
) : null}
```

If the assistant showed five product cards, the user cannot tell which one is queued for the cart. If they scroll away, the button appears orphaned.

**Fix:** When an assistant `FeedEntry` has a `pendingActionId`, render an inline confirmation card inside that entry — below its product cards:

```tsx
{/* Inside the feed map, after the product cards for an assistant entry: */}
{entry.pendingActionId && entry.pendingActionId === pendingActionId ? (
  <div className="chat-confirm-card">
    <p className="chat-confirm-label">
      Add <strong>{entry.products[0]?.title ?? "this item"}</strong> to your bag?
    </p>
    <div className="chat-confirm-actions">
      <button
        type="button"
        className="button"
        style={{ minHeight: 34, fontSize: "0.88rem", padding: "0 16px" }}
        onClick={() => void confirm()}
        disabled={busy}
        aria-label={`Confirm adding ${entry.products[0]?.title ?? "item"} to bag`}
      >
        {busy ? "Adding…" : "Add to bag"}
      </button>
      <button
        type="button"
        className="secondary"
        style={{ minHeight: 34, fontSize: "0.88rem", padding: "0 12px" }}
        onClick={() => setPendingActionId("")}
        disabled={busy}
        aria-label="Dismiss"
      >
        Not now
      </button>
    </div>
  </div>
) : null}
```

Remove the standalone confirm button entirely from the JSX returned by the component.

Add CSS for the confirmation card:
```css
.chat-confirm-card {
  margin-top: 10px;
  padding: 12px 14px;
  background: var(--accent-soft);
  border: 1px solid var(--accent);
  border-radius: 10px;
  display: grid;
  gap: 10px;
}

.chat-confirm-label {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.4;
}

.chat-confirm-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
```

**Validation:**
1. Send "Find black casual shoes." — the assistant bubble renders with product cards AND the "Add to bag / Not now" card directly below them.
2. The standalone button at the bottom of the drawer is gone.
3. Clicking "Not now" dismisses the card without navigating away.
4. Clicking "Add to bag" triggers the confirm API and shows the success bubble (I2).

---

### I2 — Add an assistant bubble to the feed after cart confirmation succeeds

- [x] After `POST /api/assistant/actions/confirm` resolves successfully, append an assistant `FeedEntry` to the feed with a confirmation message naming the added product, instead of setting a standalone `status` string.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Problem:** The current confirm handler does this:
```typescript
setStatus(result.status === "completed" ? "Added" : result.status);
setPendingActionId("");
```
`setStatus("Added")` writes a small floating status label at the bottom of the feed. There is no conversational follow-up. The user does not know what was added and cannot continue the conversation naturally.

**Fix:** Replace `setStatus` with an assistant feed entry:
```typescript
async function confirm(): Promise<void> {
  if (!pendingActionId) return;
  setError("");
  setBusy(true);
  // find the entry whose pendingActionId matches, to get the product name
  const matchEntry = feed.find((e) => e.pendingActionId === pendingActionId);
  const productName = matchEntry?.products[0]?.title ?? "the item";
  try {
    await apiFetch<{ status: string }>("/api/chat/assistant/actions/confirm", {
      method: "POST",
      body: JSON.stringify({ actionId: pendingActionId, confirm: true })
    });
    const confirmEntry: FeedEntry = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: `Done — I've added ${productName} to your bag. Would you like to keep browsing or head to checkout?`,
      products: [],
    };
    setFeed((prev) => [...prev, confirmEntry]);
    setPendingActionId("");
    setStatus("");           // clear any residual status
  } catch (caught) {
    setError(caught instanceof Error ? caught.message : "Unable to add to bag");
  } finally {
    setBusy(false);
  }
}
```

Remove the `{status ? <div className="status">{status}</div> : null}` render from the messages section once `setStatus` is no longer called from `confirm()`. Keep it only if other flows use `setStatus`.

**Validation:**
1. Send a message, receive a recommendation with the confirm card (I1).
2. Click "Add to bag" — a new assistant bubble appears in the feed: "Done — I've added [Product Name] to your bag. Would you like to keep browsing or head to checkout?"
3. The confirm card disappears. The bag icon in the nav shows the updated count.
4. The conversation can continue naturally after this message.

---

### I3 — Guard against empty assistant message text in the feed

- [x] In `AssistantDrawer`, guard `entry.text` so a blank or whitespace-only string never renders an empty bubble; fall back to a safe placeholder.

**File:** `apps/web/components/AssistantDrawer.tsx`

**Problem:** When `llm_text()` on the backend falls through all branches and returns an empty string, `reply.message` is `""`. The frontend creates a `FeedEntry` with `text: ""` and renders:
```tsx
<p className="chat-bubble-text">{entry.text}</p>
```
This produces an empty bubble — a visible white rectangle with no content — which looks broken.

**Fix:** Guard the display text at render time and the entry creation point:

At entry creation (in `submit`):
```typescript
const assistantEntry: FeedEntry = {
  id: crypto.randomUUID(),
  role: "assistant",
  text: reply.message?.trim() || "I found some options for you.",
  products: reply.suggestedProducts ?? [],
  pendingActionId: reply.pendingAction?.id,
};
```

At the `loadHistory` history-restore path, guard the same field:
```typescript
const entries: FeedEntry[] = data.items.map((msg) => ({
  id: msg._id ?? crypto.randomUUID(),
  role: msg.role,
  text: msg.content?.trim() || (msg.role === "assistant" ? "Here are some options." : ""),
  products: msg.metadata?.suggestedProducts ?? [],
  pendingActionId: msg.metadata?.pendingActionId,
}));
```

At render time, as a belt-and-suspenders guard:
```tsx
<p className="chat-bubble-text">
  {entry.text || (entry.role === "assistant" ? "Here are some options." : "")}
</p>
```

The fallback strings should only appear in practice when the LLM is not configured and the backend `fallback` parameter to `llm_text()` was left empty — which is a backend bug, but the frontend should not crash visibly.

**Validation:**
1. With `LLM_API_KEY` unset (deterministic fallback active), send any shopping message. The assistant bubble shows a non-empty string.
2. No empty white bubbles appear under any circumstances in normal use.
3. TypeScript compiles without errors: `cd apps/web && npx tsc --noEmit`

---

## Feature H: Completion Gates

- [x] `GET /api/chat/assistant/shopping/sessions/history?limit=5` returns 5 sessions with `summary`, `messageCount`, `hasMore`, and `nextCursor`.
  - Validation: open drawer and confirm network call in DevTools

- [x] "Load more" fetches the next 5 sessions with no duplicates.
  - Validation: create 6+ sessions then click "Load more" in the drawer

- [x] Switching sessions loads the selected session's messages without page reload.
  - Validation: manually switch between 2 sessions and verify feed updates

- [x] "New" button clears feed and creates a fresh session on next message send.
  - Validation: click "New", send a message, confirm new session ID in localStorage

- [x] History panel auto-collapses when user sends a message.
  - Validation: expand history, send message, confirm panel collapses
