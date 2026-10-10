# syntax=docker/dockerfile:1

# ---- build: resolve and install locked deps into a venv --------------------
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-default-groups --no-editable

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 vio
COPY --from=builder /app/.venv /app/.venv
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    MODEL_CACHE_DIR=/models

# Bake the ONNX models into the image so cold starts never hit the network.
RUN mkdir /models && python -c "\
from vio.config import Settings; \
from vio.embeddings.fastembed_impl import build_encoders; \
from vio.search.rerank import FastEmbedReranker; \
s = Settings(); e = build_encoders(s); \
e.dense.embed_query('x'); e.sparse.embed_query('x'); e.image.embed_text('x'); \
e.image.embed_images([__import__('base64').b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')]); \
FastEmbedReranker(s.rerank_model, s.model_cache_dir).score('x', ['a', 'b'])" \
    && chown -R vio /models

USER vio
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"
CMD ["vio", "serve", "--host", "0.0.0.0", "--port", "8000"]
