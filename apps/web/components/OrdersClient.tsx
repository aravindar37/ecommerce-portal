"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, money } from "@/lib/api";
import type { Order } from "@/lib/types";

export function OrdersClient() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    void apiFetch<{ items: Order[] }>("/api/core/orders")
      .then((data) => setOrders(data.items))
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load orders"));
  }, []);

  return (
    <main className="main">
      <h1 className="page-title">Orders</h1>
      <section className="panel">
        {orders.map((order) => (
          <Link key={order._id} href={`/orders/${order.orderNumber}`} className="order-row">
            <div className="order-row-meta">
              <strong className="order-number">{order.orderNumber}</strong>
              <span className="status-badge" data-status={order.status ?? "confirmed"}>
                {order.status ?? "confirmed"}
              </span>
            </div>
            <div className="order-row-detail">
              <span className="meta">{order.items.length} item{order.items.length !== 1 ? "s" : ""}</span>
              {order.placedAt ? (
                <span className="meta">{new Date(order.placedAt).toLocaleDateString("en-IN")}</span>
              ) : null}
              <span className="price">{money(order.totals.grandTotal, order.totals.currency)}</span>
            </div>
          </Link>
        ))}
        {!orders.length && !error ? <p className="meta">No orders yet.</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>
    </main>
  );
}
