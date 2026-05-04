"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ApiError, apiFetch } from "@/lib/api";
import type { Product, ProductFacets, ProductList, User } from "@/lib/types";
import { ProductCard } from "./ProductCard";
import { AssistantDrawer } from "./AssistantDrawer";

const PAGE_SIZE = 16;

export function ProductsClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);
  const [men, setMen] = useState(searchParams.get("gender") === "Men");
  const [black, setBlack] = useState(searchParams.get("baseColour") === "Black");
  const [masterCategory, setMasterCategory] = useState(searchParams.get("masterCategory") ?? "");
  const [subCategory, setSubCategory] = useState(searchParams.get("subCategory") ?? "");
  const [articleType, setArticleType] = useState(searchParams.get("articleType") ?? "");
  const [season, setSeason] = useState(searchParams.get("season") ?? "");
  const [usage, setUsage] = useState(searchParams.get("usage") ?? "");
  const [priceMax, setPriceMax] = useState(searchParams.get("priceMax") ?? "");
  const [page, setPage] = useState(Number(searchParams.get("page") ?? "1"));
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState<ProductFacets | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    void loadProducts();
    void loadFacets();
    void loadUser();
  }, []);

  function filterState(overrides: Partial<FilterState> = {}): FilterState {
    return {
      query,
      men,
      black,
      masterCategory,
      subCategory,
      articleType,
      season,
      usage,
      priceMax,
      page,
      ...overrides
    };
  }

  async function loadProducts(overrides: Partial<FilterState> = {}): Promise<void> {
    const state = filterState(overrides);
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (state.query) params.set("query", state.query);
    if (state.men) params.set("gender", "Men");
    if (state.black) params.set("baseColour", "Black");
    if (state.masterCategory) params.set("masterCategory", state.masterCategory);
    if (state.subCategory) params.set("subCategory", state.subCategory);
    if (state.articleType) params.set("articleType", state.articleType);
    if (state.season) params.set("season", state.season);
    if (state.usage) params.set("usage", state.usage);
    if (state.priceMax) params.set("priceMax", state.priceMax);
    params.set("page", String(state.page));
    params.set("limit", String(PAGE_SIZE));
    try {
      const data = await apiFetch<ProductList>(`/api/search/products?${params.toString()}`);
      setProducts(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load products");
    } finally {
      setLoading(false);
    }
  }

  async function loadFacets(): Promise<void> {
    try {
      setFacets(await apiFetch<ProductFacets>("/api/search/facets"));
    } catch {
      setFacets(null);
    }
  }

  async function loadUser(): Promise<void> {
    try {
      setUser(await apiFetch<User>("/api/core/me"));
    } catch {
      setUser(null);
    }
  }

  async function submitSearch(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    await applyState({ query, page: 1 });
  }

  async function applyState(overrides: Partial<FilterState>): Promise<void> {
    const state = filterState(overrides);
    setQuery(state.query);
    setMen(state.men);
    setBlack(state.black);
    setMasterCategory(state.masterCategory);
    setSubCategory(state.subCategory);
    setArticleType(state.articleType);
    setSeason(state.season);
    setUsage(state.usage);
    setPriceMax(state.priceMax);
    setPage(state.page);
    await loadProducts(overrides);
    router.push(`/products?${buildQuery(state).toString()}`);
  }

  async function clearFilters(): Promise<void> {
    setMobileFiltersOpen(false);
    await applyState({
      query: "",
      men: false,
      black: false,
      masterCategory: "",
      subCategory: "",
      articleType: "",
      season: "",
      usage: "",
      priceMax: "",
      page: 1
    });
  }

  async function addToCart(productId: string, size: string): Promise<void> {
    setError("");
    setStatus("");
    try {
      await apiFetch("/api/core/me");
      await apiFetch("/api/core/cart/items", {
        method: "POST",
        body: JSON.stringify({ productId, quantity: 1, size })
      });
      setStatus("Added to bag");
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        window.location.assign(`/login?returnTo=${encodeURIComponent("/products")}`);
        return;
      }
      setError(caught instanceof Error ? caught.message : "Unable to add item to cart");
    }
  }

  function renderFilters() {
    return (
    <div className="filter-sidebar" aria-label="Product filters">
      <div className="filter-sidebar-head">
        <strong>Filters</strong>
        <button type="button" className="secondary filter-close" onClick={() => setMobileFiltersOpen(false)}>Close</button>
      </div>
      <label className="checkbox-label">
        <input type="checkbox" checked={men} onChange={(event) => void applyState({ men: event.target.checked, page: 1 })} />
        Men
      </label>
      <label className="checkbox-label">
        <input type="checkbox" checked={black} onChange={(event) => void applyState({ black: event.target.checked, page: 1 })} />
        Black
      </label>
      <FacetSelect label="Category" value={masterCategory} values={facets?.masterCategory ?? []} onChange={(value) => void applyState({ masterCategory: value, page: 1 })} />
      <FacetSelect label="Subcategory" value={subCategory} values={facets?.subCategory ?? []} onChange={(value) => void applyState({ subCategory: value, page: 1 })} />
      <FacetSelect label="Article type" value={articleType} values={facets?.articleType ?? []} onChange={(value) => void applyState({ articleType: value, page: 1 })} />
      <FacetSelect label="Season" value={season} values={facets?.season ?? []} onChange={(value) => void applyState({ season: value, page: 1 })} />
      <FacetSelect label="Usage" value={usage} values={facets?.usage ?? []} onChange={(value) => void applyState({ usage: value, page: 1 })} />
      <label>
        Max price
        <input inputMode="numeric" value={priceMax} onChange={(event) => setPriceMax(event.target.value)} onBlur={() => void applyState({ priceMax, page: 1 })} placeholder="3000" />
      </label>
      <button type="button" className="secondary" onClick={() => void clearFilters()}>Clear all</button>
    </div>
    );
  }

  return (
    <main className="main">
      <div aria-hidden={assistantOpen}>
        <h1 className="page-title">Products catalogue</h1>
        <p className="lede">
          {user ? "Search fashion products, apply filters, open detail pages, or ask the assistant." : "Search fashion products, apply filters, and open detail pages."}
        </p>
        <form className="toolbar" onSubmit={(event) => void submitSearch(event)}>
          <label className="search-field">
            Search
            <input
              type="search"
              role="searchbox"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search black shoes, tunics, dresses"
            />
          </label>
          <button type="submit">Search</button>
        </form>
        <div className="results-bar">
          <span className={error ? "error" : "status"}>{error || status || (loading ? "Loading products" : "")}</span>
          <button type="button" className="secondary mobile-filter-button" onClick={() => setMobileFiltersOpen(true)}>
            Filter
          </button>
        </div>
        <div className="catalogue-layout">
          {renderFilters()}
          <div>
            {mobileFiltersOpen ? <div className="filter-scrim" onClick={() => setMobileFiltersOpen(false)} /> : null}
            {mobileFiltersOpen ? <div className="mobile-filter-drawer">{renderFilters()}</div> : null}
            <section className="grid" aria-label="Product results">
              {loading
                ? Array.from({ length: PAGE_SIZE }, (_, index) => <div className="skeleton-card" key={index} />)
                : products.map((product) => (
                    <ProductCard key={product._id} product={product} showAdd={Boolean(user)} onAdd={addToCart} />
                  ))}
            </section>
            {total > PAGE_SIZE ? (
              <div className="pager" aria-label="Product pagination">
                <button type="button" className="secondary" disabled={page <= 1} onClick={() => void applyState({ page: page - 1 })}>
                  Previous
                </button>
                <span className="meta">Page {page} of {Math.ceil(total / PAGE_SIZE)}</span>
                <button type="button" className="secondary" disabled={page >= Math.ceil(total / PAGE_SIZE)} onClick={() => void applyState({ page: page + 1 })}>
                  Next
                </button>
              </div>
            ) : null}
            {!loading && !error && products.length === 0 ? (
              <div className="empty-state">
                <div className="empty-mark">◇</div>
                <h2>No products match these filters</h2>
                <p className="meta">Try a broader search, remove a colour, or clear everything and start fresh.</p>
                <button type="button" onClick={() => void clearFilters()}>Clear all filters</button>
              </div>
            ) : null}
          </div>
        </div>
        {user ? (
          <button type="button" className="assistant-fab" onClick={() => setAssistantOpen(true)} aria-label="Open assistant chat">
            <span aria-hidden="true">AI</span>
            <strong>Chat</strong>
          </button>
        ) : null}
      </div>
      {user ? <AssistantDrawer open={assistantOpen} onClose={() => setAssistantOpen(false)} /> : null}
    </main>
  );
}

interface FilterState {
  query: string;
  men: boolean;
  black: boolean;
  masterCategory: string;
  subCategory: string;
  articleType: string;
  season: string;
  usage: string;
  priceMax: string;
  page: number;
}

interface FacetSelectProps {
  label: string;
  value: string;
  values: { value: string; count: number }[];
  onChange: (value: string) => void;
}

function FacetSelect({ label, value, values, onChange }: FacetSelectProps) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">All</option>
        {values.map((item) => (
          <option key={item.value} value={item.value}>
            {item.value}
          </option>
        ))}
      </select>
    </label>
  );
}

function buildQuery(state: FilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.query) params.set("query", state.query);
  if (state.men) params.set("gender", "Men");
  if (state.black) params.set("baseColour", "Black");
  if (state.masterCategory) params.set("masterCategory", state.masterCategory);
  if (state.subCategory) params.set("subCategory", state.subCategory);
  if (state.articleType) params.set("articleType", state.articleType);
  if (state.season) params.set("season", state.season);
  if (state.usage) params.set("usage", state.usage);
  if (state.priceMax) params.set("priceMax", state.priceMax);
  if (state.page > 1) params.set("page", String(state.page));
  return params;
}
