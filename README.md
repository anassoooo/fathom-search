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

**Backend (`backend/`, Python 3.12)**: a skeleton only so far: typed config,
the `vio` CLI, and the lint/type/test toolchain. The search service is being
built in milestone M1.

**Notebooks (`notebooks/`)**: the Colab notebooks that preprocessed the
catalog, computed Bayesian ratings and value scores, and uploaded CLIP text and
image embeddings to Qdrant.

## Limitations (known, being addressed)

- Product text is title-only (`name | category | subcategory | price bucket | price`); there are no descriptions.
- Search quality has **not been measured** yet. The evaluation harness arrives in M2.
- The LLM endpoint is hardcoded to `localhost:11434`, so the assistant needs local Ollama.
- Passwords are hashed with SHA-256 and one shared secret (no per-user salt), not bcrypt (fixed in T053). `/metrics` is not access-controlled.
- The web app uses SQLite through Prisma. Postgres is available in docker compose but not wired up yet (T052).
- The full dataset and images are not in the repo. A committed sample is pending (T002).

## Repository layout

```
backend/     Python package `vio` (FastAPI service, ingestion, eval; in progress)
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

# Backend toolchain
cd ../backend
uv sync
uv run vio --help
uv run pytest
```

The Qdrant collection must be populated before the catalog shows products. For
now that means running the notebooks in `notebooks/`. `vio ingest` replaces
this in T013.

## License

MIT. See [LICENSE](LICENSE).
