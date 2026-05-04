"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Cart, User } from "@/lib/types";

export function HeaderNav() {
  const [user, setUser] = useState<User | null>(null);
  const [cartCount, setCartCount] = useState(0);
  const [resolved, setResolved] = useState(false);

  useEffect(() => {
    void apiFetch<User>("/api/core/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setResolved(true));
    void apiFetch<Cart>("/api/core/cart")
      .then((cart) => setCartCount(cart.items.reduce((total, item) => total + item.quantity, 0)))
      .catch(() => setCartCount(0));
  }, []);

  async function signOut(): Promise<void> {
    await apiFetch("/api/core/auth/logout", { method: "POST", body: JSON.stringify({}) }).catch(() => undefined);
    window.location.assign("/login");
  }

  const isAdmin = user?.roles?.includes("admin") ?? false;

  return (
    <nav className="nav" aria-label="Primary">
      <Link href="/products">Catalogue</Link>
      {resolved && user ? (
        <>
          <Link href="/account">Account</Link>
          <Link href="/orders">Orders</Link>
          <Link href="/cart" aria-label={`Bag (${cartCount})`}>Bag ({cartCount})</Link>
          <Link href="/support">Support</Link>
          {isAdmin ? <Link href="/admin">Admin Dashboard</Link> : null}
          <button type="button" className="nav-button" onClick={() => void signOut()}>Sign out</button>
        </>
      ) : (
        <Link href="/login">Sign in</Link>
      )}
    </nav>
  );
}
