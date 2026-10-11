# Architecture

The overview diagram and search pipeline are in the [README](../README.md#architecture);
hosting details are in [DEPLOYMENT.md](DEPLOYMENT.md); decisions are in [adr/](adr/).

## Components

| Component | Code | Runs on | Responsibility |
|---|---|---|---|
| Web app | `web/` (Next.js 16) | Vercel | UI, auth (bcrypt + random sessions), cart, interaction events, metrics; `/api/*` route handlers are thin, typed proxies to the backend |
| Search API | `backend/src/vio/api` (FastAPI) | Azure Container Apps | `/v1/search`, `/v1/products`, `/v1/products/{id}`, `/similar`, `/v1/taxonomy`, `/health` |
| Search pipeline | `backend/src/vio/search` | (inside the API) | filter validation, hybrid retrieval (RRF), category boost, cross-encoder rerank, degradation |
| LLM layer | `backend/src/vio/llm` | (inside the API) | OpenAI-compatible client (Groq/Ollama), validated JSON, retries, quota handling, query understanding |
| Encoders | `backend/src/vio/embeddings` | (inside the API) | fastembed ONNX models: bge-small, BM25, CLIP text/vision; CPU or CUDA |
| Ingestion | `backend/src/vio/ingest` | laptop (GPU) | CSV → validate → normalize (merge duplicates, category aliases) → empirical-Bayes ratings → quality flags → embed → upsert |
| Data quality | `backend/src/vio/quality` | laptop / CI | contract-driven audit, derived-feature verification, outliers, confident learning, figures |
| Evaluation | `backend/src/vio/eval` | laptop (+ daily scheduled job) | query generation, pooling + LLM judge, metrics with CIs, human audit, reports |
| Vector store | — | Qdrant Cloud | named vectors `text_dense`, `text_sparse`, `image_clip`; payload indexes |
| Relational store | `web/prisma` | Neon Postgres | users, sessions, cart items, assistant history, events |

## Boundaries (Constitution Art. III)

- All AI logic (embeddings, retrieval, LLM calls, evaluation) lives in Python. The web app
  never calls Qdrant or an LLM directly ([ADR-0001](adr/0001-backend-owns-ai.md)).
- Offline evaluation calls the same `vio.search` code as production, so offline and online
  numbers describe the same system; events record the variant that served them.
- The web ↔ backend contract is the exported OpenAPI schema (`backend/openapi.json`),
  from which `web/src/lib/api-types.ts` is generated.
