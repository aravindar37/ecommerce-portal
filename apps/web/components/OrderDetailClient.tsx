"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, money } from "@/lib/api";
import { ApiError } from "@/lib/api";
import type { Order } from "@/lib/types";

interface OrderDetailClientProps {
  orderNumber: string;
}

export function OrderDetailClient({ orderNumber }: OrderDetailClientProps) {
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Order>(`/api/core/orders/${orderNumber}`)
      .then(setOrder)
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 401) {
          window.location.assign("/login");
          return;
        }
        setError(caught instanceof Error ? caught.message : "Unable to load order");
      });
  }, [orderNumber]);

  if (error) return (
    <main className="main">
      <p className="error">{error}</p>
      <Link href="/orders" className="button secondary" style={{ display: "inline-flex", marginTop: 16 }}>← Back to orders</Link>
    </main>
  );

  if (!order) return <main className="main"><p className="meta">Loading order…</p></main>;

  const addr = order.shippingAddress;

  return (
    <main className="main">
      <Link href="/orders" className="back-link">← Back to orders</Link>

      <div className="order-detail-header">
        <div>
          <h1 className="page-title" style={{ fontSize: "1.6rem" }}>{order.orderNumber}</h1>
          {order.placedAt ? (
            <p className="meta">Placed {new Date(order.placedAt).toLocaleDateString("en-IN", { dateStyle: "long" })}</p>
          ) : null}
          {order.estimatedDeliveryAt ? (
            <p className="meta">Estimated delivery {new Date(order.estimatedDeliveryAt).toLocaleDateString("en-IN", { dateStyle: "long" })}</p>
          ) : null}
        </div>
        <span className="status-badge" data-status={order.status}>{order.status}</span>
      </div>

      <div className="order-detail-grid">
        <section className="panel order-items-section">
          <h2>Items</h2>
          {order.items.map((item) => (
            <div key={item.orderItemId} className="order-item-row">
              {item.imageUrlSnapshot ? (
                <img
                  className="order-item-thumb"
                  src={item.imageUrlSnapshot}
                  alt={item.titleSnapshot}
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <div className="order-item-thumb-placeholder" />
              )}
              <div className="order-item-info">
                <strong>{item.titleSnapshot}</strong>
                {item.size ? <span className="meta">Size: {item.size}</span> : null}
                <span className="meta">Qty: {item.quantity}</span>
              </div>
              <div className="order-item-price">
                {item.unitPrice ? money(item.unitPrice.amount * item.quantity, item.unitPrice.currency) : null}
              </div>
            </div>
          ))}
        </section>

        <div className="order-detail-sidebar">
          <section className="panel">
            <h2>Order total</h2>
            <div className="order-totals">
              <span>Subtotal</span><span>{money(order.totals.subtotal, order.totals.currency)}</span>
              {order.totals.tax > 0 ? <><span>Tax (GST)</span><span>{money(order.totals.tax, order.totals.currency)}</span></> : null}
              <span>Shipping</span><span>{order.totals.shipping === 0 ? "Free" : money(order.totals.shipping, order.totals.currency)}</span>
              {order.totals.discount > 0 ? <><span>Discount</span><span>−{money(order.totals.discount, order.totals.currency)}</span></> : null}
              <strong>Total</strong><strong>{money(order.totals.grandTotal, order.totals.currency)}</strong>
            </div>
          </section>

          {addr ? (
            <section className="panel">
              <h2>Delivery address</h2>
              <address className="address-block">
                <span>{addr.name}</span>
                <span>{addr.line1}{addr.line2 ? `, ${addr.line2}` : ""}</span>
                <span>{addr.city}, {addr.region} {addr.postalCode}</span>
                <span>{addr.country}</span>
                {addr.phone ? <span>{addr.phone}</span> : null}
              </address>
            </section>
          ) : null}

          {order.payment ? (
            <section className="panel">
              <h2>Payment</h2>
              <p className="meta">{order.payment.provider} · {order.payment.status}</p>
            </section>
          ) : null}
        </div>
      </div>
    </main>
  );
}
