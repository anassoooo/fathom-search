# VIO — multimodal product search

> **Status: under active rebuild.** This README describes only what exists
> today. The target system and roadmap are in [PLAN.md](PLAN.md), the
> engineering rules in [CONSTITUTION.md](CONSTITUTION.md), and progress in
> [TASKS.md](TASKS.md).

VIO is a product-discovery app over a catalog of about 42K Amazon products.
Shoppers can browse, search with natural language or a photo, and get
recommendations from an AI assistant.

## What works today

**Web app (`web/`, Next.js 16, TypeScript)**
- Catalog browsing with category filter and pagination, product pages, and
  "similar products" (Qdrant vector similarity).
- Assistant: a text and/or image query goes to a local LLM (Ollama,
  `qwen2.5:3b-instruct`), which rewrites the query and extracts price/category
  filters as JSON. The query is then embedded with CLIP ViT-B/32
  (`@xenova/transformers`) and searched in Qdrant. If CLIP fails, it falls back
  to keyword matching.
- Email/password accounts, cart, assistant history.
- Interaction event logging (impressions, clicks, add-to-cart) and a `/metrics`
  page with CTR and add-to-cart rate.

**Search backend (`backend/`, Python 3.12, FastAPI)**: not yet used by the web app (that switch is M4).
- `vio ingest` loads the catalog CSV with per-row validation and embeds each
  product three ways: dense text (bge-small), sparse BM25, and CLIP image. It
  upserts into Qdrant with deterministic IDs, and re-runs skip existing products.
- `POST /v1/search` runs hybrid retrieval in a single Qdrant query: dense, BM25,
  and CLIP text→image (plus image→image for photo queries) as prefetches, fused
  with RRF, with filters applied inside every prefetch. A cross-encoder then
  reranks the top 30.
- Named variants (`bm25`, `dense`, `hybrid`, `hybrid_rerank`) select which
  stages run, so they can be compared directly.
- When something fails, search degrades instead of erroring: a slow reranker
  falls back to fused order, and an unreadable image falls back to text-only.
- Catalog endpoints: browse with filters, product detail, similar products, taxonomy.
- Structured JSON logs with request IDs and per-stage timings.
- All models run on CPU through ONNX (fastembed); no PyTorch.
- Tests: 86 unit tests (in-memory Qdrant, fake encoders) plus
  integration tests against a real Qdrant and the real models.

**Data quality (`vio data audit`)**: the catalog is treated as trusted only after it
passes a reviewed data contract (`data/contract.toml`). Latest report:
[`data/reports/quality_report.md`](data/reports/quality_report.md). 23 checks:
- **Schema, completeness, validity, uniqueness.** Blocking failures stop ingestion.
- **Consistency.** The source's derived columns are re-derived from their formulas.
  This exposed a **unit error in the source Bayesian rating** (prior strength set to
  median *price*), now replaced by an empirical-Bayes prior fitted on the data:
  m = 43 reviews, 95% CI 38 to 51 ([ADR-0003](docs/adr/0003-empirical-bayes-rating-prior.md)).
- **Plausibility.** Robust log-price outliers within subcategory (MAD z-score with a
  practical-significance gate) and low-evidence ratings.
- **Label quality.** Confident learning on a title → category classifier (89.8% CV
  accuracy) flags 4.3% of products. A manual audit of a random 40 found 12.5% real
  errors (Wilson CI 5.5–26%), mostly keyword collisions in the original scrape;
  72.5% are taxonomy overlap.
- **Text integrity.**

Findings become row-level `quality_flags`, handled by a documented policy (block /
merge / recompute / flag) in [`data/README.md`](data/README.md). CI enforces the
contract on the committed sample.

**Notebooks (`notebooks/`)**: the Colab notebooks that preprocessed the
catalog, computed Bayesian ratings and value scores, and uploaded CLIP text and
image embeddings to Qdrant.

## Limitations (known, being addressed)

- Product text is title-only; 12% of titles are just a brand name (97% of Footwear), so text search has little to work with there.
- Search quality has **not been measured** yet. The evaluation harness arrives in M2. The backend has only been run on a 24-product test fixture.
- `full` (LLM query understanding) behaves like `hybrid_rerank` until M3.
- The LLM endpoint is hardcoded to `localhost:11434`, so the assistant needs local Ollama.
- Passwords are hashed with SHA-256 and one shared secret (no per-user salt), not bcrypt (fixed in T053). `/metrics` is not access-controlled.
- The web app uses SQLite through Prisma. Postgres is available in docker compose but not wired up yet (T052).
- The full dataset and images are not in the repo; a 501-row sample is (`data/sample/`).

## Repository layout

```
backend/     Python package `vio`: ingestion, hybrid search, FastAPI service
web/         Next.js app
notebooks/   Colab notebooks for preprocessing, EDA, and legacy embedding upload
docs/        Architecture notes, ADRs (docs/adr/), original project report
docker-compose.yml   Local Qdrant + Postgres
```

## Running locally

Prerequisites: Node 22+, Docker, [uv](https://docs.astral.sh/uv/), and
optionally Ollama for the assistant.

```bash
# Infrastructure
docker compose up -d qdrant postgres

# Web app
cd web
npm ci                         # also runs `prisma generate`
echo 'DATABASE_URL="file:./dev.db"' > .env
echo 'QDRANT_URL=http://localhost:6333' >> .env
echo 'QDRANT_API_KEY=local' >> .env       # required by web; ignored by local Qdrant
echo 'QDRANT_COLLECTION=vio_products' >> .env
npx prisma db push
npm run dev                    # http://localhost:3000

# Search backend
cd ../backend
uv sync
uv run pytest                                   # unit tests, no services needed
uv run vio ingest --csv tests/fixtures/products.csv   # first run downloads ~700 MB of ONNX models
uv run vio serve                                # http://127.0.0.1:8000/docs
# or containerized (models baked into the image):
docker compose up -d --build backend            # http://localhost:8000/docs
```

The web app still reads the legacy v1 collection (`vio_products`), which the
notebooks in `notebooks/` populate. The backend uses the v2 collection
(`vio_products_v2`) written by `vio ingest`.

## License

MIT. See [LICENSE](LICENSE).
