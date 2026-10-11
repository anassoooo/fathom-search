# Fathom backend (package `vio`)

Python service that owns all AI logic for Fathom: ingestion, embeddings, retrieval,
reranking, LLM query understanding, the assistant agent, and evaluation.
See [../PLAN.md](../PLAN.md) and [../CONSTITUTION.md](../CONSTITUTION.md).

## Dev setup

```bash
cd backend
uv sync --extra cpu          # creates .venv with Python 3.12 (CPU inference)
# or, with an NVIDIA GPU + recent driver:
uv sync --extra gpu          # CUDA 12 / cuDNN 9 from pip; then set ONNX_DEVICE=cuda in .env
cp .env.example .env         # then paste your Groq key into LLM_API_KEY
uv run vio --help
```

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # unit tests
uv run pytest -m integration     # needs `docker compose up qdrant` from the repo root
```
