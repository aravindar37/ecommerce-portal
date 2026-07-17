"""Product read model and search ranking utilities."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.config import SearchServiceSettings, settings
from app.embeddings.config import EmbeddingSettings
from app.embeddings.generate_embeddings import EmbeddingError, generate_vectors
from app.embeddings.generate_embeddings import build_embedding_text

Json = dict[str, Any]


class ProductReadError(Exception):
    """Raised when product read data cannot be loaded."""


def clone(value: Any) -> Any:
    """Return a JSON-safe deep copy."""

    return json.loads(json.dumps(value, default=str))


def tokenize(value: str) -> list[str]:
    """Tokenize text for local keyword and semantic ranking."""

    return [token for token in re.split(r"[^a-z0-9]+", value.lower()) if token]


def read_jsonl(path: Path) -> list[Json]:
    """Read JSONL objects from disk."""

    if not path.exists():
        return []
    records: list[Json] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    raise ProductReadError(f"Expected object at {path}:{line_number}")
                records.append(payload)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProductReadError(f"Unable to read JSONL product data from {path}: {exc}") from exc
    return records


class ProductReadModel:
    """Local product read model backed by Core seed state or normalized JSONL."""

    def __init__(self, config: SearchServiceSettings) -> None:
        self.config = config
        self._atlas_client: Any | None = None
        self._atlas_unavailable = False

    def all_products(self) -> list[Json]:
        """Load products from Core local state, then ingestion JSONL as fallback."""

        local_products = self.core_state_products()
        if local_products:
            return local_products
        atlas_products = self.atlas_products()
        if atlas_products:
            return atlas_products
        products = read_jsonl(self.config.products_jsonl_path)
        return [clone(product) for product in products]

    def core_state_products(self) -> list[Json]:
        """Load seeded products from the Core Service local state file."""

        state_path = self.config.core_service_data_path
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ProductReadError(f"Unable to read Core Service state from {state_path}: {exc}") from exc
            products = state.get("products") if isinstance(state, dict) else None
            if isinstance(products, list) and products:
                return [clone(product) for product in products if isinstance(product, dict)]
        return []

    def atlas_collection(self) -> Any:
        """Return the Atlas products collection."""

        if not self.config.mongodb_uri.strip():
            raise ProductReadError("MONGODB_URI is not configured")
        if self._atlas_client is None:
            try:
                import certifi
                from pymongo import MongoClient
            except ImportError as exc:
                raise ProductReadError("pymongo and certifi must be installed for MongoDB Atlas product reads") from exc
            self._atlas_client = MongoClient(self.config.mongodb_uri, serverSelectionTimeoutMS=3000, tlsCAFile=certifi.where())
        return self._atlas_client[self.config.mongodb_db]["products"]

    def normalize_atlas_product(self, product: Json) -> Json:
        """Return an Atlas product with JSON-safe identifiers."""

        normalized = clone(product)
        if "_id" in normalized:
            normalized["_id"] = str(normalized["_id"])
        return normalized

    def atlas_products(self) -> list[Json]:
        """Load products from MongoDB Atlas when configured."""

        if not self.config.mongodb_uri.strip() or self._atlas_unavailable:
            return []
        try:
            products = list(self.atlas_collection().find({"isActive": {"$ne": False}}))
        except Exception as exc:
            self._atlas_client = None
            self._atlas_unavailable = True
            return []
        return [self.normalize_atlas_product(product) for product in products]

    def active_products(self) -> list[Json]:
        """Return active products only."""

        return [product for product in self.all_products() if product.get("isActive", True)]

    def find_product(self, product_id_or_slug: str) -> Json | None:
        """Find a product by object ID, source product ID, or slug."""

        local_product = next(
            (
                product
                for product in self.active_products()
                if product.get("_id") == product_id_or_slug
                or product.get("sourceProductId") == product_id_or_slug
                or product.get("slug") == product_id_or_slug
            ),
            None,
        )
        if local_product:
            return local_product
        if self.config.mongodb_uri.strip() and not self._atlas_unavailable:
            try:
                product = self.atlas_collection().find_one(
                    {
                        "isActive": {"$ne": False},
                        "$or": [
                            {"_id": product_id_or_slug},
                            {"sourceProductId": product_id_or_slug},
                            {"slug": product_id_or_slug},
                        ],
                    }
                )
            except Exception as exc:
                self._atlas_client = None
                self._atlas_unavailable = True
                product = None
            if isinstance(product, dict):
                return self.normalize_atlas_product(product)
        return None

    def keyword_score(self, product: Json, query: str | None) -> float:
        """Calculate a simple deterministic keyword relevance score."""

        if not query:
            return 0.0
        query_terms = set(tokenize(query))
        if not query_terms:
            return 0.0
        searchable = " ".join(
            [
                str(product.get("title") or ""),
                str(product.get("description") or ""),
                str(product.get("brand") or ""),
                str(product.get("gender") or ""),
                str(product.get("masterCategory") or ""),
                str(product.get("subCategory") or ""),
                str(product.get("articleType") or ""),
                str(product.get("baseColour") or ""),
                str(product.get("usage") or ""),
                " ".join(str(tag) for tag in product.get("tags") or []),
            ]
        )
        product_terms = set(tokenize(searchable))
        matches = len(query_terms.intersection(product_terms))
        title_terms = set(tokenize(str(product.get("title") or "")))
        title_matches = len(query_terms.intersection(title_terms))
        return float(matches + (title_matches * 2))

    def semantic_score(self, product: Json, query: str) -> float:
        """Calculate local text-similarity score as a vector-search fallback."""

        query_terms = set(tokenize(query))
        if not query_terms:
            return 0.0
        product_terms = set(tokenize(build_embedding_text(product)))
        overlap = len(query_terms.intersection(product_terms))
        denominator = math.sqrt(max(len(query_terms), 1) * max(len(product_terms), 1))
        return round(overlap / denominator, 6)

    def filter_products(self, products: list[Json], filters: Json) -> list[Json]:
        """Apply supported metadata filters."""

        filtered = products
        for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]:
            raw_value = filters.get(field_name)
            if raw_value is None:
                continue
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            value_set = {str(item).lower() for item in values}
            filtered = [product for product in filtered if str(product.get(field_name, "")).lower() in value_set]
        price_min = filters.get("priceMin")
        price_max = filters.get("priceMax")
        if price_min is not None:
            filtered = [product for product in filtered if self.price_amount(product) >= float(price_min)]
        if price_max is not None:
            filtered = [product for product in filtered if self.price_amount(product) <= float(price_max)]
        return filtered

    def normalized_filter_values(self, filters: Json, field_name: str) -> list[str]:
        """Return non-empty string filter values for a field."""

        raw_value = filters.get(field_name)
        if raw_value is None:
            return []
        values = raw_value if isinstance(raw_value, list) else [raw_value]
        return [str(value) for value in values if str(value)]

    def price_amount(self, product: Json) -> float:
        """Read the product selling price as a float."""

        price = product.get("price") if isinstance(product.get("price"), dict) else {}
        amount = price.get("amount")
        return float(amount) if isinstance(amount, (int, float)) else 0.0

    def atlas_filter(self, query: str | None, filters: Json) -> Json:
        """Build an Atlas query document for catalogue search."""

        document: Json = {"isActive": {"$ne": False}}
        for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]:
            raw_value = filters.get(field_name)
            if raw_value is None:
                continue
            values = raw_value if isinstance(raw_value, list) else [raw_value]
            clean_values = [str(value) for value in values if str(value)]
            if clean_values:
                document[field_name] = {"$in": clean_values}
        price_filter: Json = {}
        if filters.get("priceMin") is not None:
            price_filter["$gte"] = float(filters["priceMin"])
        if filters.get("priceMax") is not None:
            price_filter["$lte"] = float(filters["priceMax"])
        if price_filter:
            document["price.amount"] = price_filter
        terms = tokenize(query or "")[:8]
        if terms:
            searchable_fields = [
                "title",
                "description",
                "brand",
                "gender",
                "masterCategory",
                "subCategory",
                "articleType",
                "baseColour",
                "usage",
                "tags",
            ]
            document["$and"] = [
                {
                    "$or": [
                        {field_name: {"$regex": re.escape(term), "$options": "i"}}
                        for field_name in searchable_fields
                    ]
                }
                for term in terms
            ]
        return document

    def atlas_prefilter_document(self, filters: Json, metadata_prefix: str = "") -> Json:
        """Build a MongoDB filter document used as vector-search pre-filter."""

        document: Json = {}
        prefix = f"{metadata_prefix}." if metadata_prefix else ""
        for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]:
            clean_values = self.normalized_filter_values(filters, field_name)
            if clean_values:
                document[f"{prefix}{field_name}"] = {"$in": clean_values}
        price_filter: Json = {}
        if filters.get("priceMin") is not None:
            price_filter["$gte"] = float(filters["priceMin"])
        if filters.get("priceMax") is not None:
            price_filter["$lte"] = float(filters["priceMax"])
        if price_filter:
            price_field = "priceAmount" if metadata_prefix else "price.amount"
            document[f"{prefix}{price_field}"] = price_filter
        return document

    def atlas_search_filter_clauses(self, filters: Json) -> list[Json]:
        """Build Atlas Search filter clauses for full-text pre-filtering."""

        clauses: list[Json] = [{"equals": {"path": "isActive", "value": True}}]
        for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]:
            clean_values = self.normalized_filter_values(filters, field_name)
            if len(clean_values) == 1:
                clauses.append({"equals": {"path": field_name, "value": clean_values[0]}})
            elif clean_values:
                clauses.append({"in": {"path": field_name, "value": clean_values}})
        range_clause: Json = {}
        if filters.get("priceMin") is not None:
            range_clause["gte"] = float(filters["priceMin"])
        if filters.get("priceMax") is not None:
            range_clause["lte"] = float(filters["priceMax"])
        if range_clause:
            clauses.append({"range": {"path": "price.amount", **range_clause}})
        return clauses

    def query_embedding_settings(self) -> EmbeddingSettings:
        """Build embedding settings for one query vector."""

        return EmbeddingSettings(
            provider=self.config.embedding_provider,
            model=self.config.embedding_model,
            dimensions=self.config.embedding_dimensions,
            text_template_version=self.config.embedding_text_template_version,
            text_max_chars=self.config.embedding_text_max_chars,
            batch_size=1,
            timeout_ms=self.config.embedding_timeout_ms,
            ollama_base_url=self.config.ollama_base_url,
            ollama_embed_path=self.config.ollama_embed_path,
            voyage_api_base_url=self.config.voyage_api_base_url,
            voyage_api_key=self.config.voyage_api_key,
            voyage_input_type_document=self.config.voyage_input_type_query,
            input_products_path=self.config.products_jsonl_path,
            output_embeddings_path=self.config.product_embeddings_jsonl_path,
            mongodb_uri=self.config.mongodb_uri,
            mongodb_db=self.config.mongodb_db,
        )

    def query_vector(self, query: str) -> list[float]:
        """Generate an embedding vector for a user search query."""

        vectors = generate_vectors([query[: self.config.embedding_text_max_chars]], self.query_embedding_settings())
        if not vectors or len(vectors[0]) != self.config.embedding_dimensions:
            raise ProductReadError("Embedding provider returned an invalid query vector")
        return vectors[0]

    def atlas_full_text_candidates(self, query: str, filters: Json, limit: int) -> list[Json]:
        """Run Atlas Search full-text candidates with pre-filter clauses."""

        pipeline: list[Json] = [
            {
                "$search": {
                    "index": self.config.mongodb_search_index_name,
                    "compound": {
                        "must": [
                            {
                                "text": {
                                    "query": query,
                                    "path": [
                                        "title",
                                        "description",
                                        "brand",
                                        "gender",
                                        "masterCategory",
                                        "subCategory",
                                        "articleType",
                                        "baseColour",
                                        "usage",
                                        "tags",
                                    ],
                                    "fuzzy": {"maxEdits": 1, "prefixLength": 2},
                                }
                            }
                        ],
                        "filter": self.atlas_search_filter_clauses(filters),
                    },
                }
            },
            {"$limit": limit},
            {"$project": {"_id": 1, "textScore": {"$meta": "searchScore"}}},
        ]
        return [self.normalize_atlas_product(item) for item in self.atlas_collection().aggregate(pipeline)]

    def atlas_vector_candidates(self, query: str, filters: Json, limit: int) -> list[Json]:
        """Run Atlas Automated Embedding search against product descriptions."""

        vector_filter = self.atlas_prefilter_document(filters)
        vector_filter["isActive"] = True
        pipeline: list[Json] = [
            {
                "$vectorSearch": {
                    "index": self.config.mongodb_vector_index_name,
                    "path": "description",
                    "query": query,
                    "model": self.config.embedding_model,
                    "numCandidates": max(limit * 4, 100),
                    "limit": limit,
                    "filter": vector_filter,
                }
            },
            {"$project": {"_id": 0, "productId": "$_id", "vectorScore": {"$meta": "vectorSearchScore"}}},
        ]
        collection = self.atlas_collection()
        return [clone(item) for item in collection.aggregate(pipeline)]

    def atlas_hybrid_results(self, query: str, filters: Json, page: int, limit: int) -> Json:
        """Run Atlas full-text and vector search and fuse candidates."""

        candidate_limit = min(max(page * limit * 4, 60), 400)
        try:
            text_candidates = self.atlas_full_text_candidates(query, filters, candidate_limit)
            vector_candidates = self.atlas_vector_candidates(query, filters, candidate_limit)
        except (EmbeddingError, Exception) as exc:
            raise ProductReadError(f"Unable to run MongoDB Atlas hybrid search: {exc}") from exc

        scores: dict[str, Json] = {}
        max_text = max([float(item.get("textScore") or 0.0) for item in text_candidates] or [1.0])
        max_vector = max([float(item.get("vectorScore") or 0.0) for item in vector_candidates] or [1.0])
        for item in text_candidates:
            product_id = str(item["_id"])
            entry = scores.setdefault(product_id, {"textScore": 0.0, "vectorScore": 0.0})
            entry["textScore"] = float(item.get("textScore") or 0.0) / max(max_text, 1.0)
        for item in vector_candidates:
            product_id = str(item["productId"])
            entry = scores.setdefault(product_id, {"textScore": 0.0, "vectorScore": 0.0})
            entry["vectorScore"] = float(item.get("vectorScore") or 0.0) / max(max_vector, 1.0)

        if not scores:
            return {"results": [], "total": 0, "page": page, "limit": limit, "source": "atlas_hybrid"}

        product_filter = self.atlas_prefilter_document(filters)
        product_filter.update({"_id": {"$in": list(scores)}, "isActive": {"$ne": False}})
        products = {
            str(product["_id"]): self.normalize_atlas_product(product)
            for product in self.atlas_collection().find(product_filter)
        }
        results = []
        for product_id, score_data in scores.items():
            product = products.get(product_id)
            if not product:
                continue
            combined = round((float(score_data["vectorScore"]) * 0.6) + (float(score_data["textScore"]) * 0.4), 6)
            results.append(
                {
                    "product": product,
                    "score": combined,
                    "source": "atlas_hybrid",
                    "textScore": round(float(score_data["textScore"]), 6),
                    "vectorScore": round(float(score_data["vectorScore"]), 6),
                }
            )
        ranked = sorted(results, key=lambda item: item["score"], reverse=True)
        start = max(page - 1, 0) * limit
        return {"results": ranked[start : start + limit], "total": len(ranked), "page": page, "limit": limit, "source": "atlas_hybrid"}

    def atlas_sort(self, sort: str) -> list[tuple[str, int]]:
        """Return Mongo sort fields for supported sort options."""

        if sort == "price_asc":
            return [("price.amount", 1)]
        if sort == "price_desc":
            return [("price.amount", -1)]
        if sort == "newest":
            return [("createdAt", -1)]
        return [("title", 1)]

    def search_atlas_products(self, query: str | None, filters: Json, sort: str, page: int, limit: int) -> Json:
        """Search, filter, sort, and paginate products directly in Atlas."""

        if query:
            hybrid = self.atlas_hybrid_results(query, filters, page, limit)
            items = [item["product"] for item in hybrid["results"]]
            if sort == "price_asc":
                items = sorted(items, key=self.price_amount)
            elif sort == "price_desc":
                items = sorted(items, key=self.price_amount, reverse=True)
            return {"items": items, "total": hybrid["total"], "page": page, "limit": limit, "source": hybrid["source"]}
        document = self.atlas_filter(query, filters)
        skip = max(page - 1, 0) * limit
        try:
            collection = self.atlas_collection()
            total = collection.count_documents(document)
            cursor = collection.find(document).sort(self.atlas_sort(sort)).skip(skip).limit(limit)
            products = [self.normalize_atlas_product(product) for product in cursor]
        except Exception as exc:
            raise ProductReadError(f"Unable to search products in MongoDB Atlas: {exc}") from exc
        return {"items": products, "total": total, "page": page, "limit": limit}

    def local_hybrid_results(self, query: str, filters: Json, page: int, limit: int) -> Json:
        """Blend local keyword and semantic scores for fallback hybrid search."""

        filtered = self.filter_products(self.active_products(), filters)
        candidates: dict[str, Json] = {}
        for product in filtered:
            product_id = str(product["_id"])
            semantic_score = self.semantic_score(product, query)
            keyword_score = self.keyword_score(product, query)
            combined = round((semantic_score * 0.6) + (keyword_score * 0.4), 6)
            if combined > 0:
                candidates[product_id] = {
                    "product": product,
                    "score": combined,
                    "source": "local_hybrid",
                    "textScore": keyword_score,
                    "vectorScore": semantic_score,
                }
        ranked = sorted(candidates.values(), key=lambda item: item["score"], reverse=True)
        start = max(page - 1, 0) * limit
        return {"results": ranked[start : start + limit], "total": len(ranked), "page": page, "limit": limit, "source": "local_hybrid"}

    def hybrid_results(self, query: str, filters: Json, page: int, limit: int) -> Json:
        """Run Atlas hybrid search when possible, falling back to local hybrid ranking."""

        if self.config.mongodb_uri.strip() and not self._atlas_unavailable:
            try:
                atlas = self.atlas_hybrid_results(query, filters, page, limit)
                if atlas["total"] > 0 or not self.core_state_products():
                    return atlas
                local = self.local_hybrid_results(query, filters, page, limit)
                if local["total"] > 0:
                    local["source"] = "local_hybrid_fallback_empty_atlas"
                    for item in local["results"]:
                        item["source"] = local["source"]
                    return local
                return atlas
            except ProductReadError:
                self._atlas_client = None
                self._atlas_unavailable = True
        return self.local_hybrid_results(query, filters, page, limit)

    def search_products(self, query: str | None, filters: Json, sort: str, page: int, limit: int) -> Json:
        """Search, filter, sort, and paginate products."""

        if self.config.mongodb_uri.strip() and not self._atlas_unavailable:
            try:
                atlas = self.search_atlas_products(query, filters, sort, page, limit)
                if not query or atlas["total"] > 0 or not self.core_state_products():
                    return atlas
                local = self.local_hybrid_results(query, filters, page, limit)
                if local["total"] > 0:
                    items = [item["product"] for item in local["results"]]
                    if sort == "price_asc":
                        items = sorted(items, key=self.price_amount)
                    elif sort == "price_desc":
                        items = sorted(items, key=self.price_amount, reverse=True)
                    return {
                        "items": items,
                        "total": local["total"],
                        "page": page,
                        "limit": limit,
                        "source": "local_hybrid_fallback_empty_atlas",
                    }
                return atlas
            except ProductReadError:
                self._atlas_client = None
                self._atlas_unavailable = True
        if query:
            hybrid = self.local_hybrid_results(query, filters, page, limit)
            items = [item["product"] for item in hybrid["results"]]
            if sort == "price_asc":
                items = sorted(items, key=self.price_amount)
            elif sort == "price_desc":
                items = sorted(items, key=self.price_amount, reverse=True)
            return {"items": items, "total": hybrid["total"], "page": page, "limit": limit, "source": hybrid["source"]}
        products = self.filter_products(self.active_products(), filters)
        if sort == "price_asc":
            products = sorted(products, key=self.price_amount)
        elif sort == "price_desc":
            products = sorted(products, key=self.price_amount, reverse=True)
        elif sort == "newest":
            products = sorted(products, key=lambda product: str(product.get("createdAt") or ""), reverse=True)
        start = max(page - 1, 0) * limit
        return {"items": products[start : start + limit], "total": len(products), "page": page, "limit": limit}

    def facets(self) -> Json:
        """Build catalogue facets."""

        products = self.active_products()
        facets: Json = {}
        for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "season", "usage"]:
            values = sorted({str(product.get(field_name)) for product in products if product.get(field_name)})
            facets[field_name] = [
                {"value": value, "count": sum(1 for product in products if str(product.get(field_name)) == value)}
                for value in values
            ]
        prices = [self.price_amount(product) for product in products]
        facets["price"] = {
            "min": min(prices) if prices else 0,
            "max": max(prices) if prices else 0,
            "currency": self.config.demo_currency,
        }
        return facets

    def similar_products(self, product_id_or_slug: str, limit: int) -> list[Json]:
        """Return similar products by category, color, and usage."""

        product = self.find_product(product_id_or_slug)
        if not product:
            return []
        candidates = [candidate for candidate in self.active_products() if candidate.get("_id") != product.get("_id")]

        def score(candidate: Json) -> int:
            return sum(
                1
                for field_name in ["gender", "masterCategory", "subCategory", "articleType", "baseColour", "usage"]
                if candidate.get(field_name) and candidate.get(field_name) == product.get(field_name)
            )

        ranked = sorted(candidates, key=score, reverse=True)
        return ranked[:limit]


read_model = ProductReadModel(settings)
