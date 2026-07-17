# Ecommerce Demo Application Spec Sheet

Status: Draft v1  
Owner: Demo engineering team  
Last updated: 2026-05-02  

## 1. Purpose

Build a full-stack ecommerce demo application for fashion products that showcases:

- Secure user identity with custom email/password login and Google account login.
- Product browsing, filtering, product detail pages, cart, and demo checkout.
- Semantic product search backed by configurable embedding providers.
- A Codex-powered shopping assistant for product discovery and purchase guidance.
- A Codex-powered returns and support agent for order help, returns, refunds, and support triage.
- MongoDB Atlas as the system of record and vector database.
- Configurable LLM routing between OpenAI and a Grove/Azure gateway endpoint.
- Mandatory local OpenAI Codex MCP server integration for complex multi-step support chats.
- User activity capture for searches, product selections, filters, cart actions, and orders.

The application is a demo, but it should be built with production-shaped boundaries: provider adapters, auditable agent actions, secure server-side secrets, indexes, telemetry, and testable workflows.

## 2. Source Dataset

Primary dataset:

- Kaggle: Fashion Product Images Dataset
- URL: https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-dataset
- License: MIT, according to the Kaggle dataset page.
- Reported contents: approximately 44k fashion products with product images, `styles.csv`, and per-product metadata JSON files.
- Dataset structure:
  - `styles.csv`: product map and key category fields.
  - `images/<id>.jpg`: product image for the product ID.
  - `styles/<id>.json`: full product metadata for the product ID in the larger dataset.

Relevant `styles.csv` fields to ingest:

| Field | Type | Usage |
| --- | --- | --- |
| `id` | string/integer | Stable product ID from dataset. Store as `sourceProductId`. |
| `gender` | string | Product filtering and display. |
| `masterCategory` | string | Top-level category such as Apparel or Accessories. |
| `subCategory` | string | Secondary category. |
| `articleType` | string | Product type, useful for filters and recommendations. |
| `baseColour` | string | Color filter and product attributes. |
| `season` | string | Attribute/filter. |
| `year` | number/string | Attribute/filter. |
| `usage` | string | Intended usage, for example Casual or Sports. |
| `productDisplayName` | string | Product title. |

For demo completeness, the ingestion process must synthesize fields that are not present or not ecommerce-ready in the dataset:

- `slug`
- `description`
- `price`
- `currency`
- `inventory`
- `brand`
- `ratingAverage`
- `ratingCount`
- `tags`
- `careInstructions`
- `returnPolicyCode`

Synthetic values must be deterministic by `sourceProductId` so repeated imports are idempotent.

## 3. Product Goals

1. Present a polished ecommerce flow that can be used in live demos without seed-data fragility.
2. Demonstrate MongoDB Atlas as both transactional/document database and vector search layer.
3. Demonstrate AI-assisted shopping and support using a provider-agnostic LLM abstraction.
4. Keep embedding and LLM providers switchable through configuration, without code changes.
5. Provide clean audit trails for AI tool calls, order-affecting actions, return requests, and support actions.
6. Allow the same product corpus to be searched through keyword, filters, and semantic vector search.
7. Demonstrate Codex MCP server capabilities for complex, multi-step support chats.
8. Capture user activities, including all searches, product selections, applied filters, cart actions, and orders.

## 4. Non-Goals

- Real payment capture.
- Real shipment creation.
- Full marketplace/vendor management.
- Real inventory reservation across warehouses.
- Fine-tuning models.
- Image-based vector search in v1. Text-only semantic search is required; image embeddings may be a later extension.
- Production-grade fraud detection.

## 5. Recommended Technical Stack

This spec assumes a TypeScript-first application:

- Frontend: Next.js App Router, React, TypeScript.
- Backend: Next.js route handlers or a separate Node.js service if preferred.
- Auth: Auth.js/NextAuth-style provider model, or equivalent.
- Database: MongoDB Atlas.
- Vector search: MongoDB Atlas Vector Search.
- File/image hosting:
  - Demo default: serve imported images from the local MacBook filesystem through a backend static route or Next.js image route.
  - Optional deployment path: AWS S3 for shared demos or hosted environments.
- LLM client: internal provider adapter that can call OpenAI or Grove/Azure gateway.
- Embedding client: internal provider adapter that can call Ollama or MongoDB Atlas Voyage AI API.
- Mandatory complex-chat integration: MCP client connected to local OpenAI Codex MCP server for multi-step support workflows.

The implementation may choose another frontend framework, but the API, data model, provider contracts, and flows in this spec should remain stable.

## 6. User Roles

| Role | Description |
| --- | --- |
| Guest shopper | Can browse, search, view product details, and use anonymous cart. Must sign in before checkout. |
| Registered customer | Can save cart, checkout, view orders, request returns, and use authenticated assistant/support flows. |
| Support/admin operator | Demo-only role for viewing support tickets, return requests, order state, agent transcripts, and audit logs. |

## 7. Core User Journeys

### 7.1 Guest Product Discovery

1. User lands on the catalogue page.
2. User filters by gender, category, color, article type, season, price, and usage.
3. User searches with keyword or semantic search query.
4. User opens a product detail page.
5. User adds item to cart.

Acceptance criteria:

- Catalogue loads quickly with paginated results.
- Filters are shareable through URL query parameters.
- Empty states explain that no matching products were found and offer filter reset.
- Product cards show image, title, price, category, color, and quick add action.

### 7.2 Account Creation and Login

1. User can register with email and password.
2. User can sign in with email and password.
3. User can sign in with Google OAuth.
4. Guest cart merges into authenticated cart after login.
5. User can sign out.

Acceptance criteria:

- Passwords are hashed with Argon2id or bcrypt.
- OAuth account records are linked by verified email where safe.
- Sessions are HTTP-only secure cookies.
- Failed login attempts are rate limited.
- Duplicate email behavior is clear and safe.

### 7.3 Cart and Demo Checkout

1. User adds one or more products to cart.
2. User updates quantities and removes items.
3. User proceeds to checkout.
4. User enters or selects shipping address.
5. User selects demo payment method.
6. User places order.
7. System creates order, order items, synthetic payment record, and reduces available demo inventory if enabled.

Acceptance criteria:

- Checkout requires authentication.
- Prices are recalculated server-side.
- Client cannot modify authoritative price.
- Out-of-stock and quantity limit errors are handled.
- Order confirmation page shows order number, items, total, and expected delivery date.

### 7.4 Semantic Product Search

1. User enters natural language query, for example "lightweight black running shoes for men under 3000".
2. Backend embeds the query using configured embedding provider.
3. Backend runs MongoDB Atlas vector search with optional metadata filters.
4. Results are ranked by vector score and optionally blended with keyword/facet matches.
5. UI displays ranked products with active filters and sort controls.

Acceptance criteria:

- Search supports text query and filters together.
- Embedding provider is selected through environment/config.
- Query embeddings are not persisted unless explicitly enabled.
- Product embeddings are versioned by provider, model, dimension, and text-template version.
- Switching embedding provider requires reindexing/re-embedding products unless dimensions and embedding space are explicitly compatible.

### 7.5 Codex Shopping Assistant

1. User opens assistant from catalogue, product page, or cart.
2. Assistant can answer product questions, compare items, suggest products, explain fit/style/use cases, and add items to cart with user confirmation.
3. Assistant retrieves relevant products through semantic search and product APIs.
4. Assistant may read cart context for authenticated or anonymous sessions.
5. Assistant asks clarifying questions when intent is ambiguous.

Acceptance criteria:

- Assistant cannot place orders without explicit user confirmation through normal checkout.
- Assistant can call allowed tools only.
- All tool calls are logged.
- Assistant cites product facts from retrieved product records, not invented details.
- Assistant supports streaming responses when provider supports it.

### 7.6 Codex Returns and Support Agent

1. Authenticated customer opens support.
2. Agent can look up orders, explain order status, check return eligibility, create return requests, and create support tickets.
3. Agent can gather required return reason, item condition, and preferred resolution.
4. Agent can submit return request after user confirmation.
5. Agent can escalate to a support ticket for edge cases.

Acceptance criteria:

- Agent verifies user ownership of order before showing details.
- Agent cannot create returns outside configured policy unless it escalates.
- Agent logs decision path and tool calls.
- Return request has stable status: `requested`, `approved`, `rejected`, `label_created`, `received`, `refunded`, `cancelled`.
- Support ticket has priority, category, status, transcript link, and assigned owner.

## 8. Functional Requirements

### 8.1 Authentication and Identity

Required:

- Email/password registration.
- Email/password login.
- Google OAuth login.
- Password reset flow for custom credentials.
- Session management.
- Account linking rules.
- Profile page with name, email, avatar, addresses, and order history.

Recommended:

- Email verification for password accounts.
- MFA-ready user schema, even if MFA is not implemented in v1.
- Role-based access checks for admin/support pages.

Security requirements:

- Hash passwords with Argon2id preferred; bcrypt acceptable.
- Never store OAuth access tokens in plaintext if refresh is not required.
- Use CSRF protection for cookie-based auth.
- Use secure, HTTP-only, same-site cookies.
- Rate limit login, registration, password reset, and chat endpoints.

### 8.2 Product Catalogue

Required:

- Product listing page.
- Product detail page.
- Category/facet navigation.
- Sorting:
  - Relevance
  - Price low to high
  - Price high to low
  - Newest
  - Rating
- Filters:
  - Gender
  - Master category
  - Subcategory
  - Article type
  - Color
  - Season
  - Usage
  - Price range
  - Availability
- Pagination or infinite scroll.

Product detail page must show:

- Product image.
- Product title.
- Price and currency.
- Category hierarchy.
- Color.
- Size selector when applicable.
- Availability.
- Description.
- Return policy summary.
- Similar products.
- Add to cart.
- Ask assistant action.

### 8.3 Cart

Required:

- Anonymous cart stored by session ID.
- Authenticated cart stored by user ID.
- Merge anonymous cart into user cart on login.
- Add item.
- Update quantity.
- Remove item.
- Clear cart.
- Server-side subtotal/tax/shipping/total calculation.

Cart item identity:

- `productId`
- `variantId` if variants are created
- `size`
- `quantity`

### 8.4 Checkout

Required:

- Authenticated checkout.
- Shipping address form.
- Demo payment selection.
- Order review.
- Place order.
- Order confirmation.

Payment behavior:

- Use mock payment provider in v1.
- Store `paymentStatus` as `authorized` or `paid` for demo.
- Do not collect real card data.

Tax/shipping:

- Use deterministic demo calculations.
- Example:
  - Tax: configurable percentage.
  - Shipping: free above threshold; otherwise fixed fee.

### 8.5 Search

Required search modes:

- Keyword search against title, description, categories, tags, and color.
- Faceted filtered browse.
- Semantic search using embeddings and MongoDB Atlas Vector Search.
- Hybrid ranking mode.

Hybrid ranking recommendation:

- Run vector search for semantic candidates.
- Apply metadata filters inside or adjacent to vector search where supported.
- Optionally combine with Atlas Search text score.
- Normalize scores and produce a blended relevance score.

Query examples:

- "red casual shoes for women"
- "office wear for men"
- "summer backpack"
- "something sporty and black"
- "gift under 2000 for a college student"

### 8.6 Shopping Assistant

Capabilities:

- Product recommendation.
- Product comparison.
- Gift guidance.
- Outfit/use-case guidance.
- Cart-aware suggestions.
- Size/color clarification.
- Add-to-cart proposal.
- Explain why a product matches the query.

Allowed tools:

- `searchProducts(query, filters, limit)`
- `getProduct(productId)`
- `getSimilarProducts(productId, limit)`
- `getCart()`
- `addToCart(productId, quantity, variant)`
- `removeFromCart(cartItemId)`
- `updateCartItem(cartItemId, quantity)`
- `getUserPreferences()`
- `saveUserPreference(key, value)`

Tool safety:

- Mutating cart tools require assistant-level confirmation UX.
- Checkout and payment are not exposed as assistant tools in v1.
- The assistant may deep-link the user to checkout.

### 8.7 Returns and Support Agent

Capabilities:

- Order lookup.
- Return eligibility check.
- Return request creation.
- Refund estimate.
- Exchange recommendation.
- Support ticket creation.
- Policy explanation.
- Escalation summary.

Allowed tools:

- `listUserOrders(userId, filters)`
- `getOrder(orderId)`
- `getOrderItem(orderId, orderItemId)`
- `checkReturnEligibility(orderId, orderItemId)`
- `createReturnRequest(orderId, items, reason, resolution)`
- `createSupportTicket(category, priority, subject, body, orderId?)`
- `appendTicketMessage(ticketId, message)`
- `getReturnPolicy(policyCode)`

Tool safety:

- Agent must verify that the order belongs to the authenticated user.
- Agent must request explicit confirmation before creating a return or ticket.
- Agent must not promise refund timing beyond configured policy text.
- Agent must escalate unclear/damaged/warranty cases.

### 8.8 User Activity Capture

Required:

- Capture every product search with query, search mode, filters, sort, result count, and user/anonymous session.
- Capture every filter application and sort change.
- Capture product selections from catalogue cards, search results, assistant recommendations, and product detail views.
- Capture cart actions, including add, update quantity, remove, and clear cart.
- Capture checkout start and order placement.
- Capture return requests and support ticket creation.
- Store activity events in MongoDB Atlas through `userActivityEvents`.
- Associate events with `userId` when authenticated and `anonymousId` when not authenticated.
- Preserve enough metadata to reconstruct a demo funnel without storing secrets or payment-sensitive data.

Activity capture must be implemented server-side for authoritative events such as orders, returns, support tickets, and cart mutations. Client-side events may be used for browse behavior, but the backend should validate event shape before writing.

## 9. AI Provider Configuration

### 9.1 Design Principle

No application code should directly depend on a specific LLM or embedding provider. All AI calls go through provider interfaces:

- `LLMClient`
- `EmbeddingClient`
- `MCPComplexChatClient`

Provider choice is controlled by environment variables and runtime config.

### 9.2 LLM Providers

Supported LLM providers:

1. OpenAI API.
2. Grove/Azure gateway-compatible chat completions endpoint.

The user-requested OpenAI model default is `gpt-5.4`. The model string must remain configurable because actual account access and model IDs can vary.

OpenAI docs currently recommend the Responses API for new OpenAI-native projects, while Chat Completions remains available. This demo should use a Chat Completions-compatible adapter by default because the Grove endpoint is explicitly a `/chat/completions` endpoint and the user requirement names that shape.

LLM environment variables:

| Variable | Example | Required | Description |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | `openai` or `grove` | Yes | Selects provider. |
| `LLM_MODEL` | `gpt-5.4` | Yes | Model/deployment name sent to provider. |
| `LLM_API_BASE_URL` | `https://api.openai.com/v1` | Yes | Base URL for OpenAI-compatible provider. |
| `LLM_CHAT_COMPLETIONS_PATH` | `/chat/completions` | Yes | Path appended to base URL. |
| `LLM_API_KEY` | secret | Yes | Provider API key. |
| `LLM_ORGANIZATION_ID` | optional | No | OpenAI org header when needed. |
| `LLM_PROJECT_ID` | optional | No | OpenAI project header when needed. |
| `LLM_TIMEOUT_MS` | `60000` | Yes | Request timeout. |
| `LLM_MAX_OUTPUT_TOKENS` | `1200` | Yes | Default response budget. |
| `LLM_TEMPERATURE` | `0.3` | Yes | Default assistant temperature. |
| `LLM_STREAMING_ENABLED` | `true` | Yes | Enables streaming when supported. |

OpenAI default example:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_CHAT_COMPLETIONS_PATH=/chat/completions
LLM_API_KEY=...
```

Grove/Azure gateway default example:

```env
LLM_PROVIDER=grove
LLM_MODEL=gpt-5.4
LLM_API_BASE_URL=https://grove-gateway-prod.azure-api.net/grove-foundry-prod/openai/v1
LLM_CHAT_COMPLETIONS_PATH=/chat/completions
LLM_API_KEY=...
```

The exact Grove URL must be configurable and should not be hardcoded.

### 9.3 Embedding Providers

Supported embedding providers:

1. Ollama with `nomic-embed-text:v1.5`.
2. MongoDB Atlas Voyage AI API with `voyage-4`.

Embedding environment variables:

| Variable | Example | Required | Description |
| --- | --- | --- | --- |
| `EMBEDDING_PROVIDER` | `ollama` or `voyage_atlas` | Yes | Selects embedding provider. |
| `EMBEDDING_MODEL` | `nomic-embed-text:v1.5` or `voyage-4` | Yes | Model name. |
| `EMBEDDING_DIMENSIONS` | `768` or `1024` | Yes | Vector dimensions stored in Atlas index. |
| `EMBEDDING_TEXT_TEMPLATE_VERSION` | `product-v1` | Yes | Version of text template used for product embeddings. |
| `EMBEDDING_BATCH_SIZE` | `64` | Yes | Batch size for ingestion. |
| `EMBEDDING_TIMEOUT_MS` | `60000` | Yes | Provider timeout. |

Ollama-specific:

| Variable | Example | Required | Description |
| --- | --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Yes if Ollama | Ollama server URL. |
| `OLLAMA_EMBED_PATH` | `/api/embed` | Yes if Ollama | Embedding endpoint. |

Ollama example:

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text:v1.5
EMBEDDING_DIMENSIONS=768
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_PATH=/api/embed
```

Voyage/MongoDB Atlas API-specific:

| Variable | Example | Required | Description |
| --- | --- | --- | --- |
| `VOYAGE_API_BASE_URL` | provider URL from MongoDB Atlas docs/account | Yes if Voyage | Base URL for Voyage API. |
| `VOYAGE_API_KEY` | secret | Yes if Voyage | Model API key managed in Atlas. |
| `VOYAGE_INPUT_TYPE_DOCUMENT` | `document` | Yes if Voyage | Input type for product embeddings. |
| `VOYAGE_INPUT_TYPE_QUERY` | `query` | Yes if Voyage | Input type for search query embeddings. |

Voyage example:

```env
EMBEDDING_PROVIDER=voyage_atlas
EMBEDDING_MODEL=voyage-4
EMBEDDING_DIMENSIONS=1024
VOYAGE_API_BASE_URL=...
VOYAGE_API_KEY=...
VOYAGE_INPUT_TYPE_DOCUMENT=document
VOYAGE_INPUT_TYPE_QUERY=query
```

Important embedding rules:

- Store provider, model, dimensions, and text-template version with every product embedding.
- Product embeddings must be regenerated when:
  - provider changes,
  - model changes,
  - dimension changes,
  - product embedding text changes,
  - template version changes.
- Atlas vector index dimensions must match stored embedding dimensions.
- Keep separate vector indexes if supporting multiple embedding models side by side.

### 9.4 Local Codex MCP Server for Complex Chats

Purpose:

- The local OpenAI Codex MCP server is mandatory for complex, multi-step support chat workflows.
- Use the local OpenAI Codex MCP server when a chat needs deeper multi-step reasoning, structured tool use, long-context support history, or return/refund workflow orchestration.
- Keep normal shopping interactions and short support answers available through the standard LLM adapter, but complex support flows must route through MCP.

Config:

| Variable | Example | Required | Description |
| --- | --- | --- | --- |
| `CODEX_MCP_ENABLED` | `true` | Yes | Must be `true` for demo readiness; enables MCP complex-chat routing. |
| `CODEX_MCP_TRANSPORT` | `stdio`, `sse`, or `streamable_http` | Yes | MCP transport mode. |
| `CODEX_MCP_COMMAND` | `codex` | Required for stdio | Local command to start server. |
| `CODEX_MCP_ARGS` | `mcp,serve` | Required for stdio | Command args as comma-separated list or JSON array. |
| `CODEX_MCP_URL` | `http://localhost:.../mcp` | Required for HTTP/SSE | Local MCP server URL. |
| `CODEX_MCP_TIMEOUT_MS` | `120000` | Yes | Timeout for complex tasks. |

Routing policy:

- Use regular `LLMClient` for product Q&A, recommendation, and short support answers.
- Use `MCPComplexChatClient` when:
  - user asks multi-step or ambiguous support questions,
  - return eligibility requires several tool calls,
  - agent needs to summarize long order/support history,
  - standard LLM adapter returns a low-confidence handoff signal,
  - admin explicitly asks for complex agent mode.
- The demo health check must fail if MCP is configured as unavailable or disabled.

The MCP integration must not expose filesystem, shell, or developer tools to end users unless explicitly scoped and sandboxed. For this ecommerce demo, MCP tools should be limited to ecommerce application tools registered by the backend.

## 10. Data Model

Use MongoDB ObjectIds for internal IDs and keep dataset IDs as `sourceProductId`.

### 10.1 `users`

```json
{
  "_id": "ObjectId",
  "email": "user@example.com",
  "emailVerified": true,
  "name": "Asha Kumar",
  "image": "https://...",
  "passwordHash": "...",
  "roles": ["customer"],
  "preferences": {
    "gender": "Women",
    "sizes": ["M"],
    "colors": ["Black", "Blue"]
  },
  "createdAt": "ISODate",
  "updatedAt": "ISODate",
  "lastLoginAt": "ISODate"
}
```

Indexes:

- Unique `email`.
- `roles`.

### 10.2 `authAccounts`

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "provider": "google",
  "providerAccountId": "...",
  "accessTokenEncrypted": "...",
  "refreshTokenEncrypted": "...",
  "expiresAt": "ISODate",
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique compound `provider`, `providerAccountId`.
- `userId`.

### 10.3 `sessions`

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "sessionTokenHash": "...",
  "expiresAt": "ISODate",
  "createdAt": "ISODate"
}
```

Indexes:

- Unique `sessionTokenHash`.
- TTL on `expiresAt`.

### 10.4 `products`

```json
{
  "_id": "ObjectId",
  "source": "kaggle-fashion-product-images",
  "sourceProductId": "42431",
  "slug": "men-black-running-shoes-42431",
  "title": "Men Black Running Shoes",
  "description": "Synthetic demo description...",
  "brand": "DemoFit",
  "gender": "Men",
  "masterCategory": "Footwear",
  "subCategory": "Shoes",
  "articleType": "Sports Shoes",
  "baseColour": "Black",
  "season": "Summer",
  "year": 2012,
  "usage": "Sports",
  "price": {
    "amount": 2499,
    "currency": "INR"
  },
  "inventory": {
    "available": 42,
    "reserved": 0,
    "trackInventory": true
  },
  "images": [
    {
      "url": "/product-images/42431.jpg",
      "alt": "Men Black Running Shoes",
      "sourcePath": "images/42431.jpg",
      "isPrimary": true
    }
  ],
  "attributes": {
    "careInstructions": "Wipe with clean dry cloth",
    "material": "Synthetic",
    "fit": "Regular"
  },
  "tags": ["men", "black", "sports", "shoes"],
  "ratingAverage": 4.2,
  "ratingCount": 128,
  "returnPolicyCode": "standard-30-day",
  "isActive": true,
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique compound `source`, `sourceProductId`.
- Unique `slug`.
- Compound filter indexes:
  - `isActive`, `masterCategory`, `subCategory`
  - `isActive`, `gender`
  - `isActive`, `articleType`
  - `isActive`, `baseColour`
  - `isActive`, `price.amount`
- Text/search index for keyword search.

### 10.5 `productEmbeddings`

Use a separate collection to support multiple providers/models side by side.

```json
{
  "_id": "ObjectId",
  "productId": "ObjectId",
  "sourceProductId": "42431",
  "provider": "ollama",
  "model": "nomic-embed-text:v1.5",
  "dimensions": 768,
  "textTemplateVersion": "product-v1",
  "embeddingTextHash": "sha256...",
  "embedding": [0.0123, -0.0456],
  "metadata": {
    "gender": "Men",
    "masterCategory": "Footwear",
    "subCategory": "Shoes",
    "articleType": "Sports Shoes",
    "baseColour": "Black",
    "usage": "Sports",
    "priceAmount": 2499,
    "isActive": true
  },
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique compound `productId`, `provider`, `model`, `dimensions`, `textTemplateVersion`.
- `provider`, `model`, `dimensions`, `textTemplateVersion`.
- Metadata filter indexes as needed.
- Atlas Vector Search index on `embedding`.

Example Atlas vector index for 768-dimensional Ollama/Nomic:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 768,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "provider"
    },
    {
      "type": "filter",
      "path": "model"
    },
    {
      "type": "filter",
      "path": "metadata.masterCategory"
    },
    {
      "type": "filter",
      "path": "metadata.gender"
    },
    {
      "type": "filter",
      "path": "metadata.baseColour"
    }
  ]
}
```

Example Atlas vector index for 1024-dimensional Voyage:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1024,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "provider"
    },
    {
      "type": "filter",
      "path": "model"
    },
    {
      "type": "filter",
      "path": "metadata.masterCategory"
    },
    {
      "type": "filter",
      "path": "metadata.gender"
    },
    {
      "type": "filter",
      "path": "metadata.baseColour"
    }
  ]
}
```

### 10.6 `carts`

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "anonymousId": "uuid",
  "status": "active",
  "items": [
    {
      "cartItemId": "uuid",
      "productId": "ObjectId",
      "sourceProductId": "42431",
      "titleSnapshot": "Men Black Running Shoes",
      "priceSnapshot": {
        "amount": 2499,
        "currency": "INR"
      },
      "size": "9",
      "quantity": 1,
      "addedAt": "ISODate",
      "updatedAt": "ISODate"
    }
  ],
  "totals": {
    "subtotal": 2499,
    "tax": 450,
    "shipping": 0,
    "discount": 0,
    "grandTotal": 2949,
    "currency": "INR"
  },
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- `userId`, `status`.
- `anonymousId`, `status`.

### 10.7 `orders`

```json
{
  "_id": "ObjectId",
  "orderNumber": "ORD-20260502-000001",
  "userId": "ObjectId",
  "status": "confirmed",
  "items": [
    {
      "orderItemId": "uuid",
      "productId": "ObjectId",
      "sourceProductId": "42431",
      "titleSnapshot": "Men Black Running Shoes",
      "imageUrlSnapshot": "/product-images/42431.jpg",
      "size": "9",
      "quantity": 1,
      "unitPrice": {
        "amount": 2499,
        "currency": "INR"
      },
      "returnStatus": "eligible"
    }
  ],
  "shippingAddress": {
    "name": "Asha Kumar",
    "line1": "Demo address",
    "line2": "",
    "city": "Bengaluru",
    "region": "KA",
    "postalCode": "560001",
    "country": "IN",
    "phone": "+91..."
  },
  "totals": {
    "subtotal": 2499,
    "tax": 450,
    "shipping": 0,
    "discount": 0,
    "grandTotal": 2949,
    "currency": "INR"
  },
  "payment": {
    "provider": "demo",
    "status": "paid",
    "transactionId": "demo_txn_..."
  },
  "placedAt": "ISODate",
  "estimatedDeliveryAt": "ISODate",
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique `orderNumber`.
- `userId`, `placedAt`.
- `status`.

### 10.8 `returnRequests`

```json
{
  "_id": "ObjectId",
  "returnNumber": "RET-20260502-000001",
  "userId": "ObjectId",
  "orderId": "ObjectId",
  "orderNumber": "ORD-20260502-000001",
  "items": [
    {
      "orderItemId": "uuid",
      "productId": "ObjectId",
      "quantity": 1,
      "reason": "Size issue",
      "condition": "Unused",
      "resolution": "refund"
    }
  ],
  "status": "requested",
  "eligibility": {
    "eligible": true,
    "policyCode": "standard-30-day",
    "returnWindowEndsAt": "ISODate"
  },
  "agentSessionId": "ObjectId",
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique `returnNumber`.
- `userId`, `createdAt`.
- `orderId`.
- `status`.

### 10.9 `supportTickets`

```json
{
  "_id": "ObjectId",
  "ticketNumber": "SUP-20260502-000001",
  "userId": "ObjectId",
  "orderId": "ObjectId",
  "category": "returns",
  "priority": "normal",
  "subject": "Need help with return",
  "status": "open",
  "messages": [
    {
      "senderType": "customer",
      "message": "I need help returning this item.",
      "createdAt": "ISODate"
    }
  ],
  "agentSessionId": "ObjectId",
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

Indexes:

- Unique `ticketNumber`.
- `userId`, `createdAt`.
- `status`, `priority`.

### 10.10 `chatSessions`

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "anonymousId": "uuid",
  "type": "shopping_assistant",
  "status": "active",
  "provider": "openai",
  "model": "gpt-5.4",
  "usedMcp": false,
  "metadata": {
    "entryPoint": "product_detail",
    "productId": "ObjectId"
  },
  "createdAt": "ISODate",
  "updatedAt": "ISODate"
}
```

### 10.11 `chatMessages`

```json
{
  "_id": "ObjectId",
  "sessionId": "ObjectId",
  "role": "user",
  "content": "I need black running shoes.",
  "toolCalls": [],
  "tokenUsage": {
    "inputTokens": 100,
    "outputTokens": 200
  },
  "createdAt": "ISODate"
}
```

Indexes:

- `sessionId`, `createdAt`.

### 10.12 `agentToolAuditLogs`

```json
{
  "_id": "ObjectId",
  "sessionId": "ObjectId",
  "userId": "ObjectId",
  "agentType": "returns_support",
  "toolName": "createReturnRequest",
  "input": {},
  "output": {},
  "status": "success",
  "requiresUserConfirmation": true,
  "confirmedAt": "ISODate",
  "createdAt": "ISODate"
}
```

Indexes:

- `sessionId`, `createdAt`.
- `userId`, `createdAt`.
- `toolName`, `status`.

### 10.13 `userActivityEvents`

Capture user behavior for analytics, personalization, support context, and demo reporting.

```json
{
  "_id": "ObjectId",
  "userId": "ObjectId",
  "anonymousId": "uuid",
  "sessionId": "uuid",
  "eventType": "search_performed",
  "eventSource": "web",
  "occurredAt": "ISODate",
  "metadata": {
    "query": "black running shoes",
    "searchMode": "semantic",
    "filters": {
      "gender": ["Men"],
      "baseColour": ["Black"],
      "priceMax": 3000
    },
    "productId": "ObjectId",
    "sourceProductId": "42431",
    "orderId": "ObjectId",
    "cartId": "ObjectId"
  },
  "requestId": "req_...",
  "createdAt": "ISODate"
}
```

Required event types:

- `search_performed`
- `filter_applied`
- `sort_changed`
- `product_card_clicked`
- `product_detail_viewed`
- `assistant_opened`
- `assistant_product_recommended`
- `cart_item_added`
- `cart_item_updated`
- `cart_item_removed`
- `checkout_started`
- `order_placed`
- `return_requested`
- `support_ticket_created`

Indexes:

- `userId`, `occurredAt`.
- `anonymousId`, `occurredAt`.
- `eventType`, `occurredAt`.
- `metadata.productId`, `occurredAt`.
- `metadata.orderId`, `occurredAt`.

## 11. Product Ingestion Pipeline

### 11.1 Inputs

Expected local dataset directory:

```text
data/fashion-product-images/
  styles.csv
  images/
    42431.jpg
  styles/
    42431.json
```

### 11.2 Pipeline Stages

1. Validate dataset structure.
2. Parse `styles.csv`.
3. Normalize fields and skip malformed records.
4. Join optional `styles/<id>.json` metadata when present.
5. Register local filesystem image paths and produce public image URLs through the app image route.
6. Synthesize ecommerce fields deterministically.
7. Upsert `products`.
8. Build embedding text for each active product.
9. Generate embeddings with configured embedding provider.
10. Upsert `productEmbeddings`.
11. Build or validate Atlas vector indexes.
12. Emit ingestion report.

### 11.3 Product Embedding Text Template

Template version: `product-v1`

```text
Title: {title}
Description: {description}
Brand: {brand}
Gender: {gender}
Category: {masterCategory} > {subCategory} > {articleType}
Color: {baseColour}
Season: {season}
Usage: {usage}
Price: {price.amount} {price.currency}
Tags: {tags}
```

Provider-specific prefixes:

- Nomic/Ollama:
  - Documents: prefix text with `search_document: `
  - Queries: prefix user search with `search_query: `
- Voyage:
  - Use provider `input_type=document` for products.
  - Use provider `input_type=query` for search queries.

### 11.4 Ingestion CLI Commands

Recommended commands:

```bash
npm run ingest:products -- --dataset ./data/fashion-product-images
npm run embeddings:generate -- --provider $EMBEDDING_PROVIDER --model $EMBEDDING_MODEL
npm run search:index:validate
```

Ingestion report fields:

- Dataset path.
- Products read.
- Products skipped.
- Products inserted.
- Products updated.
- Images missing.
- Embeddings generated.
- Embeddings skipped as unchanged.
- Provider/model/dimensions/template version.
- Duration.

## 12. API Surface

All API responses should use a consistent envelope:

```json
{
  "data": {},
  "error": null,
  "meta": {}
}
```

Error example:

```json
{
  "data": null,
  "error": {
    "code": "PRODUCT_NOT_FOUND",
    "message": "Product not found"
  },
  "meta": {
    "requestId": "req_..."
  }
}
```

### 12.1 Auth

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/auth/register` | Create password account. |
| `POST` | `/api/auth/login` | Login with email/password. |
| `POST` | `/api/auth/logout` | End session. |
| `GET` | `/api/auth/google/start` | Start Google OAuth. |
| `GET` | `/api/auth/google/callback` | Complete Google OAuth. |
| `POST` | `/api/auth/password-reset/request` | Request reset link. |
| `POST` | `/api/auth/password-reset/confirm` | Set new password. |
| `GET` | `/api/me` | Current user profile. |

### 12.2 Products and Search

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/products` | Product listing with filters and pagination. |
| `GET` | `/api/products/:slug` | Product detail. |
| `GET` | `/api/products/:id/similar` | Similar products. |
| `GET` | `/api/facets` | Available filter facets. |
| `POST` | `/api/search/semantic` | Semantic product search. |
| `POST` | `/api/search/hybrid` | Hybrid keyword/vector search. |

Semantic search request:

```json
{
  "query": "black shoes for running",
  "filters": {
    "gender": ["Men"],
    "priceMax": 3000
  },
  "limit": 24,
  "page": 1
}
```

Semantic search response:

```json
{
  "data": {
    "results": [
      {
        "product": {},
        "score": 0.87,
        "matchReason": "Matches running, black color, footwear category"
      }
    ]
  },
  "error": null,
  "meta": {
    "provider": "ollama",
    "model": "nomic-embed-text:v1.5",
    "dimensions": 768
  }
}
```

### 12.3 Cart

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/cart` | Get current cart. |
| `POST` | `/api/cart/items` | Add cart item. |
| `PATCH` | `/api/cart/items/:cartItemId` | Update quantity/variant. |
| `DELETE` | `/api/cart/items/:cartItemId` | Remove item. |
| `POST` | `/api/cart/merge` | Merge anonymous cart after login. |
| `DELETE` | `/api/cart` | Clear cart. |

### 12.4 Checkout and Orders

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/checkout/quote` | Calculate totals. |
| `POST` | `/api/checkout/place-order` | Place demo order. |
| `GET` | `/api/orders` | List user orders. |
| `GET` | `/api/orders/:orderNumber` | Order detail. |

### 12.5 Returns and Support

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/returns/check-eligibility` | Check return eligibility. |
| `POST` | `/api/returns` | Create return request. |
| `GET` | `/api/returns` | List user returns. |
| `GET` | `/api/returns/:returnNumber` | Return detail. |
| `POST` | `/api/support/tickets` | Create ticket. |
| `GET` | `/api/support/tickets` | List tickets. |
| `GET` | `/api/support/tickets/:ticketNumber` | Ticket detail. |
| `POST` | `/api/support/tickets/:ticketNumber/messages` | Add ticket message. |

### 12.6 AI Chat

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/assistant/shopping/sessions` | Start shopping assistant session. |
| `POST` | `/api/assistant/shopping/messages` | Send shopping assistant message. |
| `POST` | `/api/assistant/support/sessions` | Start support session. |
| `POST` | `/api/assistant/support/messages` | Send support message. |
| `POST` | `/api/assistant/actions/confirm` | Confirm pending mutating action. |

Chat message request:

```json
{
  "sessionId": "session_id",
  "message": "Can you find black casual sneakers under 3000?",
  "context": {
    "currentProductId": "optional",
    "cartAware": true
  }
}
```

Chat response:

```json
{
  "data": {
    "message": "Here are three options...",
    "suggestedProducts": [],
    "pendingAction": {
      "id": "action_id",
      "type": "add_to_cart",
      "label": "Add Men Black Sneakers to cart"
    }
  },
  "error": null,
  "meta": {
    "provider": "openai",
    "model": "gpt-5.4",
    "usedMcp": false
  }
}
```

## 13. UI Requirements

### 13.1 Pages

| Page | Route | Required Content |
| --- | --- | --- |
| Catalogue | `/products` | Filters, search, product grid, sorting, pagination. |
| Product detail | `/products/[slug]` | Product info, add to cart, similar products, assistant entry. |
| Login | `/login` | Email/password login, Google login, register link. |
| Register | `/register` | Account creation. |
| Cart | `/cart` | Cart items, totals, checkout CTA. |
| Checkout | `/checkout` | Address, demo payment, review, place order. |
| Order confirmation | `/orders/[orderNumber]` | Order summary and support CTA. |
| Orders | `/account/orders` | Order history. |
| Returns | `/account/returns` | Return history. |
| Support | `/support` | Support agent chat and tickets. |
| Admin demo console | `/admin` | Ingestion status, provider config display, tickets, audit logs. |

### 13.2 Global UI

Required:

- Header with brand, search bar, auth state, cart icon.
- Responsive layout for desktop and mobile.
- Assistant launcher.
- Loading, error, and empty states.
- Product image fallback.
- Toasts for cart and support actions.

### 13.3 Assistant UI

Required:

- Floating chat panel or side drawer.
- Streaming response display when enabled.
- Suggested product cards inside chat.
- Confirm/cancel controls for mutating actions.
- Clear indicator when support agent is viewing order/return context.

The UI must never claim the agent has completed an order, refund, or return until the backend action succeeds.

## 14. Agent Design

### 14.1 Common System Rules

All agents:

- Must stay within ecommerce domain.
- Must use tools for product/order facts.
- Must not invent product availability, order status, refund timing, or policy details.
- Must ask clarifying questions when required fields are missing.
- Must request confirmation before mutating state.
- Must produce concise, helpful responses.
- Must write tool-call audit logs.

### 14.2 Shopping Assistant Prompt Contract

High-level behavior:

- Be a helpful fashion shopping assistant.
- Prefer retrieved product facts.
- Recommend no more than 5 products at once unless user asks for more.
- Explain matches using concrete attributes.
- Use filters inferred from user language.
- Ask follow-up questions for size, budget, gender, or use case when needed.

Tool-first rules:

- If user asks for product recommendations, call `searchProducts`.
- If user asks about a specific product, call `getProduct`.
- If user asks for alternatives, call `getSimilarProducts`.
- If user wants to add to cart, summarize item and ask for confirmation before calling `addToCart`.

### 14.3 Returns and Support Agent Prompt Contract

High-level behavior:

- Be clear, calm, and policy-grounded.
- Verify authenticated user context.
- Use order tools before discussing order-specific details.
- Use return policy tools before saying an item is eligible or ineligible.
- Provide escalation path if policy is unclear.

Tool-first rules:

- If user asks about an order, call `listUserOrders` or `getOrder`.
- If user asks to return an item, call `checkReturnEligibility`.
- Before creating return, confirm item, reason, condition, and requested resolution.
- If creating ticket, confirm subject/category before tool call.

### 14.4 MCP Complex Chat

Complex chat sessions should run as an orchestration layer:

1. Receive user message and context.
2. Decide if standard LLM path is sufficient.
3. If complex support mode is needed, invoke the mandatory local Codex MCP server.
4. Expose only ecommerce tool contracts.
5. Return a normalized assistant response to frontend.
6. Persist transcript, tool calls, and MCP usage metadata.

Fallback:

- If MCP server is unavailable, the application must show a demo readiness error for complex support flows and create a support ticket when user-facing continuity is needed.
- MCP unavailability should be treated as a failed health check, not an optional feature toggle.

## 15. MongoDB Atlas Search Design

### 15.1 Keyword Search

Create Atlas Search index over:

- `title`
- `description`
- `brand`
- `masterCategory`
- `subCategory`
- `articleType`
- `baseColour`
- `usage`
- `tags`

Keyword search should support:

- Fuzzy matching.
- Autocomplete on product title and categories.
- Facet filters.

### 15.2 Vector Search

Use MongoDB Atlas Vector Search with current `vector` index type and `vectorSearch` operator.

General aggregation shape:

```javascript
[
  {
    $vectorSearch: {
      index: "product_embeddings_ollama_768",
      path: "embedding",
      queryVector: queryEmbedding,
      numCandidates: 200,
      limit: 24,
      filter: {
        provider: "ollama",
        model: "nomic-embed-text:v1.5",
        "metadata.isActive": true
      }
    }
  },
  {
    $project: {
      productId: 1,
      score: { $meta: "vectorSearchScore" },
      metadata: 1
    }
  }
]
```

Then join product records by `productId` and apply additional business filters if needed.

### 15.3 Hybrid Search

Hybrid search should support two approaches:

1. Simple v1:
   - Run semantic search.
   - Run keyword search.
   - Merge, dedupe, normalize scores, and rerank in application code.
2. Enhanced:
   - Use Atlas Search and Vector Search pipelines with reciprocal rank fusion or weighted scoring.

Recommended initial weights:

- Semantic score: 0.70
- Keyword score: 0.20
- Popularity/rating score: 0.10

## 16. Return Policy Rules

Demo policy: `standard-30-day`

Rules:

- Return window: 30 days from delivered date, or from placed date if delivery event is not modeled.
- Eligible states: `delivered`, `confirmed` for demo mode.
- Ineligible:
  - Item already returned.
  - Return window expired.
  - Quantity exceeds ordered quantity minus already returned quantity.
  - Product marked final sale.
- Resolutions:
  - Refund.
  - Exchange.
  - Store credit.

Agent must show the reason when ineligible.

## 17. Security and Compliance

Required:

- Store secrets only in environment variables or secret manager.
- Never expose provider API keys to browser.
- Sanitize all user inputs.
- Validate all API inputs with schema validation.
- Rate limit auth and AI endpoints.
- Use user ownership checks for orders, returns, tickets, carts, and chat sessions.
- Encrypt sensitive OAuth tokens if stored.
- Redact secrets from logs.
- Log request IDs for traceability.

AI-specific:

- Guard against prompt injection in product descriptions and support messages.
- Treat retrieved product/order data as untrusted context.
- Tool calls must be schema-validated.
- Mutating tools require confirmation tokens.
- Agent cannot call admin-only tools unless user has admin role.

## 18. Observability

Required logs:

- Request ID.
- User ID or anonymous ID.
- Auth events.
- Cart/order events.
- User activity events for all searches, applied filters, product selections, cart changes, checkout starts, orders, returns, and support tickets.
- Search query metadata, excluding sensitive raw data where configured.
- Embedding provider, model, dimensions, latency.
- LLM provider, model, latency, token usage.
- Agent tool calls and outcomes.
- MCP usage, readiness failures, and complex support routing events.

Metrics:

- Catalogue latency.
- Search latency.
- Embedding generation throughput.
- LLM latency and error rate by provider.
- Cart conversion.
- Checkout success rate.
- Agent sessions by type.
- Return request creation count.
- User activity events by type and funnel stage.
- MCP complex-chat success/failure rate.

Admin demo console should display:

- Active provider config excluding secrets.
- Dataset ingestion status.
- Product count.
- Embedding count by provider/model/dimension.
- Recent AI failures.
- Recent support tickets and returns.
- Recent user activity events and conversion funnel summary.
- MCP server readiness status.

## 19. Testing Strategy

### 19.1 Unit Tests

- Product normalization.
- Synthetic price/inventory generation.
- Embedding text generation.
- Provider selection.
- Cart total calculation.
- Return eligibility.
- Tool authorization.
- Agent action confirmation logic.

### 19.2 Integration Tests

- Auth registration and login.
- Google OAuth callback with mocked provider.
- Product ingestion with sample dataset subset.
- Semantic search with mocked embedding provider.
- Cart merge on login.
- Checkout order creation.
- Return request creation.
- Support ticket creation.
- LLM provider adapter with mocked OpenAI-compatible endpoint.

### 19.3 End-to-End Tests

Critical flows:

- Guest browse -> search -> product detail -> add cart -> login -> checkout.
- Semantic search query -> filtered products.
- Shopping assistant recommends product -> user confirms add to cart.
- User views order -> support agent creates return request.
- Complex support chat routes through mocked local MCP server.
- MCP unavailable state fails health check and blocks complex support demo readiness.
- Searches, filters, product selections, cart actions, and orders create user activity events.

### 19.4 Load/Scale Demo Checks

- Catalogue can page through 44k products.
- Ingestion can resume after failure.
- Embedding generation can skip unchanged products.
- Search returns within demo target latency:
  - Keyword: under 500 ms server-side.
  - Vector: under 1200 ms server-side.
  - AI chat first token: under 5 seconds when streaming provider supports it.

## 20. Configuration Reference

```env
# App
APP_ENV=development
APP_BASE_URL=http://localhost:3000
SESSION_SECRET=...
COOKIE_SECURE=false

# MongoDB
MONGODB_URI=...
MONGODB_DB=ecommerce_demo
MONGODB_VECTOR_INDEX_NAME=product_embeddings_ollama_768

# Auth
AUTH_PASSWORD_ENABLED=true
AUTH_GOOGLE_ENABLED=true
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
PASSWORD_HASH_ALGORITHM=argon2id

# Dataset
DATASET_NAME=kaggle-fashion-product-images
DATASET_PATH=./data/fashion-product-images
PRODUCT_IMAGE_STORAGE=local_filesystem
PRODUCT_IMAGE_LOCAL_ROOT=./data/fashion-product-images/images
PRODUCT_IMAGE_PUBLIC_BASE_URL=/product-images
# Optional hosted image storage
# PRODUCT_IMAGE_STORAGE=s3
# AWS_S3_BUCKET=...
# AWS_REGION=...
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...

# LLM
LLM_PROVIDER=openai
LLM_MODEL=gpt-5.4
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_CHAT_COMPLETIONS_PATH=/chat/completions
LLM_API_KEY=...
LLM_TIMEOUT_MS=60000
LLM_MAX_OUTPUT_TOKENS=1200
LLM_TEMPERATURE=0.3
LLM_STREAMING_ENABLED=true

# Grove alternate
# LLM_PROVIDER=grove
# LLM_API_BASE_URL=https://grove-gateway-prod.azure-api.net/grove-foundry-prod/openai/v1
# LLM_CHAT_COMPLETIONS_PATH=/chat/completions

# Embeddings
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text:v1.5
EMBEDDING_DIMENSIONS=768
EMBEDDING_TEXT_TEMPLATE_VERSION=product-v1
EMBEDDING_BATCH_SIZE=64
EMBEDDING_TIMEOUT_MS=60000

# Ollama embeddings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_PATH=/api/embed

# Voyage/MongoDB Atlas embeddings
VOYAGE_API_BASE_URL=...
VOYAGE_API_KEY=...
VOYAGE_INPUT_TYPE_DOCUMENT=document
VOYAGE_INPUT_TYPE_QUERY=query

# Codex MCP
CODEX_MCP_ENABLED=true
CODEX_MCP_TRANSPORT=stdio
CODEX_MCP_COMMAND=codex
CODEX_MCP_ARGS=mcp,serve
CODEX_MCP_URL=http://localhost:9000/mcp
CODEX_MCP_TIMEOUT_MS=120000

# Demo checkout
CHECKOUT_PAYMENT_PROVIDER=demo
DEMO_TAX_PERCENT=18
DEMO_FREE_SHIPPING_THRESHOLD=3000
DEMO_SHIPPING_FEE=99

# Rate limits
RATE_LIMIT_AUTH_PER_MINUTE=10
RATE_LIMIT_SEARCH_PER_MINUTE=60
RATE_LIMIT_CHAT_PER_MINUTE=20
```

## 21. Delivery Plan

### Phase 1: Foundation

- Set up app shell, routing, styling, and MongoDB connection.
- Implement auth with password and Google.
- Create user/session/account collections.
- Build basic admin config page.

Exit criteria:

- User can register, log in, log out, and view profile.
- Google login works in development.
- MongoDB health check works.

### Phase 2: Product Ingestion and Catalogue

- Implement dataset ingestion.
- Normalize product fields.
- Serve product images.
- Create catalogue and product detail pages.
- Add keyword search and filters.

Exit criteria:

- At least 1,000 products imported for local development.
- Full dataset import can run for demo/staging.
- Catalogue filters and product detail pages work.

### Phase 3: Cart and Checkout

- Implement anonymous and authenticated carts.
- Implement cart merge.
- Implement checkout quote and order creation.
- Implement order history.

Exit criteria:

- Guest can add to cart.
- User can log in and retain cart.
- User can place demo order.

### Phase 4: Semantic Search

- Implement embedding provider abstraction.
- Implement Ollama/Nomic adapter.
- Implement Voyage/MongoDB Atlas adapter.
- Generate product embeddings.
- Create Atlas vector indexes.
- Implement semantic and hybrid search APIs/UI.

Exit criteria:

- Search provider can be switched with config.
- Semantic search returns relevant products.
- Admin console shows embedding counts.

### Phase 5: Shopping Assistant

- Implement LLM provider abstraction.
- Implement OpenAI-compatible chat completions adapter.
- Implement Grove URL config support.
- Implement shopping assistant tools.
- Add assistant UI with product cards and cart confirmation.

Exit criteria:

- Assistant can recommend products from search.
- Assistant can add to cart after user confirmation.
- Tool calls are audited.

### Phase 6: Returns and Support Agent

- Implement returns model and support tickets.
- Implement support agent tools.
- Implement return policy engine.
- Add support UI.

Exit criteria:

- User can request return through agent.
- User can create support ticket through agent.
- Agent respects ownership and policy rules.

### Phase 7: Codex MCP Complex Chat

- Implement MCP client wrapper.
- Register ecommerce-safe tools.
- Add routing policy for complex support chats.
- Add health checks and readiness failure handling for MCP unavailability.
- Ensure complex support workflows require MCP.

Exit criteria:

- MCP-enabled complex support flow works locally.
- MCP unavailable path fails demo readiness checks and creates a support ticket for affected user flows.
- MCP usage is visible in transcript metadata.

### Phase 8: Hardening and Demo Polish

- Add tests.
- Add observability.
- Improve error states.
- Create seed/demo script.
- Add README and runbook.

Exit criteria:

- E2E critical paths pass.
- Demo can be reset and reseeded.
- Provider switching is documented and tested.

## 22. Acceptance Checklist

- Auth supports password and Google login.
- Products imported from Kaggle dataset.
- Catalogue supports filters, sort, pagination, and detail pages.
- Cart supports anonymous and authenticated usage.
- Checkout creates demo orders.
- Semantic search works with Ollama/Nomic.
- Semantic search works with Voyage/MongoDB Atlas API.
- Embedding model/provider/dimensions are configurable.
- LLM provider/model/base URL are configurable.
- Grove endpoint can be configured without code changes.
- Shopping assistant can retrieve products and modify cart after confirmation.
- Returns/support agent can create return requests and support tickets after confirmation.
- MongoDB Atlas stores core data and vector embeddings.
- Local Codex MCP server integration is mandatory and operational for complex support chats.
- User activity capture records searches, filters, product selections, cart actions, checkout starts, orders, returns, and support tickets.
- Product images are served from the local MacBook filesystem for the demo, with optional AWS S3 support for hosted environments.
- Tool calls, agent actions, and provider metadata are audited.
- Tests cover core business logic and demo flows.

## 23. Open Questions

- Should the demo currency default to INR, USD, or be configurable per deployment? Developer Answer: INR
- Should optional AWS S3 image hosting be included in the first implementation or deferred until hosted demos?
- Should the first implementation use Next.js route handlers only, or split backend into a separate API service?
- What exact local Codex MCP server command/transport should be used in the target environment?
- Should Google OAuth be available in local development, or only in shared demo environments?
- Should support/admin console require a separate admin seed user?

## 24. External References

- Kaggle Fashion Product Images Dataset: https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-dataset
- MongoDB Atlas Vector Search overview: https://www.mongodb.com/docs/atlas/atlas-vector-search/vector-search-overview/
- MongoDB Atlas vector index field mapping: https://www.mongodb.com/docs/atlas/atlas-search/define-field-mappings-for-vector-search/
- MongoDB Voyage AI API overview: https://www.mongodb.com/docs/voyageai/api-reference/overview/
- MongoDB Voyage AI model overview: https://www.mongodb.com/docs/voyageai/models/
- Ollama `nomic-embed-text`: https://ollama.com/library/nomic-embed-text
- Ollama embeddings docs: https://docs.ollama.com/capabilities/embeddings
- Nomic `nomic-embed-text-v1.5` model card: https://huggingface.co/nomic-ai/nomic-embed-text-v1.5
- OpenAI Chat Completions API reference: https://platform.openai.com/docs/api-reference/chat/create
- OpenAI text generation guide: https://platform.openai.com/docs/guides/chat-completions
