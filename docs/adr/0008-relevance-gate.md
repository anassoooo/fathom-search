# 0008 — A learned relevance gate instead of a fixed top-12

- **Status:** accepted
- **Date:** 2026-10-30
- **Task:** —

## Context
Search always showed exactly 12 products. That is wrong in both directions:

- When only a few products fit, the rest of the 12 are noise. A request the catalog cannot
  serve at all ("plumber to fix a leaking pipe", "zzzz") still got 12 products.
- When many fit, everything after 12 was hidden. In the judged pool the median query has
  16 relevant products, and 57% have more than 12.

The cross-encoder orders well *within* a query (mean per-query ROC-AUC 0.83) but its raw
score does not transfer *across* queries (global ROC-AUC 0.76): a score that means
"relevant" for one query means "irrelevant" for another. A single threshold on it empties
17% of real queries at P ≥ 0.5 after calibration.

Constraints: no extra retrieval calls per search (latency), and no scikit-learn in the
production image (it lives in the `data` dependency group).

## Decision
A logistic regression on 8 **query-relative** features of the reranked top-30
(`vio.search.gate.features`: score, gap to the query's best score, within-query z-score,
rank, best score, top margin, spread, pre-rerank fused position) gives each candidate
P(relevant). Products with P ≥ 0.6 are **matches**; the rest are **related** (behind
"Show more"). If even the best P is below 0.7, the response says **no close match** and
the app shows the 3 nearest products under that heading instead of an empty page.

The same `features` function serves training (`vio eval gate`) and serving, so they
cannot drift. Weights ship as `backend/src/vio/search/gate_v1.json` and are applied with
plain Python. The gate is skipped (and the app falls back to 12 shown) when there is no
cross-encoder score: photo-only search, or a reranker timeout. A gate fit for another
reranker or list size refuses to load.

## Alternatives considered
| Option | Why not |
|---|---|
| Fixed top-k (status quo) | Precision 0.616; noise on narrow queries, hidden products on broad ones. |
| Threshold on the calibrated cross-encoder score | Score is not comparable across queries: precision 0.68 / recall 0.54 at P ≥ 0.5, with 17% of real queries left empty. |
| Add BM25 and dense ranks as features | +0.005 AUC for three extra Qdrant queries per search. |
| Gradient boosting instead of logistic regression | Lower out-of-fold AUC (0.78 vs 0.80) on ~7,500 labels; harder to ship and explain. |
| Train the item gate on no-answer queries too | Flags 98% of them, but recall on real queries fell 0.61 → 0.55 and 17% of real queries were emptied: one model asked two questions. |
| A separate query-level "is there any answer?" model | AUC 0.945 vs 0.936 for the simple best-P floor; not worth a second model. Its first version scored 0.977 only by learning query length, an artefact of how the two query sets were written. |
| Show nothing below the floor | A wrong flag (5% of real queries at 0.7) would cost the results, not just a label. |

## Consequences
Measured in [`eval/reports/2026-10-30-c130a73-gate.md`](../../eval/reports/2026-10-30-c130a73-gate.md)
(275 judged text queries, out-of-fold; 137 hand-written no-answer queries):

- Precision of what is shown: 0.616 → 0.757 (+0.141, 95% CI +0.105 to +0.178).
- Recall within the top-30: 0.568 → 0.616 (+0.049, CI −0.002 to +0.093; not significant).
- Average products shown 12 → 10.6, adapting per query (25 for "wireless noise cancelling
  headphones", 1 for "plumber to fix a leaking pipe").
- No-answer queries: 70% get "no close match"; without the floor they would show 1.5
  products on average instead of 12. 5% of real queries are wrongly flagged.

To watch:
- **Vague queries lose recall** (0.53 → 0.29): many partly relevant products fall below 0.6.
  They are one click away under "Show more"; a per-bucket threshold is a possible next step.
- Labels come from the LLM judge (human agreement not yet measured). The no-answer set was
  written by hand and some of it is arguably answerable ("used toyota corolla" → Toyota
  wheels).
- Fit on `hybrid_rerank`; the app serves `full`, whose rewritten query text is what gets
  reranked. Re-run `vio eval gate` whenever the reranker, `rerank_top_n` or the judged set
  changes; a stale gate is refused at load time.
- Photo-only search is not gated yet: CLIP image-to-image similarity separates relevant
  products poorly (AUC 0.72), so it needs its own gate.
