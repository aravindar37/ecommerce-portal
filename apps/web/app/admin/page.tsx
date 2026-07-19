import { headers } from "next/headers";

interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
}

interface AdminConfig {
  services: Record<string, { runtime?: string; framework: string }>;
  llm: { provider: string; model: string };
  embedding: { provider: string; model: string };
  imageStorage: { provider: string };
  codexMcp: { enabled: boolean; transport: string };
}

async function fetchCoreAdmin<T>(path: string): Promise<T | null> {
  const token = process.env.TEST_ADMIN_TOKEN;
  if (!token) return null;
  const response = await fetch(`${process.env.CORE_SERVICE_BASE_URL ?? "http://localhost:4000"}${path}`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store"
  });
  const payload = (await response.json()) as Envelope<T>;
  return payload.data;
}

async function fetchChatAdmin<T>(path: string): Promise<T | null> {
  const token = process.env.TEST_ADMIN_TOKEN;
  if (!token) return null;
  const response = await fetch(`${process.env.CHAT_SERVICE_BASE_URL ?? "http://localhost:4002"}${path}`, {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store"
  });
  if (!response.ok) return null;
  const payload = (await response.json()) as Envelope<T>;
  return payload.data;
}

export default async function AdminPage() {
  const requestHeaders = await headers();
  const host = requestHeaders.get("host") ?? "localhost:3000";
  const config = await fetchCoreAdmin<AdminConfig>("/api/admin/config");
  const activity = await fetchCoreAdmin<{ items: unknown[] }>("/api/admin/activity-events?limit=20");
  const voiceCalls = await fetchChatAdmin<{ items: Array<{ callId?: string; disposition?: string; durationSeconds?: number; escalated?: boolean; verificationOutcome?: string; transcriptSummary?: string }> }>("/api/admin/voice/call-sessions?limit=10");

  return (
    <main className="main">
      <h1 className="page-title">Admin console</h1>
      <p className="lede">Provider config and agent readiness for {host}.</p>
      <section className="admin-grid">
        <div className="panel">
          <h2>Services</h2>
          <p>Python FastAPI</p>
          <p className="meta">{Object.keys(config?.services ?? {}).join(" · ") || "core · search · chat"}</p>
        </div>
        <div className="panel">
          <h2>LLM</h2>
          <p>{config?.llm.model ?? "gpt-5.4"}</p>
          <p className="meta">{config?.llm.provider ?? "openai"}</p>
        </div>
        <div className="panel">
          <h2>Embeddings</h2>
          <p>{config?.embedding.model ?? "nomic-embed-text:v1.5"}</p>
          <p className="meta">{config?.embedding.provider ?? "ollama"}</p>
        </div>
        <div className="panel">
          <h2>MCP</h2>
          <p className="status">{config?.codexMcp.enabled ? "ready" : "not ready"}</p>
          <p className="meta">{config?.codexMcp.transport ?? "stdio"}</p>
        </div>
        <div className="panel">
          <h2>Image storage</h2>
          <p>{config?.imageStorage.provider ?? "local_filesystem"}</p>
        </div>
        <div className="panel">
          <h2>Activity funnel</h2>
          <p>{activity?.items.length ?? 0} recent captured events</p>
        </div>
        <div className="panel">
          <h2>Recent voice calls</h2>
          {voiceCalls?.items.length ? voiceCalls.items.map((call, index) => (
            <p className="meta" key={index}>
              {call.disposition ?? "unknown"} · {call.durationSeconds ?? 0}s · {call.verificationOutcome ?? "pending"}{call.escalated ? " · escalated" : ""}
              {call.transcriptSummary ? ` — ${call.transcriptSummary}` : ""}
              {call.callId ? <> · <a href={`/admin/voice/${encodeURIComponent(call.callId)}`}>Transcript</a></> : null}
            </p>
          )) : <p className="meta">No voice calls yet.</p>}
        </div>
      </section>
    </main>
  );
}
