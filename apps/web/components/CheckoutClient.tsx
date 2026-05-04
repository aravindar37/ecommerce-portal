"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { Order } from "@/lib/types";

const baseAddress = {
  name: "",
  line1: "",
  line2: "",
  city: "",
  region: "",
  postalCode: "",
  country: "IN",
  phone: ""
};

export function CheckoutClient() {
  const [address, setAddress] = useState(baseAddress);
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError("");
    try {
      const placed = await apiFetch<Order>("/api/core/checkout/place-order", {
        method: "POST",
        body: JSON.stringify({ shippingAddress: address, paymentMethod: "demo" })
      });
      setOrder(placed);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to place order");
    }
  }

  return (
    <main className="main">
      <h1 className="page-title">Checkout</h1>
      {order ? (
        <section className="panel">
          <h2>Order confirmed</h2>
          <strong>{order.orderNumber}</strong>
          <p>Your demo purchase was placed.</p>
        </section>
      ) : (
        <form className="form" onSubmit={(event) => void submit(event)}>
          <label>Name<input value={address.name} onChange={(event) => setAddress({ ...address, name: event.target.value })} required /></label>
          <label>Address line 1<input value={address.line1} onChange={(event) => setAddress({ ...address, line1: event.target.value })} required /></label>
          <div className="two-col">
            <label>City<input value={address.city} onChange={(event) => setAddress({ ...address, city: event.target.value })} required /></label>
            <label>State / Region<input value={address.region} onChange={(event) => setAddress({ ...address, region: event.target.value })} required /></label>
          </div>
          <div className="two-col">
            <label>Postal code<input value={address.postalCode} onChange={(event) => setAddress({ ...address, postalCode: event.target.value })} required /></label>
            <label>Phone<input value={address.phone} onChange={(event) => setAddress({ ...address, phone: event.target.value })} required /></label>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input type="radio" name="payment" value="demo" defaultChecked style={{ width: "auto", minHeight: "auto" }} />
            Demo payment
          </label>
          <button type="submit">Place order</button>
          {error ? <p className="error">{error}</p> : null}
        </form>
      )}
    </main>
  );
}
