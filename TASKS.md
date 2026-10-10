# VIO — Tasks

Execution backlog for [PLAN.md](PLAN.md). Every task must satisfy the
Definition of Done in [CONSTITUTION.md](CONSTITUTION.md#article-xii--workflow).

**Legend:** `[ ]` todo · `[~]` in progress · `[x]` done · **[P]** can run in parallel
with other [P] tasks in the same milestone · **Deps** must be done first.
Branch name: `t<id>-<slug>`.

---

## M0 — Foundation & honesty

- [x] **T001 · Repo cleanup**
  Delete committed junk: `app/build_log.txt`, `app/prisma_error.txt`,
  `app/prisma_log.txt`, `app/src/app/layout.txt`, `app/src/pages.tsx`,
  `app/src/lib/test-prisma.ts`, `app/src/lib/test-qdrant.ts`, root
  `package-lock.json`. Commit the pending `.gitignore` change.
  *Accept:* `git ls-files` shows none of these; the app still builds.

- [x] **T002 · Recover and commit data** — Deps: T001
  Export `vio_EDA.csv` from Google Drive to `data/processed/` (gitignored).
  Write a sample generator (built as `vio make-sample`) to create a stratified ~500-product sample
  (by category) in `data/sample/products.csv`. Write `data/README.md` with
  the source, license, columns, and row counts.
  *Accept:* the sample is committed and under 1 MB; every category is represented; the README lists all columns.

- [x] **T003 · Restructure repo** — Deps: T001
  `git mv app web`; `git mv data-pipeline/notebooks notebooks`; move
  `data-pipeline/docs/report.pdf` → `docs/`; remove the empty
  `data-pipeline/`. Fix paths in docs.
  *Accept:* the layout matches PLAN §6 (backend may still be empty); `web` builds.

- [x] **T004 · Truthful README** [P] — Deps: T003
  Rewrite the README to list only what exists today, with a "Roadmap → PLAN.md"
  link and a "Limitations" section. Remove references to missing docs, tests,
  and NextAuth.
  *Accept:* every claim in the README can be checked against the code.

- [x] **T005 · Backend skeleton** [P] — Deps: T003
  `backend/` with `uv init`, Python 3.12, `pyproject.toml` (ruff, mypy strict,
  pytest config), `src/vio/__init__.py`, `config.py` (pydantic-settings, all
  vars from PLAN §7.1), a `cli.py` entry point `vio`, `.env.example`, and one
  passing test.
  *Accept:* `uv run vio --help`, `uv run ruff check`, `uv run mypy src`, and `uv run pytest` all pass.

- [x] **T006 · Local infra** [P] — Deps: T005
  `docker-compose.yml` with `qdrant` (pinned version, volume) and `postgres`;
  backend and web services are added later. Write a `make`/`just` file or
  documented commands.
  *Accept:* `docker compose up qdrant postgres` is healthy.

- [~] **T007 · CI skeleton** — Deps: T005
  `.github/workflows/ci.yml`: backend job (uv sync, ruff, mypy, pytest) and
  web job (npm ci, lint, `tsc --noEmit`, build).
  *Accept:* green on `main`.
  *Note:* passes locally (backend: ruff, mypy, pytest, integration; web: lint, typecheck, build). Not yet run on GitHub.

- [x] **T008 · ADR template + ADR-0001** [P] — Deps: T003
  `docs/adr/0000-template.md` and `0001-backend-owns-ai.md`.
  *Accept:* the ADR follows the template: context, decision, alternatives, consequences.

## M1 — Backend + ingestion

- [x] **T010 · Domain models** — Deps: T005
  `vio/models.py`: `Product` (Pydantic, validated from CSV columns),
  `SearchRequest`, `SearchResult`, `ParsedQuery`, `Filters`. Map CSV column
  names → payload field names in one place.
  *Accept:* unit tests parse sample rows; invalid rows raise clear errors.

- [x] **T011 · Qdrant store wrapper** — Deps: T010, T006
  `vio/store/`: client factory from settings; `ensure_collection(recreate=False)`
  with the v2 schema (PLAN §7.3) and payload indexes; `upsert_batch`, `get`,
  `count`, `scroll`.
  *Accept:* an integration test against docker Qdrant creates the schema twice
  (idempotent) and upserts and reads back points.

- [x] **T012 · Embedding encoders** [P] — Deps: T005
  `vio/embeddings/`: `TextDenseEncoder`, `SparseEncoder`, and `ImageEncoder`
  protocols, plus implementations (fastembed bge-small, fastembed bm25,
  transformers or open_clip CLIP with `encode_text` and `encode_image`). Lazy
  model loading; batch API; L2-normalized outputs.
  *Accept:* unit tests check shapes, normalization, and determinism; a fake encoder exists for tests.

- [x] **T013 · Ingest CLI** — Deps: T011, T012
  `vio ingest [--sample|--csv PATH] [--limit N] [--recreate] [--only ...]
  [--vectors-parquet PATH]`. It builds document text, embeds in batches with a
  progress bar, upserts with `uuid5("vio:{product_id}")` IDs, and resumes after
  interruption.
  *Accept:* `vio ingest --sample` on CPU finishes in under 5 minutes; a re-run
  makes no duplicates; the count equals the number of sample rows.

- [ ] **T014 · Colab GPU embedding notebook** [P] — Deps: T012
  `notebooks/embed_full_catalog.ipynb` imports `vio` (pip install from git),
  embeds the full catalog plus images, and writes `vectors.parquet`.
  *Accept:* `vio ingest --vectors-parquet` loads it without recomputing.
  *Note:* the `--vectors-parquet` flag is not built yet; it is part of this task.

- [x] **T015 · Filter builder** [P] — Deps: T010
  `vio/search/filters.py`: `Filters` → Qdrant `Filter`. Validates against the
  taxonomy (unknown values dropped, then logged); clamps prices; handles min > max.
  *Accept:* table-driven unit tests, including invalid LLM-like inputs.

- [x] **T016 · Retrieval + RRF fusion** — Deps: T011, T012, T015
  `vio/search/retrieve.py`: a single Query API call with prefetch over the
  enabled sources (dense, sparse, CLIP text→image, image→image) and RRF
  fusion, with filters applied in every prefetch.
  *Accept:* an integration test on sample data shows that filters are respected
  and each source can be toggled.

- [x] **T017 · Reranker** [P] — Deps: T012
  `vio/search/rerank.py`: cross-encoder over `name | category | subcategory`
  for the top N, with a timeout → falls back to fused order (Art. VI).
  *Accept:* unit test with a fake model; the timeout fallback is tested.

- [x] **T018 · Search pipeline + variants** — Deps: T016, T017
  `vio/search/pipeline.py`: `search(request, variant)` where `variant` ∈
  `bm25|dense|hybrid|hybrid_rerank|full`, defined in `variants.py`. It returns
  results plus per-stage timings.
  *Accept:* each variant runs on sample data; timings are populated.

- [x] **T019 · FastAPI app** — Deps: T018
  `vio/api/`: app factory, CORS, request-ID middleware, error handlers;
  routes `/health`, `/v1/taxonomy`, `/v1/search`, `/v1/products`,
  `/v1/products/{id}`, `/v1/products/{id}/similar`. Image payload ≤ 5 MB.
  Taxonomy cached at startup.
  *Accept:* tests with `httpx.AsyncClient` and fakes; `/docs` renders; `vio serve` works.

- [x] **T020 · Observability base** [P] — Deps: T019
  `vio/observability/`: structured JSON logging, a `timed()` span helper, and
  optional Langfuse integration (a no-op when unconfigured).
  *Accept:* every search log line has the trace ID, variant, and stage timings.
  *Note:* JSON logs are done. The Langfuse integration moves to T040, where the first LLM calls appear.

- [x] **T021 · Backend Dockerfile** — Deps: T019
  Multi-stage uv image; models pre-downloaded at build time or cached in a
  volume; add the `backend` service to compose.
  *Accept:* `docker compose up` gives a healthy `/health` that reports Qdrant as reachable.

## M1.5 — Data quality & trust

Goal: the catalog becomes a *trusted* source only after its quality is measured
against an explicit contract. Problems are fixed, flagged, or quarantined by a
documented policy, never silently. Report: `data/reports/quality_report.md`.

- [x] **T080 · Quality framework + data contract** — Deps: T002
  `vio/quality/`: a check registry where each check returns `{name, dimension, severity,
  metric, threshold, passed, n_affected, examples}`. Dimensions: completeness,
  uniqueness, validity, consistency, plausibility, text integrity, label quality.
  Thresholds live in `data/contract.toml`. `vio data audit --csv PATH` writes a
  Markdown + JSON report and exits non-zero when a *blocking* check fails.
  *Accept:* the audit runs on the full CSV and the sample; unit tests cover each check on crafted rows.

- [x] **T081 · Verify and recompute derived features** — Deps: T080
  Reproduce `bayes_rating`, `value_score`, and `price_bucket` from their notebook
  definitions (verification check). Recompute the Bayesian rating with an
  **empirical-Bayes** prior estimated from the data (per-category mean C, prior
  strength m = σ²/τ² by method of moments) instead of the notebook's m = median price.
  Keep the source values as `*_source` for traceability. ADR-0003.
  *Accept:* the report shows the reproduction error and the estimated m with method;
  a ranking comparison (old vs new) shows what changes.

- [x] **T082 · Statistical outlier detection** [P] — Deps: T080
  Robust z-score on log(price) within subcategory (median/MAD, Iglewicz–Hoaglin
  |z| > 3.5, min group size); low-evidence ratings (few reviews).
  *Accept:* flagged rows have reason codes; the $40,922 chair is flagged.

- [x] **T083 · Label-noise detection (confident learning)** [P] — Deps: T080
  TF-IDF (word + char n-grams) on titles → logistic regression → 5-fold
  out-of-fold probabilities → flag products whose given categories all have low
  probability, using per-class thresholds (cleanlab-style).
  *Accept:* a manual audit of a random sample of flags estimates precision;
  per-category noise rates are reported.

- [x] **T084 · Text integrity checks** [P] — Deps: T080
  Mojibake (U+FFFD), HTML entities, brand-only titles, all-caps, whitespace
  anomalies, truncation markers.
  *Accept:* counts and examples are in the report.

- [x] **T085 · Quality flags + handling policy** — Deps: T081–T084
  `Product.quality_flags` stored in the payload; a policy table (fix / flag /
  quarantine) per issue; ingest applies it; eval seed selection (M2) excludes flagged products.
  *Accept:* policy documented in `data/README.md`; flags are queryable in Qdrant.

- [x] **T086 · Visual EDA report** — Deps: T081–T083
  Figures for the report: price distribution by category, rating vs evidence
  (raw vs Bayesian shrinkage), label-noise by category, quality-flag summary.
  *Accept:* figures are generated by `vio data audit --figures` and embedded in the report.

- [x] **T087 · Contract in CI** — Deps: T080, T007
  CI runs `vio data audit` on the committed sample against the contract.
  *Accept:* breaking a sample row fails CI.

## M2 — Evaluation harness

- [x] **T030 · Metrics library** — Deps: T010
  `vio/eval/metrics.py`: NDCG@k (graded), Recall@k, MRR@k, precision/recall/F1,
  and latency percentiles.
  *Accept:* unit tests against hand-computed examples.

- [ ] **T031 · Query generation** — Deps: T019, T085
  `vio eval gen-queries`: picks seed products stratified by category, uses an
  LLM (paraphrase instruction) to produce queries in the six buckets (PLAN §8),
  and writes `data/eval/queries_v1.jsonl` with the seed ID and bucket.
  *Accept:* about 300 queries; token overlap with seed titles is reported and kept low.

- [ ] **T032 · Pooling + LLM judge** — Deps: T031, T018
  `vio eval pool` (top 20 from every variant) and `vio eval judge` (fixed
  rubric prompt, graded 0/1/2, cached) → `qrels_v1.jsonl`.
  *Accept:* every query has ≥ 1 relevant document; the judge prompt is versioned.

- [ ] **T033 · Human audit tool** [P] — Deps: T032
  `vio eval audit` presents a stratified sample of 100 pairs in the terminal and
  stores human labels; computes Cohen's κ against the judge.
  *Accept:* the κ value is written to the report and the README.

- [ ] **T034 · Retrieval eval runner + report** — Deps: T030, T032
  `vio eval retrieval --variants ...` → `eval/reports/<date>-<sha>.{md,json}`
  with an overall table, per-bucket table, and latency.
  *Accept:* the first committed report contains the full ablation table.

- [ ] **T035 · CI eval gate** — Deps: T034, T007
  `eval/gates.yaml` (baseline + tolerance); `vio eval gate` runs a 60-query
  subset on the sample collection in CI with no LLM.
  *Accept:* a deliberately broken retriever fails CI.

- [ ] **T036 · ADR-0004, 0005, 0007** [P] — Deps: T034
  Record the fusion, embedding-model, and labeling decisions, citing report numbers.

## M3 — Query understanding + agent

- [ ] **T040 · LLM client** — Deps: T005
  `vio/llm/client.py`: OpenAI SDK with `base_url`; `structured(prompt, schema)`
  with JSON-schema output, Pydantic validation, ≤ 2 repair retries, timeout,
  token/cost accounting, and a TTL cache.
  *Accept:* unit tests with a fake transport cover retry, failure, and caching.

- [ ] **T041 · Query understanding** — Deps: T040, T015
  `vio/llm/query_understanding.py` plus `prompts/query_understanding.v1.md`,
  with the taxonomy injected and user text delimited. Produces `ParsedQuery`.
  Wired into the `full` variant. Falls back to no-parse on failure.
  *Accept:* integration test with Ollama/Groq; the fallback is tested.

- [ ] **T042 · Query-understanding eval** — Deps: T041, T030
  `data/eval/query_understanding_v1.jsonl` (about 150, hand-checked) and
  `vio eval query-understanding` → per-field accuracy plus exact match. Compare
  2 models and 2 prompt versions.
  *Accept:* the report section is added; the best config is set as default.

- [ ] **T043 · Agent tools + loop** — Deps: T041, T018
  `vio/agent/`: tool schemas, an executor, and a loop with max 4 steps and a
  20 s budget, with fallback to plain search. Returns `reply, products,
  clarification?, tool_calls`.
  *Accept:* unit tests with a scripted fake LLM cover each path (answer, clarify, tool error, budget exceeded).

- [ ] **T044 · Clarification policy** — Deps: T043
  Decides from `ParsedQuery.is_vague` and `missing`; one question with 2–4
  quick replies; never asks twice in a row.
  *Accept:* unit tests; the policy is documented in code.

- [ ] **T045 · `/v1/assistant/chat` endpoint** — Deps: T043, T044, T019
  Rate-limited, traced.
  *Accept:* an API test drives a 2-turn conversation (clarify → results).

- [ ] **T046 · Agent eval** — Deps: T045, T030
  `data/eval/clarification_v1.jsonl` (about 100) plus tool-choice cases;
  `vio eval agent` → clarification F1, tool accuracy, steps, latency, cost.
  *Accept:* report section added; ADR-0006 written.

## M4 — Web migration

- [ ] **T050 · Typed API client** — Deps: T019
  Generate `web/src/lib/api-types.ts` from OpenAPI (`openapi-typescript`)
  plus a thin `web/src/lib/api.ts`. Add an npm script `gen:api`.
  *Accept:* `tsc` passes; CI checks that the generated file is up to date.

- [ ] **T051 · Swap web data paths** — Deps: T050
  Catalog, product page, similar products, and assistant now call the backend.
  Delete `lib/qdrant.ts`, `lib/clip.ts`, `lib/embeddings.ts`, `lib/ollama.ts`,
  `/api/clip`, `/api/products*`, `/api/categories`, and `/api/assistant/recommend`.
  *Accept:* `grep -r qdrant web/src` is empty; all pages work against the backend.

- [ ] **T052 · Postgres + Prisma fix** [P] — Deps: T006
  Datasource → postgresql; pin Prisma 6 (or migrate config for 7 properly);
  move `@prisma/client` to dependencies; first migration.
  *Accept:* `npx prisma migrate dev` works against compose Postgres.

- [ ] **T053 · Auth hardening** [P] — Deps: T052
  bcrypt hashing; random session IDs; auth required on `/metrics` and
  `/api/metrics`; input validation with zod.
  *Accept:* tests or a manual checklist in the PR; no `default-secret` fallback remains.

- [ ] **T054 · Variant-tagged events** — Deps: T051, T052
  Search responses carry `variant` and `trace_id`; impression, click, and
  add-to-cart events store them. Optional variant assignment per session.
  *Accept:* the metrics page shows CTR per variant.

- [ ] **T055 · Assistant UI** — Deps: T045, T051
  Chat UI with clarification quick replies, product cards, and "why this
  result" chips; add-to-cart as a client action.
  *Accept:* the clarify → results flow works end to end.

- [ ] **T056 · Dependency diet** [P] — Deps: T051
  Remove unused packages (Radix components, `@xenova/transformers`, `ai`,
  `@neondatabase/serverless` if unused, and others). Rename the package from
  `my-v0-project`.
  *Accept:* `npx depcheck` is clean; the build passes.

## M5 — Ship

- [ ] **T060 · Deploy backend** — Deps: T021
  Render, Fly.io, or Hugging Face Spaces; Qdrant Cloud; full catalog ingested
  from parquet; secrets in platform env vars.
  *Accept:* the public `/health` is green.

- [ ] **T061 · Deploy web** — Deps: T060, T051
  Vercel plus Neon Postgres; CORS locked to the web origin.
  *Accept:* the public demo URL works for search and the assistant.

- [ ] **T062 · Final README** — Deps: T034, T046, T061
  Demo GIF, live link, architecture diagram, **ablation table from the latest
  report**, κ, limitations, quickstart (`docker compose up` + `vio ingest
  --sample`).
  *Accept:* a fresh clone following the README works in under 10 minutes.

- [ ] **T063 · Demo video + docs** [P] — Deps: T061
  A 2-minute walkthrough; update `docs/ARCHITECTURE.md` to match reality.

## M6 — Stretch (pick one)

- [ ] **T070 · Fine-tune text embeddings**
  Contrastive fine-tune of bge-small on (query, product) pairs (train split
  only; keep `queries_v1` test split held out). Report the NDCG delta and add a `ft` variant.

- [ ] **T071 · Personalization rerank**
  Session-level click history → a feature in rerank; offline replay eval plus online CTR.

- [ ] **T072 · Performance work**
  Embedding cache, ONNX/quantized reranker, query-result cache; before/after p95 in the report.
