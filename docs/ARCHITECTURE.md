# Architecture

This page describes the **current** system. The target architecture is in
[PLAN.md §5](../PLAN.md#5-target-architecture). Decisions are recorded in [adr/](adr/).
The page is rewritten to match reality at the end of M5 (T063).

## Current (pre-migration)

```
Browser ──▶ Next.js (web/)
              ├─ /api/assistant/recommend ─▶ Ollama (localhost:11434) → rewritten query + filters
              │                             └▶ /api/clip (CLIP via @xenova/transformers) → vectors
              ├─ /api/products*, /api/categories ─▶ Qdrant REST (named vectors `text`, `image`)
              └─ auth, cart, events, metrics ─▶ Prisma → SQLite

Offline: notebooks/ (Colab) → CLIP ViT-B/32 text+image embeddings → Qdrant `vio_products`
```

## Target (after M4)

The Python backend (`backend/`, package `vio`) owns embeddings, hybrid
retrieval, reranking, LLM query understanding, the agent, ingestion, and
evaluation. `web/` calls it over HTTP and keeps only auth, cart, and events
(Postgres). See [ADR-0001](adr/0001-backend-owns-ai.md).
