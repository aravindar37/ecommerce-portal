import { ProductDetailClient } from "@/components/ProductDetailClient";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export default async function ProductDetailPage({ params }: PageProps) {
  return <ProductDetailClient slug={(await params).slug} />;
}
