# Query understanding evaluation, 2026-10-10 (16aa3ba)

- **Model:** `openai/gpt-oss-20b`, prompt `query_understanding.v1`,
  reasoning effort `low`
- **Queries:** 275 text queries from `data/eval/queries_v1.jsonl`
  (image queries excluded)


| Metric | Value |
|---|---|
| parsed successfully | 275/275 = 100.0% |
| budget extracted exactly (constrained) | 50/50 = 100.0% |
| invented price filter (no budget stated) | 0/225 = 0.0% |
| invented price intent (no budget stated) | 4/225 = 1.8% |
| category committed (seeded queries) | 207/250 = 82.8% |
| category correct when committed | 165/207 = 79.7% |
| category abstained on vague goals | 6/25 = 24.0% |
| typo queries: similarity to clean query (before -> after) | 0.971 -> 0.991 (n=50) |
| latency p50 / p95 (uncached) | 2435 / 5414 ms (n=275) |

Ground truth is built into the query set: constrained queries carry their generated budget,
other text queries state none, seeded queries belong to their seed product's categories,
and each noisy query was derived from a clean descriptive query of the same seed.


