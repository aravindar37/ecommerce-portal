"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetch } from "@/lib/api";
import type { User } from "@/lib/types";

export function AccountClient() {
  const [user, setUser] = useState<User | null>(null);
  const [style, setStyle] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function load(): Promise<void> {
      try {
        const current = await apiFetch<User>("/api/core/me");
        setUser(current);
        setStyle(String(current.preferences?.style ?? ""));
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          window.location.assign("/login?returnTo=/account");
          return;
        }
        setError(caught instanceof Error ? caught.message : "Unable to load account");
      }
    }
    void load();
  }, []);

  async function save(): Promise<void> {
    setError("");
    setStatus("");
    try {
      const updated = await apiFetch<User>("/api/core/me/preferences", {
        method: "PATCH",
        body: JSON.stringify({ key: "style", value: style })
      });
      setUser(updated);
      setStatus("Preferences saved");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save preferences");
    }
  }

  return (
    <main className="main">
      <h1 className="page-title">Account</h1>
      <p className="lede">Profile details and shopping preferences for your demo identity.</p>
      {error ? <p className="error">{error}</p> : null}
      <section className="account-layout">
        <div className="panel">
          <h2>Profile</h2>
          <p><strong>{user?.name ?? "Loading"}</strong></p>
          <p className="meta">{user?.email}</p>
          <p className="meta">Roles: {(user?.roles ?? ["customer"]).join(", ")}</p>
        </div>
        <div className="panel">
          <h2>Preferences</h2>
          <label>
            Style notes
            <textarea value={style} onChange={(event) => setStyle(event.target.value)} rows={4} placeholder="Minimal, formal, black shoes, breathable fabrics..." />
          </label>
          <button type="button" onClick={() => void save()}>Save preferences</button>
          {status ? <p className="status">{status}</p> : null}
        </div>
      </section>
    </main>
  );
}
