# 0001 — Python backend owns all AI logic; web keeps auth, cart, and events

- **Status:** accepted
- **Date:** 2026-10-08
- **Task:** T008

## Context
The original app did everything inside Next.js API routes: Qdrant queries, CLIP
inference via `@xenova/transformers`, calls to a hardcoded local Ollama, auth,
cart, and analytics. This had problems:
- The server called its own `/api/clip` over HTTP via `localhost:3000`, which is fragile.
- The ML ecosystem we need (fastembed, sentence-transformers cross-encoders, eval
  tooling, fine-tuning) is Python-first.
- Retrieval logic in TypeScript could not be reused by offline evaluation.

## Decision
A FastAPI service in `backend/` (package `vio`) owns embeddings, retrieval,
reranking, LLM calls, the agent, ingestion, and evaluation. The Next.js app in
`web/` is a client of its HTTP API. Users, sessions, cart, and interaction
events stay in Next.js with Prisma on Postgres, because that code works and
isn't AI logic.

## Alternatives considered
| Option | Why not |
|---|---|
| Keep everything in Next.js | No shared code path between serving and offline eval; weak ML library support |
| Move auth/cart/events to FastAPI too | Rewrites working code with no AI or learning value; delays the critical path |
| Separate microservices per stage | Overkill for one developer; more deploy surface on free tiers |

## Consequences
- Two deployables (web, backend) and one typed contract between them (OpenAPI → TS types, T050).
- Offline eval calls the exact same `vio.search` code as production (Constitution Art. II).
- Events must carry the retrieval `variant` returned by the backend so online and offline metrics line up (T054).
