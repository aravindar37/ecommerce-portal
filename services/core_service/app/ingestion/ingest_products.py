"""CLI wrapper for product ingestion.

Run with:
    python -m app.ingestion.ingest_products --dataset ./dataset
"""

from __future__ import annotations

from app.ingestion.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main())
