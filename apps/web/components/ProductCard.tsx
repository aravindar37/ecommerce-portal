"use client";

import { useState } from "react";
import { money } from "@/lib/api";
import type { Product } from "@/lib/types";

interface ProductCardProps {
  product: Product;
  onAdd?: (productId: string, size: string) => Promise<void>;
  showAdd?: boolean;
}

export function ProductCard({ product, onAdd, showAdd = true }: ProductCardProps) {
  const [size, setSize] = useState("M");
  const image = product.images[0]?.url ?? "/product-images/fallback.jpg";
  const sizes = ["S", "M", "L", "XL"];
  return (
    <article className="product-card">
      <a className="product-media-link" href={`/products/${product.slug}`} aria-label="Product detail">
        <img className="product-media" src={image} alt={product.images[0]?.alt ?? product.title} />
      </a>
      <div className="card-body">
        <a className="product-title" href={`/products/${product.slug}`} aria-label="Product detail">
          {product.title}
        </a>
        <div className="meta">
          {product.gender} · {product.baseColour} · {product.usage ?? product.articleType}
        </div>
        <div className="price">{money(product.price.amount, product.price.currency)}</div>
        <div className="rating" aria-label={`Rating ${ratingValue(product)} out of 5`}>
          <span aria-hidden="true">★</span> {ratingValue(product)} <span className="meta">({product.ratingCount ?? 0})</span>
        </div>
        {showAdd ? (
          <>
            <div className="size-picker" role="group" aria-label="Select size">
              <span className="size-label">Size</span>
              <div className="size-options">
                {sizes.map((option) => (
                  <button
                    key={option}
                    type="button"
                    className={`size-chip${size === option ? " selected" : ""}`}
                    aria-pressed={size === option}
                    onClick={() => setSize(option)}
                  >
                    {option}
                  </button>
                ))}
              </div>
            </div>
            <button className="add-to-cart" type="button" aria-label="Add to bag" onClick={() => onAdd && void onAdd(product._id, size)}>
              Add to bag
            </button>
          </>
        ) : null}
      </div>
    </article>
  );
}

function ratingValue(product: Product): string {
  return (product.ratingAverage ?? 4.2).toFixed(1);
}
