"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { apiFetch, money } from "@/lib/api";
import type { AssistantReply, ChatMessage, ChatSession, ChatSessionHistory, Product } from "@/lib/types";

interface AssistantDrawerProps {
  open: boolean;
  onClose: () => void;
}

interface FeedEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  products: Product[];
  pendingActionId?: string;
}

const STORAGE_KEY = "styleSenseShoppingSessionId";

function relativeTime(value: string): string {
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const seconds = Math.max(1, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return "now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

function safeText(value: string): string {
  const cleaned = value.trim();
  return cleaned || "Assistant response is ready.";
}

export function AssistantDrawer({ open, onClose }: AssistantDrawerProps) {
  const [sessionId, setSessionId] = useState<string>(
    () => (typeof window !== "undefined" ? (localStorage.getItem(STORAGE_KEY) ?? "") : "")
  );
  const [message, setMessage] = useState("");
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const [pendingActionId, setPendingActionId] = useState<string>("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionCursor, setSessionCursor] = useState<string | null>(null);
  const [hasMoreSessions, setHasMoreSessions] = useState(false);
  const [sessionsBusy, setSessionsBusy] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const scrollAnchor = useRef<HTMLDivElement>(null);

  function persistSession(id: string): void {
    setSessionId(id);
    localStorage.setItem(STORAGE_KEY, id);
  }

  useEffect(() => {
    setHistoryLoaded(false);
  }, [sessionId]);

  useEffect(() => {
    if (!open) return;
    void loadSessionHistory(true);
  }, [open]);

  useEffect(() => {
    if (!open || historyLoaded) return;

    async function loadHistory(): Promise<void> {
      const sid = sessionId || (localStorage.getItem(STORAGE_KEY) ?? "");
      if (!sid) { setHistoryLoaded(true); return; }
      try {
        const data = await apiFetch<{ items: ChatMessage[] }>(
          `/api/chat/assistant/shopping/sessions/${sid}/messages?limit=100`
        );
        const entries: FeedEntry[] = data.items.map((msg) => ({
          id: msg._id ?? crypto.randomUUID(),
          role: msg.role,
          text: msg.content,
          products: msg.metadata?.suggestedProducts ?? [],
          pendingActionId: msg.metadata?.pendingActionId,
        }));
        setFeed(entries);
        setHistoryLoaded(true);
      } catch {
        setHistoryLoaded(true);
      }
    }

    void loadHistory();
  }, [open, historyLoaded, sessionId]);

  useEffect(() => {
    scrollAnchor.current?.scrollIntoView({ behavior: "smooth" });
  }, [feed]);

  if (!open) return null;

  async function loadSessionHistory(reset: boolean): Promise<void> {
    setSessionsBusy(true);
    try {
      const cursor = reset ? "" : (sessionCursor ? `&before=${sessionCursor}` : "");
      const data = await apiFetch<ChatSessionHistory>(`/api/chat/assistant/shopping/sessions/history?limit=5${cursor}`);
      setSessions((prev) => (reset ? data.items : [...prev, ...data.items]));
      setSessionCursor(data.nextCursor ?? null);
      setHasMoreSessions(data.hasMore);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load conversation history");
    } finally {
      setSessionsBusy(false);
    }
  }

  async function loadSessionMessages(id: string): Promise<void> {
    setError("");
    setBusy(true);
    try {
      const data = await apiFetch<{ items: ChatMessage[] }>(
        `/api/chat/assistant/shopping/sessions/${id}/messages?limit=100`
      );
      const entries: FeedEntry[] = data.items.map((msg) => ({
        id: msg._id ?? crypto.randomUUID(),
        role: msg.role,
        text: msg.content,
        products: msg.metadata?.suggestedProducts ?? [],
        pendingActionId: msg.metadata?.pendingActionId,
      }));
      setFeed(entries);
      const latestPending = [...entries].reverse().find((entry) => entry.pendingActionId);
      setPendingActionId(latestPending?.pendingActionId ?? "");
      setHistoryLoaded(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load conversation");
    } finally {
      setBusy(false);
    }
  }

  function selectSession(id: string): void {
    persistSession(id);
    void loadSessionMessages(id);
  }

  function startNewSession(): void {
    setSessionId("");
    localStorage.removeItem(STORAGE_KEY);
    setFeed([]);
    setPendingActionId("");
    setError("");
    setHistoryLoaded(true);
    setHistoryCollapsed(false);
  }

  async function ensureSession(): Promise<string> {
    if (sessionId) return sessionId;
    try {
      const existing = await apiFetch<{ session: { _id: string } | null }>(
        "/api/chat/assistant/shopping/sessions"
      );
      if (existing.session?._id) {
        persistSession(existing.session._id);
        return existing.session._id;
      }
    } catch {
      // No active session — create a new one
    }
    const session = await apiFetch<{ _id: string }>("/api/chat/assistant/shopping/sessions", {
      method: "POST",
      body: JSON.stringify({ entryPoint: "catalogue" })
    });
    persistSession(session._id);
    void loadSessionHistory(true);
    return session._id;
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!message.trim()) return;
    setError("");
    setBusy(true);
    const userEntry: FeedEntry = {
      id: crypto.randomUUID(),
      role: "user",
      text: message,
      products: [],
    };
    setFeed((prev) => [...prev, userEntry]);
    const userMessage = message;
    setMessage("");
    setHistoryCollapsed(true);
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
      setFeed((prev) => [...prev, assistantEntry]);
      setPendingActionId(reply.pendingAction?.id ?? "");
      void loadSessionHistory(true);
    } catch (caught) {
      setFeed((prev) => prev.filter((e) => e.id !== userEntry.id));
      setError(caught instanceof Error ? caught.message : "Unable to reach the shopping assistant");
    } finally {
      setBusy(false);
    }
  }

  async function confirm(): Promise<void> {
    if (!pendingActionId) return;
    setError("");
    setBusy(true);
    const product = feed.flatMap((entry) => entry.products).find((entry) => entry._id);
    try {
      const result = await apiFetch<{ status: string }>("/api/chat/assistant/actions/confirm", {
        method: "POST",
        body: JSON.stringify({ actionId: pendingActionId, confirm: true })
      });
      setFeed((prev) => [
        ...prev.map((entry) => entry.pendingActionId === pendingActionId ? { ...entry, pendingActionId: undefined } : entry),
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: result.status === "completed" ? `Added ${product?.title ?? "the selected product"} to your cart.` : result.status,
          products: [],
        },
      ]);
      setPendingActionId("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to complete assistant action");
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="drawer" aria-label="Shopping assistant">
      <div className="drawer-header">
        <div className="assistant-avatar" aria-hidden="true">AI</div>
        <div>
          <strong>StyleSense AI</strong>
          <p className="meta">Shopping assistant</p>
        </div>
        <button type="button" className="secondary" onClick={() => setHistoryCollapsed((value) => !value)} aria-label="Toggle chat history">
          History
        </button>
        <button type="button" className="secondary" onClick={onClose} aria-label="Close assistant">
          Close
        </button>
      </div>
      <div className={`assistant-shell${historyCollapsed ? " collapsed" : ""}`}>
        <div className="assistant-history chat-history-panel" aria-label="Conversation history">
          <div className="assistant-history-header chat-history-header">
            <strong>Chats</strong>
            <button type="button" className="secondary icon-button chat-new-btn" onClick={startNewSession} aria-label="Start new chat">
              +
            </button>
          </div>
          <div className="assistant-history-list">
            {sessions.map((session) => (
              <button
                key={session._id}
                type="button"
                className={`assistant-history-item chat-session-row${session._id === sessionId ? " active" : ""}`}
                onClick={() => selectSession(session._id)}
              >
                <span className="chat-session-summary">{session.summary || "New conversation"}</span>
                <small className="chat-session-meta">
                  {session.messageCount ?? 0} messages · {relativeTime(session.updatedAt)}
                </small>
              </button>
            ))}
            {hasMoreSessions ? (
              <button
                type="button"
                className="secondary assistant-history-more chat-load-more"
                onClick={() => void loadSessionHistory(false)}
                disabled={sessionsBusy}
              >
                {sessionsBusy ? "Loading" : "More"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="messages">
        {feed.map((entry) => (
          <div key={entry.id} className={`chat-bubble chat-bubble-${entry.role}`}>
            <p className="chat-bubble-text">{safeText(entry.text)}</p>
            {entry.products.map((product) => (
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
            ))}
            {entry.pendingActionId ? (
              <div className="assistant-action-card">
                <strong>Add to cart</strong>
                <span className="meta">{entry.products[0]?.title ?? "Selected product"}</span>
                <button type="button" aria-label="Confirm add to cart" onClick={() => void confirm()} disabled={busy}>
                  Confirm
                </button>
              </div>
            ) : null}
          </div>
        ))}
        {busy ? (
          <div className="chat-bubble chat-bubble-assistant chat-typing" aria-live="polite">
            <span className="typing-text">Finding recommendations...</span>
            <span /><span /><span />
          </div>
        ) : null}
        {error ? <div className="error">{error}</div> : null}
        <div ref={scrollAnchor} />
        </div>
      </div>
      <form onSubmit={(event) => void submit(event)} className="form">
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
            rows={3}
          />
        </label>
        <button type="submit" disabled={busy || !message.trim()}>{busy ? "Working" : "Send"}</button>
      </form>
    </aside>
  );
}
