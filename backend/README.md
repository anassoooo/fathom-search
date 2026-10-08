# vio (backend)

Python service that owns all AI logic for VIO: ingestion, embeddings, retrieval,
reranking, LLM query understanding, the assistant agent, and evaluation.
See [../PLAN.md](../PLAN.md) and [../CONSTITUTION.md](../CONSTITUTION.md).

## Dev setup

```bash
cd backend
uv sync                      # creates .venv with Python 3.12
cp .env.example .env         # then fill in values
uv run vio --help
```

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # unit tests
uv run pytest -m integration     # needs `docker compose up qdrant` from the repo root
```
