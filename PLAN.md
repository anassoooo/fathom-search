# VIO — Project Plan

> Multimodal, evaluation-driven product search and shopping assistant.
> Governed by [CONSTITUTION.md](CONSTITUTION.md). Executed via [TASKS.md](TASKS.md).

---

## 1. Vision

A shopper types *"comfy running shoes for flat feet under $80"* or uploads a
photo. VIO:

1. understands the request (category, price limits, intent);
2. asks one clarifying question if the request is too vague;
3. retrieves products with hybrid search (dense + sparse + image);
4. reranks them;
5. explains *why* each result matches.

Every stage is **measured**: an offline eval harness reports retrieval quality,
filter-extraction accuracy, latency, and cost, and CI blocks regressions.

**Portfolio goal:** a deployed, reproducible system whose README leads with a
real ablation table. It should show applied-AI engineering judgment, not just
API wiring.

## 2. Goals and non-goals

**Goals**
- G1. Hybrid retrieval over about 42K products, with server-side filters and reranking.
- G2. LLM query understanding with validated structured output.
- G3. A tool-calling shopping assistant with a real clarification loop.
- G4. An offline eval harness plus CI gates; online CTR by retrieval variant.
- G5. A live demo on free tiers, runnable locally with one command.

**Non-goals** (explicitly out of scope)
- Payments, checkout, inventory, or order management.
- Custom auth beyond a correct email/password plus sessions.
- Training models from scratch. Fine-tuning is a single, optional stretch task.
- Pixel-perfect UI. The UI exists to demo the AI and to collect events.

## 3. Success metrics (the numbers the README will report)

| Metric                          | Measured by                    | Target                 |
|---------------------------------|--------------------------------|------------------------|
| NDCG@10, Recall@10, MRR         | `vio eval retrieval`           | Beat BM25 baseline     |
| Filter-extraction exact match   | `vio eval query-understanding` | ≥ 90 %                 |
| Clarification decision F1       | `vio eval agent`               | ≥ 0.8                  |
| p50 / p95 search latency        | eval run + traces              | p95 < 800 ms (no LLM)  |
| Cost per 1K assistant queries   | Langfuse token accounting      | Reported, not targeted |
| Online CTR per variant          | `events` table                 | Reported               |

Targets are aspirations. The README reports whatever the eval actually says
(Constitution Art. I).

## 4. Current state (baseline we are migrating from)

- `app/`: Next.js 16 app that does everything, including Qdrant calls, CLIP via
  `@xenova/transformers`, Ollama on a hardcoded localhost, SQLite via Prisma,
  and SHA-256 password hashing.
- `data-pipeline/`: Colab notebooks that read CSV/images from Google Drive and
  embed `name | category | subcategory | bucket | price` with CLIP ViT-B/32
  into named vectors `text` and `image` (512-d, cosine). They **delete and
  recreate** the collection on every run.
- Point IDs are `uuid5(NAMESPACE_URL, "vio:{product_id}")`. **Keep this.**
- Payload: `product_id, name, category, subcategory, price, price_bucket,
  rating, total_ratings, bayes_rating, value_score, image_url`.
- Products have **no long descriptions**; text is title-like. This shapes model
  and eval choices (see §7, §9).

## 5. Target architecture

```
 ┌───────────────┐   HTTPS/JSON    ┌───────────────────────────────────────────┐
 │  web/ Next.js │ ──────────────▶ │ backend/ FastAPI (vio.api)                │
 │  UI, auth,    │                 │                                           │
 │  cart, events │                 │  /v1/search ──▶ search.pipeline           │
 └──────┬────────┘                 │                  ├ query understanding    │──▶ LLM (OpenAI-compatible:
        │ Prisma                   │                  │   (vio.llm, Pydantic)  │     Groq prod / Ollama dev)
        ▼                          │                  ├ retrieve: prefetch     │
 ┌───────────────┐                 │                  │   dense + sparse (+img)│──▶ Qdrant
 │  Postgres     │◀── events ──────│                  │   → RRF fusion, filters│     named vectors:
 │  users, cart, │   (variant id)  │                  └ rerank (cross-encoder) │     text_dense, text_sparse,
 │  events       │                 │  /v1/assistant ──▶ agent (tool calling)   │     image_clip
 └───────────────┘                 │  tracing ──────────────────────────────── │──▶ Langfuse + JSON logs
                                   └───────────────────────────────────────────┘
 Offline:  vio ingest  (CSV → embeddings → Qdrant upsert)
           vio eval    (datasets in data/eval → reports in eval/reports, gated in CI)
```

**Ownership decision (ADR-0001):** the Next.js app keeps users, sessions, cart,
and event logging (via Prisma on Postgres) because that code already exists and
isn't AI logic. Everything that touches Qdrant, embeddings, or LLMs moves to the
Python backend. The web app gets product data only from the backend API.

## 6. Repository layout (target)

```
VIO/
├── CONSTITUTION.md  PLAN.md  TASKS.md  README.md  LICENSE
├── docker-compose.yml           # qdrant, postgres, backend, web
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml  uv.lock  Dockerfile  .env.example
│   ├── src/vio/
│   │   ├── config.py            # pydantic-settings, the only env reader
│   │   ├── cli.py               # `vio ingest|eval|serve`
│   │   ├── api/                 # FastAPI app, routers, schemas, deps
│   │   ├── store/               # Qdrant client wrapper, collection schema
│   │   ├── embeddings/          # dense text, sparse, image encoders (protocols + impls)
│   │   ├── search/              # filters, retrieval, fusion, rerank, pipeline
│   │   ├── llm/                 # client, query understanding, prompts/
│   │   ├── agent/               # tools, loop, clarification policy
│   │   ├── ingest/              # load/clean CSV, build docs, batch upsert
│   │   ├── eval/                # datasets, metrics, runners, report writer
│   │   └── observability/       # tracing, logging, timing
│   └── tests/{unit,integration}/
├── web/                         # renamed from app/
├── data/
│   ├── sample/                  # committed ~500-product CSV (+ thumbnails if small)
│   ├── eval/                    # versioned eval sets: queries_v1.jsonl, qrels_v1.jsonl
│   └── raw/ processed/          # gitignored
├── eval/
│   ├── gates.yaml               # metric thresholds + tolerances used by CI
│   └── reports/                 # committed markdown/JSON reports per run
├── notebooks/                   # EDA only (moved from data-pipeline/notebooks)
└── docs/
    ├── ARCHITECTURE.md
    ├── adr/                     # 0001-backend-owns-ai.md, …
    └── report.pdf
```

## 7. Component design

### 7.1 Configuration
`vio.config.Settings` (pydantic-settings) holds: `QDRANT_URL`, `QDRANT_API_KEY`,
`QDRANT_COLLECTION`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_QUERY`,
`LLM_MODEL_AGENT`, `DENSE_MODEL`, `SPARSE_MODEL`, `IMAGE_MODEL`,
`RERANK_MODEL`, `RERANK_TOP_N`, `LANGFUSE_*`, `CORS_ORIGINS`, `LOG_LEVEL`.

### 7.2 Ingestion (`vio ingest`)
- Input: the processed CSV (same columns as `vio_EDA.csv`) plus an optional image directory.
- Steps: load → validate rows (Pydantic `Product`) → build document text →
  embed in batches (dense, sparse, image) → upsert with deterministic IDs.
- Flags: `--sample`, `--limit N`, `--recreate`, `--only {dense,sparse,image}`,
  `--batch-size`.
- Creates **payload indexes** on `category` and `subcategory` (keyword),
  `price_bucket` (keyword), and `price`, `rating`, `bayes_rating` (float).
- Image embedding for the full 42K runs on Colab GPU. The resulting vectors are
  saved as parquet so the CPU path can upsert precomputed vectors.

### 7.3 Collection schema (v2)
| Named vector  | Model (default)                    | Dim | Distance |
|---------------|------------------------------------|-----|----------|
| `text_dense`  | `BAAI/bge-small-en-v1.5`           | 384 | Cosine   |
| `text_sparse` | `Qdrant/bm25` (fastembed)          | —   | IDF      |
| `image_clip`  | `openai/clip-vit-base-patch32`     | 512 | Cosine   |

Text→image retrieval uses the CLIP **text** encoder on the query against
`image_clip`. That is the one job CLIP's text tower is good at.

### 7.4 Search pipeline (`vio.search`)
1. **Parse** (optional, `use_llm=true`): `QueryUnderstanding` → `ParsedQuery
   {rewritten_query, category?, subcategory?, price_min?, price_max?,
   price_bucket?, sort_hint?, k?, is_vague, missing: [..]}`.
2. **Validate filters** against the cached taxonomy and price bounds, then
   build a Qdrant `Filter`.
3. **Retrieve** with one Qdrant Query API call: `prefetch` dense (top 100) +
   sparse (top 100) [+ CLIP text→image (top 100)] [+ image→image if an image
   was uploaded] → `fusion: RRF` → top 50, with filters applied in every prefetch.
4. **Rerank** the top `RERANK_TOP_N` (default 50) with a cross-encoder
   (`cross-encoder/ms-marco-MiniLM-L-6-v2` for CPU, ablate
   `BAAI/bge-reranker-base`), then return top k.
5. Return results with per-stage timings, the parsed query, the variant ID, and the trace ID.

**Variants** are named configs (`bm25`, `dense`, `hybrid`, `hybrid_rerank`,
`full`) so that eval and online A/B comparisons use exactly the same code paths.

### 7.5 LLM layer (`vio.llm`)
- One `LLMClient` built on the `openai` SDK with a configurable `base_url`
  (Groq, Ollama, and others).
- Structured output via JSON-schema / tool calling + Pydantic validation, with
  up to 2 repair retries, then fall back to "no parse".
- Prompts are versioned files (`prompts/query_understanding.v1.md`). The prompt
  version is logged on every call.
- A small LRU/TTL cache keyed by (prompt version, normalized query).

### 7.6 Assistant agent (`vio.agent`)
- Tools: `search_products(query, filters, k)`, `get_product(id)`,
  `compare_products(ids)`, `similar_products(id)`. `add_to_cart` is exposed as a
  client-side action the web app executes.
- **Clarification policy:** if `ParsedQuery.is_vague` (no category inferable
  *and* no strong semantic signal) → ask exactly one question with 2–4 quick
  replies. Never ask twice in a row.
- Limits: max 4 tool steps, a 20 s budget, and a fallback to plain `/v1/search`.
- The response includes `reply`, `products[]`, `clarification?`, and
  `tool_calls[]` (for the UI and traces).

### 7.7 API (v1)
| Method | Path                           | Purpose                                   |
|--------|--------------------------------|-------------------------------------------|
| GET    | `/health`                      | Liveness, plus Qdrant/LLM reachability    |
| GET    | `/v1/taxonomy`                 | Categories, subcategories, price buckets  |
| POST   | `/v1/search`                   | `{query?, image_b64?, filters?, k, variant?, use_llm?}` |
| GET    | `/v1/products/{id}`            | Single product                            |
| GET    | `/v1/products/{id}/similar`    | Similar by dense + image                  |
| GET    | `/v1/products`                 | Browse with filters + pagination          |
| POST   | `/v1/assistant/chat`           | Agent turn `{messages[], session_id}`     |

The OpenAPI schema is exported to `web/src/lib/api-types.ts` with
`openapi-typescript`, so the frontend types never drift from the backend.

### 7.8 Web (`web/`)
- Keep: catalog, product page, cart, auth, the assistant UI, and the metrics page.
- Change: every product/search call goes to the backend; show a "why this
  result" chip (matched filters plus the top signal); log the `variant` with events.
- Remove: `lib/qdrant.ts`, `lib/clip.ts`, `lib/embeddings.ts`, `lib/ollama.ts`,
  `/api/clip`, and unused Radix and other packages.
- Fix: bcrypt hashing, Postgres datasource, and auth on `/metrics`.

## 8. Evaluation methodology

**Datasets** (`data/eval/`, versioned):
- `queries_v1.jsonl`: about 300 queries in buckets: *specific* ("logitech
  wireless mouse"), *descriptive* ("quiet keyboard for office"), *constrained*
  ("headphones under $50"), *vague* ("gift for my dad"), *noisy* (typos), and
  *image* (product photo → same/similar product).
- `qrels_v1.jsonl`: graded relevance labels (0 = irrelevant, 1 = partial, 2 = exact).
- `query_understanding_v1.jsonl`: query → expected `ParsedQuery` fields.
- `clarification_v1.jsonl`: query → should_clarify (bool).

**Building the labels without bias:**
1. Generate queries with an LLM from **seed products**, telling it to paraphrase
   (not copy title words). Otherwise the dataset favors BM25.
2. **Pool** the top 20 results from every variant (TREC-style), then label
   pooled (query, product) pairs with an LLM judge using a fixed rubric.
3. **Check by hand** a stratified sample of 100 or more pairs. Report
   judge–human agreement (Cohen's κ) in the README.
4. Freeze as `v1`. Any relabel becomes `v2`, and reports state which version they used.

**Metrics:** NDCG@10, Recall@10/50, MRR@10 per bucket and overall; filter
exact-match and per-field accuracy; clarification precision/recall/F1;
latency p50/p95 per stage; tokens and $ per query.

**Reports:** `vio eval all --variants bm25,dense,hybrid,hybrid_rerank,full`
writes `eval/reports/<date>-<git-sha>.md` plus `.json`. CI runs a fast subset
(about 60 queries, no LLM judge) against `eval/gates.yaml`.

## 9. Key risks and mitigations

| Risk | Mitigation |
|------|------------|
| Raw data and images live only in Google Drive | T002: export the processed CSV plus a sample to `data/`; document the source and license |
| Title-only text limits dense retrieval | Hybrid with BM25; optional offline LLM description enrichment as an ablation (watch for eval leakage) |
| LLM-generated eval set is too easy or biased | Paraphrase instruction, pooling, human-checked sample, κ reported |
| CLIP-encoding 42K images on CPU is slow | Run on Colab GPU once; save vectors to parquet; CPU path upserts precomputed |
| Free-tier limits (Qdrant 1 GB, Groq rate limits) | ~42K × 896 floats ≈ 150 MB fits; LLM cache plus a fallback path |
| Cold starts on free hosting hurt the demo | Warm-up on `/health`; keep a recorded demo video as backup |
| Reranker CPU latency | MiniLM-L6 by default; rerank only the top 50; report the latency trade-off |

## 10. Milestones

| ID | Milestone                    | Exit criteria                                                        | Est.   |
|----|------------------------------|----------------------------------------------------------------------|--------|
| M0 | Foundation & honesty         | Repo restructured, README truthful, CI skeleton green, sample data committed | 3–4 d |
| M1 | Backend + ingestion          | `vio ingest --sample` builds collection v2; `/v1/search` serves `hybrid_rerank` | 1.5 wk |
| M2 | Evaluation harness           | Eval sets v1 frozen; ablation report committed; CI gate active        | 1.5 wk |
| M3 | Query understanding + agent  | Validated parsing ≥ target; assistant with clarification; agent eval  | 1.5 wk |
| M4 | Web migration                | Web uses only the backend; events carry the variant; metrics page authed | 1 wk |
| M5 | Ship                         | Deployed demo, README with ablation table, demo video, ADRs           | 1 wk   |
| M6 | Stretch (choose one)         | Fine-tuned embeddings **or** personalization **or** perf work, with eval delta | 1–2 wk |

The critical path is M0 → M1 → M2. M3 and M4 can overlap once M1's API is stable.

## 11. Decisions log

Recorded as ADRs in `docs/adr/`:
- 0001: Backend owns all AI logic; web keeps auth, cart, and events.
- 0002: Qdrant named vectors + server-side RRF (vs. client-side weighted blend).
- 0003: bge-small for text, CLIP only for the image modality.
- 0004: OpenAI-compatible LLM client; Groq in prod, Ollama in dev.
- 0005: Eval labeling with pooling + LLM judge + human audit.
