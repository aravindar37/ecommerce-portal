from tests.helpers.test_client import (
    search_client,
    expect_activity,
    expect_ok,
    first_product,
    response_meta,
)


def test_catalogue_lists_active_products_with_dataset_and_ecommerce_fields() -> None:
    data = expect_ok(search_client().get("/api/products?limit=12"))
    assert data["total"] >= len(data["items"])
    assert data["items"]

    product = data["items"][0]
    for field in [
        "_id",
        "sourceProductId",
        "slug",
        "title",
        "price",
        "gender",
        "masterCategory",
        "subCategory",
        "articleType",
        "baseColour",
        "images",
        "inventory",
        "tags",
        "ratingAverage",
        "ratingCount",
    ]:
        assert field in product


def test_product_detail_by_slug_records_product_selection_activity() -> None:
    client = search_client()
    product = first_product(client)
    detail = expect_ok(client.get(f"/api/products/{product['slug']}"))

    assert detail["slug"] == product["slug"]
    assert isinstance(detail["images"], list)
    expect_activity("product_detail_viewed")


def test_facets_expose_catalogue_filters() -> None:
    facets = expect_ok(search_client().get("/api/facets"))
    for facet in [
        "gender",
        "masterCategory",
        "subCategory",
        "articleType",
        "baseColour",
        "season",
        "usage",
        "price",
    ]:
        assert facet in facets


def test_keyword_search_supports_filters_sort_and_pagination() -> None:
    client = search_client()
    response = client.get(
        "/api/products?query=black%20shoes&gender=Men&baseColour=Black&sort=price_asc&page=1&limit=12"
    )
    data = expect_ok(response)
    meta = response_meta(response)

    assert data["page"] == 1
    assert isinstance(data["items"], list)
    assert meta["searchMode"] == "hybrid"
    assert meta["filtersAppliedTo"] == ["fullText", "vector"]
    expect_activity("search_performed")
    expect_activity("filter_applied")


def test_search_service_owns_default_hybrid_product_search() -> None:
    client = search_client()
    response = client.get(
        "/api/search/products?query=black%20shoes&gender=Men&sort=relevance&page=1&limit=12"
    )
    data = expect_ok(response)
    meta = response_meta(response)

    assert data["page"] == 1
    assert isinstance(data["items"], list)
    assert meta["searchMode"] == "hybrid"
    expect_activity("search_performed")


def test_semantic_search_returns_ranked_products_and_embedding_metadata() -> None:
    client = search_client()
    response = client.post(
        "/api/search/semantic",
        json={
            "query": "lightweight black running shoes for men under 3000",
            "filters": {"gender": ["Men"], "priceMax": 3000},
            "limit": 10,
            "page": 1,
        },
    )
    data = expect_ok(response)
    meta = response_meta(response)

    assert isinstance(data["results"], list)
    assert meta["provider"]
    assert meta["model"]
    assert meta["dimensions"]


def test_hybrid_search_deduplicates_keyword_and_vector_results() -> None:
    client = search_client()
    response = client.post(
        "/api/search/hybrid",
        json={"query": "casual red shoes", "filters": {"usage": ["Casual"]}, "limit": 20},
    )
    data = expect_ok(response)
    meta = response_meta(response)

    ids = [item["product"]["_id"] for item in data["results"]]
    assert len(set(ids)) == len(ids)
    assert meta["searchMode"] == "hybrid"
    assert meta["filtersAppliedTo"] == ["fullText", "vector"]


def test_search_index_definitions_include_full_text_and_vector_prefilters() -> None:
    definitions = expect_ok(search_client().get("/api/indexes/definitions"))
    product_index = definitions["products"]
    vector_index = definitions["productEmbeddings"]

    assert product_index["type"] == "search"
    assert vector_index["type"] == "vectorSearch"
    product_fields = product_index["definition"]["mappings"]["fields"]
    assert "gender" in product_fields
    assert "price" in product_fields
    vector_paths = {field["path"] for field in vector_index["definition"]["fields"]}
    assert {"metadata.gender", "metadata.baseColour", "metadata.priceAmount", "provider", "model"}.issubset(vector_paths)
