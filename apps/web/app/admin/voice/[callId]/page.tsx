import Link from "next/link";
import { headers } from "next/headers";

interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
}

interface Transcript {
  callId: string;
  disposition?: string;
  items: Array<{ role?: string; content?: string; createdAt?: string }>;
}

async function fetchTranscript(callId: string): Promise<Transcript | null> {
  const token = process.env.TEST_ADMIN_TOKEN;
  if (!token) return null;
  const response = await fetch(
    `${process.env.CHAT_SERVICE_BASE_URL ?? "http://localhost:4002"}/api/admin/voice/call-sessions/${encodeURIComponent(callId)}/transcript`,
    { headers: { authorization: `Bearer ${token}` }, cache: "no-store" }
  );
  if (!response.ok) return null;
  const payload = (await response.json()) as Envelope<Transcript>;
  return payload.data;
}

export default async function VoiceTranscriptPage({ params }: { params: Promise<{ callId: string }> }) {
  const { callId } = await params;
  const transcript = await fetchTranscript(callId);
  const host = (await headers()).get("host") ?? "localhost:3000";

  return (
    <main className="main">
      <Link href="/admin" className="meta">← Admin console</Link>
      <h1 className="page-title">Voice call transcript</h1>
      <p className="lede">{host} · {transcript?.disposition ?? "unavailable"}</p>
      <section className="panel">
        {transcript?.items.length ? transcript.items.map((message, index) => (
          <p key={`${message.createdAt ?? index}-${index}`}>
            <strong>{message.role === "assistant" ? "Agent" : "Caller"}:</strong> {message.content}
          </p>
        )) : <p className="meta">No transcript is available for this call.</p>}
      </section>
    </main>
  );
}