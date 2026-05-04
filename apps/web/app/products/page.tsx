import { Suspense } from "react";
import { ProductsClient } from "@/components/ProductsClient";

export default function ProductsPage() {
  return (
    <Suspense fallback={<main className="main">Loading products</main>}>
      <ProductsClient />
    </Suspense>
  );
}
