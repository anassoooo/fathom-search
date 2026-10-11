# Fathom Constitution

These are the non-negotiable rules for building Fathom (codename `vio`). They override convenience,
deadlines, and individual task descriptions. Every task in [TASKS.md](TASKS.md)
is done only when it satisfies this document. Humans and AI coding agents alike
follow it.

---

## Article I — Honesty

1. **The README claims only what exists.** A feature is listed only once it is
   merged, tested, and reachable from the demo. Planned work goes in
   [PLAN.md](PLAN.md), never in the README's feature list.
2. **Every number is reproducible.** Any metric in the README, CV, or a slide
   must come from a committed eval report that can be regenerated with one
   command. No hand-typed metrics.
3. **Known limitations are written down.** The README keeps a "Limitations"
   section (e.g. eval queries are LLM-generated, product text is title-only).

## Article II — Measure before you claim

1. No retrieval or LLM change is merged without running the eval harness
   against the current baseline.
2. A change that regresses a **gated metric** (Recall@10, NDCG@10,
   filter-extraction accuracy) by more than the tolerance in `eval/gates.yaml`
   fails CI unless the PR explains the trade-off and updates the baseline.
3. Ablations are run one variable at a time. The comparison table always
   includes the simplest baseline (BM25).

## Article III — Architecture boundaries

1. **Python owns all AI logic**: embeddings, retrieval, reranking, LLM calls,
   agent, evaluation. It lives in `backend/`.
2. **The web app is a thin client.** `web/` renders UI and calls the backend
   HTTP API. It never calls Qdrant, an LLM, or an embedding model directly.
3. **The backend is the only writer to Qdrant at query time.** Ingestion writes
   only through the `vio.ingest` CLI.
4. Modules depend inward: `api → agent → search → (embeddings, store)`.
   Lower layers never import higher ones.

## Article IV — Configuration and secrets

1. No hardcoded URLs, model names, API keys, or ports. Everything is read
   through one typed settings object (`vio.config.Settings`, pydantic-settings).
2. Secrets never enter git. `.env*` stays gitignored except `.env.example`,
   which lists every variable with a safe placeholder.
3. LLM providers are swappable through an OpenAI-compatible client. Switching
   between Groq, Ollama, or another provider is a config change, not a code
   change.

## Article V — LLM outputs are untrusted input

1. Every LLM output that drives behavior is parsed into a **Pydantic model** and
   validated, with bounded retries on failure.
2. LLM-produced filters are checked against the real taxonomy and numeric
   bounds before they reach Qdrant. Unknown categories are dropped, not passed
   through.
3. User text is never string-concatenated into a prompt without delimiting.
   Prompts live in versioned files under `backend/src/vio/llm/prompts/`.
4. Agents have a max step count, a per-call timeout, and a deterministic
   fallback (plain search).

## Article VI — Graceful degradation

The system still answers when parts fail:

| Failure        | Behavior                                         |
|----------------|--------------------------------------------------|
| LLM down/slow  | Skip query understanding; raw hybrid search      |
| Reranker slow  | Return fused results un-reranked                 |
| Image encoder  | Text-only search, with a UI notice               |
| Qdrant down    | 503 with a clear error. Never fake results.      |

Every fallback is logged and visible in traces.

## Article VII — Reproducibility

1. A fresh clone runs end-to-end on the committed **sample dataset** with
   `docker compose up` plus one ingest command, in under 10 minutes on a laptop CPU.
2. Python dependencies are locked (`uv.lock`); Node dependencies are locked
   (`package-lock.json`).
3. Ingestion is **idempotent**. Re-running it upserts the same deterministic
   point IDs (`uuid5("vio:{product_id}")`) and never deletes a collection
   unless `--recreate` is passed.
4. Eval datasets are versioned files in `data/eval/`, never regenerated
   silently. A new version gets a new filename.

## Article VIII — Quality bar

1. **Python**: `ruff` (lint + format), `mypy --strict` on `vio/`, and `pytest`.
   **TypeScript**: `eslint`, `tsc --noEmit`.
2. Every module in `search/`, `llm/`, and `agent/` has unit tests. External
   services (Qdrant, LLM) are faked in unit tests and real in integration
   tests marked `@pytest.mark.integration`.
3. CI must be green to merge to `main`.
4. Public functions have type hints. Comments explain *why*, not *what*.

## Article IX — Observability

1. Every request gets a trace ID. LLM calls, retrieval stages, and rerank are
   spans with latency (and token cost where applicable), sent to Langfuse when
   configured and to structured logs always.
2. User interaction events (impression, click, add-to-cart) record which
   retrieval **variant** served them, so online metrics can be compared.

## Article X — Security basics

1. Passwords are hashed with bcrypt or argon2. Sessions are random, httpOnly,
   and expire.
2. The API validates all input with Pydantic, caps payload sizes (images ≤ 5 MB),
   and rate-limits the LLM-backed endpoints.
3. Admin and metrics endpoints require authentication.

## Article XI — Simplicity

1. Build the simplest thing that can be measured, then improve it with eval
   evidence. No speculative abstractions.
2. A dependency is added only when it removes more code or risk than it adds.
   Unused dependencies are deleted.
3. Significant decisions (model choice, fusion method, store) are recorded as a
   short ADR in `docs/adr/NNNN-title.md`: context, decision, alternatives, and
   the consequence.

## Article XII — Workflow

1. Work happens on short-lived branches named `t<id>-short-slug`
   (e.g. `t012-hybrid-retrieval`) and merges to `main` via PR.
2. Commits follow Conventional Commits (`feat:`, `fix:`, `eval:`, `docs:`,
   `chore:`, `refactor:`, `test:`).
3. A task's **Definition of Done**:
   - its acceptance criteria in TASKS.md are met;
   - tests are added and CI is green;
   - eval was run if retrieval or LLM behavior changed;
   - docs and README are updated if user-visible behavior changed;
   - the task's checkbox in TASKS.md is ticked in the same PR.

---

## Governance

- This document is amended only by a PR titled `constitution: …` that states
  the reason. The version and date below are bumped on every amendment.
- When a task conflicts with the constitution, the constitution wins and the
  task is rewritten.

**Version** 1.0.0 · **Ratified** 2026-10-08
