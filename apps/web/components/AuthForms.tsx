"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";

interface AuthFormProps {
  mode: "login" | "register";
  initialError?: string;
  returnTo?: string;
}

export function AuthForm({ mode, initialError = "", returnTo = "/products" }: AuthFormProps) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(initialError);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (mode === "register") {
        await apiFetch("/api/core/auth/register", {
          method: "POST",
          body: JSON.stringify({ name, email, password })
        });
      }
      await apiFetch("/api/core/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password })
      });
      await apiFetch("/api/core/cart/merge", { method: "POST", body: JSON.stringify({}) }).catch(() => undefined);
      window.location.assign(returnTo);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Authentication failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="main">
      <h1 className="page-title">{mode === "register" ? "Create account" : "Sign in"}</h1>
      <form
        className="form"
        onSubmit={(event) => void submit(event)}
      >
        {mode === "register" ? (
          <label>
            Name
            <input name="name" value={name} onChange={(event) => setName(event.target.value)} required />
          </label>
        ) : null}
        <label>
          Email
          <input name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
        </label>
        <label>
          Password
          <input name="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        </label>
        <button type="submit" disabled={submitting}>{submitting ? "Please wait" : mode === "register" ? "Create account" : "Sign in"}</button>
        {error ? <p className="error">{error}</p> : null}
        {mode === "login" ? <Link href="/register">Register</Link> : <Link href="/login">Login</Link>}
      </form>
    </main>
  );
}
