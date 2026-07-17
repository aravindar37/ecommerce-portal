export interface ApiEnvelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
  meta: Record<string, unknown>;
}

export interface ProductPrice {
  amount: number;
  currency: string;
  listAmount?: number | null;
}

export interface ProductImage {
  url: string;
  alt: string;
  isLocalFileAvailable?: boolean;
}

export interface Product {
  _id: string;
  sourceProductId: string;
  slug: string;
  title: string;
  description?: string;
  brand?: string;
  gender: string;
  masterCategory: string;
  subCategory: string;
  articleType: string;
  baseColour: string;
  season?: string | null;
  usage?: string | null;
  price: ProductPrice;
  images: ProductImage[];
  inventory: { available: number; reserved: number; trackInventory: boolean };
  returnPolicyCode?: string;
  ratingAverage?: number;
  ratingCount?: number;
  tags?: string[];
}

export interface ProductList {
  items: Product[];
  total: number;
  page: number;
  limit: number;
}

export interface ProductFacetValue {
  value: string;
  count: number;
}

export interface ProductFacets {
  gender: ProductFacetValue[];
  masterCategory: ProductFacetValue[];
  subCategory: ProductFacetValue[];
  articleType: ProductFacetValue[];
  baseColour: ProductFacetValue[];
  season: ProductFacetValue[];
  usage: ProductFacetValue[];
  price: { min: number; max: number; currency: string };
}

export interface CartItem {
  cartItemId: string;
  productId: string;
  titleSnapshot: string;
  priceSnapshot: ProductPrice;
  imageUrlSnapshot?: string;
  quantity: number;
  size?: string | null;
}

export interface Totals {
  subtotal: number;
  tax: number;
  shipping: number;
  discount: number;
  grandTotal: number;
  currency: string;
}

export interface Cart {
  _id: string;
  items: CartItem[];
  totals: Totals;
}

export interface User {
  _id: string;
  email: string;
  name: string;
  roles?: string[];
  preferences?: Record<string, unknown>;
}

export interface Address {
  name: string;
  line1: string;
  line2?: string;
  city: string;
  region: string;
  postalCode: string;
  country: string;
  phone?: string;
}

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

export interface ChatMessage {
  _id?: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  metadata?: {
    suggestedProducts?: Product[];
    pendingActionId?: string;
    pendingActionType?: string;
    pendingActionExpiresAt?: string;
    usedAgenticLoop?: boolean;
    usedDeepAgents?: boolean;
    runId?: string;
    context?: Record<string, unknown>;
  };
  createdAt: string;
}

export interface ChatSession {
  _id: string;
  type: "shopping" | "support";
  status: string;
  summary?: string;
  messageCount?: number;
  createdAt: string;
  updatedAt: string;
}

export interface ChatSessionHistory {
  items: ChatSession[];
  hasMore: boolean;
  nextCursor?: string | null;
}

export interface PendingAction {
  id: string;
  type: string;
  expiresAt: string;
  requiresDetails?: boolean;
}

export interface AssistantReply {
  message: string;
  suggestedProducts?: Product[];
  pendingAction?: PendingAction;
  usedMcp?: boolean;
  comparison?: Record<string, (string | number | null)[]>;
  eligibility?: Record<string, unknown>;
  usedAgenticLoop?: boolean;
  usedDeepAgents?: boolean;
  agentFallbackReason?: string;
}
