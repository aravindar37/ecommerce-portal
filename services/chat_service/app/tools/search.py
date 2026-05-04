"""Search Service backed assistant tools."""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.http import build_url, request_json, unwrap_envelope

Json = dict[str, Any]


class SearchTools:
    """Tool wrapper around Search Service APIs."""

    def headers(self, cookie_header: str | None = None) -> dict[str, str]:
        """Build Search request headers."""

        headers: dict[str, str] = {}
        if cookie_header:
            headers["cookie"] = cookie_header
        if settings.search_service_internal_token:
            headers["x-service-token"] = settings.search_service_internal_token
        return headers

    def search_products(self, cookie_header: str, query: str, filters: Json | None = None, limit: int = 5) -> list[Json]:
        """Search products through hybrid search."""

        data = unwrap_envelope(
            request_json(
                "POST",
                build_url(settings.search_service_base_url, "/api/search/hybrid"),
                payload={"query": query, "filters": filters or {}, "limit": limit},
                headers=self.headers(cookie_header),
            )
        )
        results = data.get("results") if isinstance(data, dict) else []
        return [item["product"] for item in results if isinstance(item, dict) and isinstance(item.get("product"), dict)]

    def get_product(self, cookie_header: str, product_id: str) -> Json:
        """Fetch one product detail."""

        return unwrap_envelope(
            request_json(
                "GET",
                build_url(settings.search_service_base_url, f"/api/products/{product_id}"),
                headers=self.headers(cookie_header),
            )
        )

    def get_similar_products(self, cookie_header: str, product_id: str, limit: int = 4) -> list[Json]:
        """Fetch similar products."""

        data = unwrap_envelope(
            request_json(
                "GET",
                build_url(settings.search_service_base_url, f"/api/products/{product_id}/similar", {"limit": limit}),
                headers=self.headers(cookie_header),
            )
        )
        items = data.get("items") if isinstance(data, dict) else []
        return [item for item in items if isinstance(item, dict)]

    def find_matching_products(
        self,
        cookie_header: str,
        reference_product_id: str,
        target_article_type: str,
        limit: int = 5,
    ) -> list[Json]:
        """Search for products that complement a reference item."""

        reference = self.get_product(cookie_header, reference_product_id)
        query_parts = [
            str(reference.get("baseColour") or ""),
            target_article_type,
            str(reference.get("usage") or ""),
        ]
        filters: Json = {}
        if target_article_type.lower() != "shoes":
            filters["articleType"] = target_article_type
        if reference.get("gender"):
            filters["gender"] = reference["gender"]
        if reference.get("usage"):
            filters["usage"] = [reference["usage"]]
        query = " ".join(part for part in query_parts if part).strip()
        products = self.search_products(cookie_header, query, filters=filters, limit=limit)
        if not products and filters:
            products = self.search_products(cookie_header, query, filters={}, limit=limit)
        if target_article_type.lower() == "shoes":
            shoe_products = [
                product
                for product in products
                if "shoe" in str(product.get("articleType") or product.get("title") or "").lower()
            ]
            if not shoe_products:
                shoe_products = [
                    product
                    for product in self.search_products(cookie_header, "shoes", filters={}, limit=limit)
                    if "shoe" in str(product.get("articleType") or product.get("title") or "").lower()
                ]
            products = shoe_products or products
        return products

    def compare_products(self, cookie_header: str, product_ids: list[str]) -> Json:
        """Fetch multiple products and return a structured comparison."""

        products = [self.get_product(cookie_header, product_id) for product_id in product_ids]
        fields = ["title", "price", "baseColour", "articleType", "usage", "gender", "ratingAverage", "ratingCount", "tags"]
        return {
            "products": products,
            "attributes": {field: [product.get(field) for product in products] for field in fields},
        }


search_tools = SearchTools()
