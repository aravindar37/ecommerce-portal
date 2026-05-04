"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, money } from "@/lib/api";
import type { Cart } from "@/lib/types";

export function CartClient() {
  const router = useRouter();
  const [cart, setCart] = useState<Cart | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void loadCart();
  }, []);

  async function loadCart(): Promise<void> {
    try {
      setCart(await apiFetch<Cart>("/api/core/cart"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load cart");
    }
  }

  return (
    <main className="main">
      <h1 className="page-title">Cart</h1>
      {error ? <p className="error">{error}</p> : null}
      <section className="panel">
        {cart?.items.length ? (
          cart.items.map((item) => (
            <div key={item.cartItemId} className="cart-line">
              <img src={item.imageUrlSnapshot ?? "/product-images/fallback.jpg"} alt="" />
              <div>
                <strong>{item.titleSnapshot}</strong>
                <p className="meta">Size {item.size ?? "M"} · Qty {item.quantity}</p>
              </div>
              <span>{money(item.priceSnapshot.amount * item.quantity, item.priceSnapshot.currency)}</span>
            </div>
          ))
        ) : (
          <p className="meta">Your cart is empty.</p>
        )}
        {cart ? <strong>Subtotal {money(cart.totals.subtotal, cart.totals.currency)} · Total {money(cart.totals.grandTotal, cart.totals.currency)}</strong> : null}
        <button type="button" onClick={() => router.push("/checkout")} disabled={!cart?.items.length}>Checkout</button>
      </section>
    </main>
  );
}
