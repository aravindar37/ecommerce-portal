import Link from "next/link";

export default function HomePage() {
  return (
    <>
      <section className="band">
        <div className="hero">
          <div className="hero-copy">
            <h1>Codex Fashion</h1>
            <p>
              Browse the local fashion product catalogue, search with natural language, checkout with INR demo totals,
              and use Codex assistants for shopping and returns.
            </p>
            <p>
              <Link className="button" href="/products">
                Browse products
              </Link>
            </p>
          </div>
          <div className="hero-lookbook" aria-label="Featured products">
            <img src="/product-images/15970.jpg" alt="Navy casual shirt" />
            <img src="/product-images/9204.jpg" alt="Black casual shoes" />
            <img src="/product-images/59263.jpg" alt="Silver watch" />
          </div>
        </div>
      </section>
      <main className="main">
        <div className="admin-grid">
          <section className="panel">
            <h2>Semantic Search</h2>
            <p className="meta">Keyword, filters, and hybrid product retrieval through Search Service.</p>
          </section>
          <section className="panel">
            <h2>Demo Checkout</h2>
            <p className="meta">Authenticated cart and order flow with INR totals from Core Service.</p>
          </section>
          <section className="panel">
            <h2>Codex Support</h2>
            <p className="meta">Shopping and return agents call backend services through safe tools.</p>
          </section>
        </div>
      </main>
    </>
  );
}
