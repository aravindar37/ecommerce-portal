"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { apiFetch, money } from "@/lib/api";
import type { AssistantReply, ChatMessage, Order, OrderItem, PendingAction } from "@/lib/types";

interface FeedEntry {
  id: string;
  role: "user" | "assistant" | "action";
  text: string;
  pendingAction?: PendingAction;
}

const STORAGE_KEY = "styleSenseSupportSessionId";

export function SupportClient() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [sessionId, setSessionId] = useState<string>(
    () => (typeof window !== "undefined" ? (localStorage.getItem(STORAGE_KEY) ?? "") : "")
  );
  const [message, setMessage] = useState("");
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const [reason, setReason] = useState("");
  const [condition, setCondition] = useState("Unused");
  const [resolution, setResolution] = useState("refund");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const scrollAnchor = useRef<HTMLDivElement>(null);

  const selectedOrder = orders.find((order) => order._id === selectedOrderId);
  const selectedItem = selectedOrder?.items.find((item) => item.orderItemId === selectedItemId);

  useEffect(() => {
    void loadOrders();
    void resumeSession();
  }, []);

  useEffect(() => {
    scrollAnchor.current?.scrollIntoView({ behavior: "smooth" });
  }, [feed]);

  function persistSession(id: string): void {
    setSessionId(id);
    localStorage.setItem(STORAGE_KEY, id);
  }

  async function loadOrders(): Promise<void> {
    try {
      const data = await apiFetch<{ items: Order[] }>("/api/core/orders");
      setOrders(data.items);
      if (data.items[0]) {
        setSelectedOrderId((current) => current || data.items[0]._id);
        setSelectedItemId((current) => current || data.items[0].items[0]?.orderItemId || "");
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign in and place an order before requesting support.");
    }
  }

  async function resumeSession(): Promise<void> {
    const stored = typeof window !== "undefined" ? (localStorage.getItem(STORAGE_KEY) ?? "") : "";
    try {
      const latest = stored
        ? { session: { _id: stored } }
        : await apiFetch<{ session: { _id: string } | null }>("/api/chat/assistant/support/sessions");
      if (latest.session?._id) {
        persistSession(latest.session._id);
        await loadMessages(latest.session._id);
      }
    } catch {
      // A new session will be created on first send.
    }
  }

  async function loadMessages(id: string): Promise<void> {
    const data = await apiFetch<{ items: ChatMessage[] }>(`/api/chat/assistant/support/sessions/${id}/messages?limit=100`);
    setFeed(
      data.items.map((item) => ({
        id: item._id ?? crypto.randomUUID(),
        role: item.role,
        text: safeText(item.content),
        pendingAction: item.metadata?.pendingActionId
          ? {
              id: item.metadata.pendingActionId,
              type: item.metadata.pendingActionType ?? "create_return_request",
              expiresAt: item.metadata.pendingActionExpiresAt ?? "",
            }
          : undefined,
      }))
    );
  }

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    const session = await apiFetch<{ _id: string }>("/api/chat/assistant/support/sessions", {
      method: "POST",
      body: JSON.stringify({ orderId: selectedOrderId || null })
    });
    persistSession(session._id);
    return session._id;
  }

  function selectOrder(order: Order): void {
    setSelectedOrderId(order._id);
    setSelectedItemId(order.items[0]?.orderItemId || "");
  }

  function startNew(): void {
    localStorage.removeItem(STORAGE_KEY);
    setSessionId("");
    setFeed([]);
    setReason("");
    setCondition("Unused");
    setResolution("refund");
    setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!message.trim()) return;
    setError("");
    setBusy(true);
    const userText = message;
    const userEntry: FeedEntry = { id: crypto.randomUUID(), role: "user", text: safeText(userText) };
    setFeed((prev) => [...prev, userEntry]);
    setMessage("");
    try {
      const activeSession = await ensureSession();
      const response = await apiFetch<AssistantReply>("/api/chat/assistant/support/messages", {
        method: "POST",
        body: JSON.stringify({
          sessionId: activeSession,
          message: userText,
          context: { orderId: selectedOrderId || undefined, orderItemId: selectedItemId || undefined }
        })
      });
      setFeed((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "assistant", text: safeText(response.message) },
        ...(response.pendingAction ? [{ id: crypto.randomUUID(), role: "action" as const, text: "Confirm return request", pendingAction: response.pendingAction }] : []),
      ]);
    } catch (caught) {
      setFeed((prev) => prev.filter((entry) => entry.id !== userEntry.id));
      setError(caught instanceof Error ? caught.message : "Unable to reach support agent.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(action: PendingAction): Promise<void> {
    setError("");
    setBusy(true);
    try {
      const result = await apiFetch<{ result?: { returnNumber?: string } }>("/api/chat/assistant/actions/confirm", {
        method: "POST",
        body: JSON.stringify({ actionId: action.id, confirm: true, reason, condition, resolution })
      });
      const returnNumber = result.result?.returnNumber ?? "Return requested";
      setFeed((prev) => [
        ...prev.filter((entry) => entry.pendingAction?.id !== action.id),
        { id: crypto.randomUUID(), role: "assistant", text: `Return created: ${returnNumber}` },
      ]);
      setReason("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create return request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="main">
      <div className="support-header">
        <div>
          <h1 className="page-title">Support</h1>
          {selectedOrder ? <p className="meta">Selected {selectedOrder.orderNumber}</p> : null}
        </div>
        <button type="button" className="secondary" onClick={startNew}>New chat</button>
      </div>

      <div className="support-layout">
        <section className="panel support-orders" aria-label="Orders">
          <h2>Orders</h2>
          {orders.map((order) => (
            <button
              key={order._id}
              type="button"
              className={`support-order-row${order._id === selectedOrderId ? " active" : ""}`}
              onClick={() => selectOrder(order)}
            >
              <strong>{order.orderNumber}</strong>
              <span>{money(order.totals.grandTotal, order.totals.currency)}</span>
            </button>
          ))}
          {selectedOrder ? (
            <div className="support-items">
              {selectedOrder.items.map((item) => (
                <button
                  key={item.orderItemId}
                  type="button"
                  className={`support-item-row${item.orderItemId === selectedItemId ? " active" : ""}`}
                  onClick={() => setSelectedItemId(item.orderItemId)}
                >
                  {item.imageUrlSnapshot ? <img src={item.imageUrlSnapshot} alt={item.titleSnapshot} /> : null}
                  <span>{item.titleSnapshot}</span>
                </button>
              ))}
            </div>
          ) : null}
        </section>

        <section className="panel support-chat">
          <div className="messages support-messages">
            {feed.map((entry) => (
              <div key={entry.id} className={entry.role === "action" ? "support-action-card" : `chat-bubble chat-bubble-${entry.role}`}>
                {entry.role === "action" && entry.pendingAction ? (
                  <ReturnActionCard
                    action={entry.pendingAction}
                    item={selectedItem}
                    reason={reason}
                    condition={condition}
                    resolution={resolution}
                    busy={busy}
                    onReasonChange={setReason}
                    onConditionChange={setCondition}
                    onResolutionChange={setResolution}
                    onConfirm={(action) => void confirm(action)}
                  />
                ) : (
                  <p className="chat-bubble-text">{safeText(entry.text)}</p>
                )}
              </div>
            ))}
            {busy ? <p className="meta">Working...</p> : null}
            {error ? <p className="error">{error}</p> : null}
            <div ref={scrollAnchor} />
          </div>

          <form className="form" onSubmit={(event) => void submit(event)}>
            <label>
              Message
              <textarea
                aria-label="Message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                rows={4}
              />
            </label>
            <button type="submit" disabled={busy || !message.trim()}>Ask support agent</button>
          </form>
        </section>
      </div>
    </main>
  );
}

function ReturnActionCard({
  action,
  item,
  reason,
  condition,
  resolution,
  busy,
  onReasonChange,
  onConditionChange,
  onResolutionChange,
  onConfirm,
}: {
  action: PendingAction;
  item?: OrderItem;
  reason: string;
  condition: string;
  resolution: string;
  busy: boolean;
  onReasonChange: (value: string) => void;
  onConditionChange: (value: string) => void;
  onResolutionChange: (value: string) => void;
  onConfirm: (action: PendingAction) => void;
}) {
  return (
    <div>
      <strong>Create return</strong>
      {item ? <p className="meta">{item.titleSnapshot}</p> : null}
      <label>Reason<input aria-label="Reason" value={reason} onChange={(event) => onReasonChange(event.target.value)} required /></label>
      <label>
        Condition
        <select aria-label="Condition" value={condition} onChange={(event) => onConditionChange(event.target.value)}>
          <option>Unused</option>
          <option>Opened</option>
          <option>Damaged</option>
        </select>
      </label>
      <label>
        Resolution
        <select aria-label="Resolution" value={resolution} onChange={(event) => onResolutionChange(event.target.value)}>
          <option value="refund">Refund</option>
          <option value="exchange">Exchange</option>
        </select>
      </label>
      <button type="button" onClick={() => onConfirm(action)} disabled={busy || !reason.trim()}>
        Confirm create return
      </button>
    </div>
  );
}

function safeText(value: string): string {
  const cleaned = value.trim();
  return cleaned || "Support response is ready.";
}
