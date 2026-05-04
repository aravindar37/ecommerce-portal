"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, apiFetch, money } from "@/lib/api";
import type { Product } from "@/lib/types";
import { ProductCard } from "./ProductCard";

interface ProductDetailClientProps {
  slug: string;
}

export function ProductDetailClient({ slug }: ProductDetailClientProps) {
  const [product, setProduct] = useState<Product | null>(null);
  const [similar, setSimilar] = useState<Product[]>([]);
  const [status, setStatus] = useState("");
  const [selectedSize, setSelectedSize] = useState("M");
  const [error, setError] = useState("");

  useEffect(() => {
    async function load(): Promise<void> {
      try {
        const detail = await apiFetch<Product>(`/api/search/products/${slug}`);
        setProduct(detail);
        const similarData = await apiFetch<{ items: Product[] }>(`/api/search/products/${detail._id}/similar?limit=4`);
        setSimilar(similarData.items);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Unable to load product");
      }
    }
    void load();
  }, [slug]);

  async function addToCart(productId: string, size = selectedSize): Promise<void> {
    setError("");
    try {
      await apiFetch("/api/core/me");
      await apiFetch("/api/core/cart/items", {
        method: "POST",
        body: JSON.stringify({ productId, quantity: 1, size })
      });
      setStatus("Added to bag");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        window.location.assign(`/login?returnTo=${encodeURIComponent(`/products/${slug}`)}`);
        return;
      }
      setError(caught instanceof Error ? caught.message : "Unable to add item to cart");
    }
  }

  if (error) return <main className="main"><p className="error">{error}</p></main>;
  if (!product) return <main className="main">Loading product</main>;

  return (
    <main className="main">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/products">Catalogue</Link>
        <span>/</span>
        <Link href={`/products?masterCategory=${encodeURIComponent(product.masterCategory)}`}>{product.masterCategory}</Link>
        <span>/</span>
        <Link href={`/products?subCategory=${encodeURIComponent(product.subCategory)}`}>{product.subCategory}</Link>
      </nav>
      <section className="detail">
        <img className="product-media" src={product.images[0]?.url ?? "/product-images/fallback.jpg"} alt={product.title} />
        <div className="panel">
          <div className="meta">
            {product.masterCategory} / {product.subCategory} / {product.articleType}
          </div>
          <h1>{product.title}</h1>
          <div className="price">{money(product.price.amount, product.price.currency)}</div>
          <p>
            {product.baseColour} · {product.gender} · {product.usage ?? "Fashion"}
          </p>
          <p className="rating">★ {(product.ratingAverage ?? 4.2).toFixed(1)} <span className="meta">({product.ratingCount ?? 0} reviews)</span></p>
          <label>
            Size
            <select value={selectedSize} onChange={(event) => setSelectedSize(event.target.value)}>
              <option>S</option>
              <option>M</option>
              <option>L</option>
              <option>XL</option>
            </select>
          </label>
          <p>{product.description}</p>
          <p className="meta">Return policy: {product.returnPolicyCode ?? "standard-30-day"}</p>
          <button type="button" aria-label="Add to bag" onClick={() => void addToCart(product._id)}>
            Add to bag
          </button>
          <span className="status">{status}</span>
        </div>
      </section>
      <h2>Similar products</h2>
      <section className="grid">
        {similar.map((item) => (
          <ProductCard key={item._id} product={item} onAdd={addToCart} showAdd={false} />
        ))}
      </section>
    </main>
  );
}
