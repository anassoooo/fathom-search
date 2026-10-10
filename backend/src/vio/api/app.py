"""FastAPI application factory."""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from vio import __version__
from vio.api.routes import router
from vio.config import Settings, get_settings
from vio.observability.context import request_id_var
from vio.observability.logging import configure_logging
from vio.search.pipeline import SearchInputError, SearchService

log = logging.getLogger(__name__)

# base64 inflates by 4/3; leave headroom for the rest of the JSON body.
_BODY_OVERHEAD = 64 * 1024


def build_service(settings: Settings, llm_cache: Path | None = None) -> SearchService:
    """`llm_cache` (eval runs) persists LLM answers on disk; serving keeps them in memory."""
    from vio.embeddings.fastembed_impl import Runtime, build_encoders
    from vio.llm.client import LLMClient, openai_chat_fn
    from vio.llm.query_understanding import QueryUnderstanding
    from vio.search.rerank import FastEmbedReranker
    from vio.store.qdrant import ProductStore, create_client

    store = ProductStore(create_client(settings), settings.qdrant_collection)
    # Serving must not hang on the LLM: short timeout, one attempt, then degrade.
    fast = settings.model_copy(update={"llm_timeout_s": min(settings.llm_timeout_s, 8.0)})
    llm = LLMClient(
        openai_chat_fn(fast), cache_path=llm_cache, max_attempts=1 if llm_cache is None else 6
    )
    service = SearchService(
        store,
        build_encoders(settings),
        FastEmbedReranker(settings.rerank_model, Runtime.from_settings(settings)),
        settings,
    )
    service.understander = QueryUnderstanding(
        llm, settings.llm_model_query, lambda: service.taxonomy().categories
    )
    return service


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "request_id": request_id_var.get()}, status_code=status)


def create_app(
    service: SearchService | None = None,
    settings: Settings | None = None,
    *,
    warmup: bool = True,
    configure_logs: bool = False,
) -> FastAPI:
    settings = settings or get_settings()
    if configure_logs:
        configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        svc = service or build_service(settings)
        if warmup:
            log.info("warming up models")
            svc.warmup()
        app.state.service = svc
        yield

    app = FastAPI(
        title="VIO search API",
        version=__version__,
        description="Hybrid multimodal product search. See PLAN.md section 7.7.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    max_body = settings.max_image_bytes * 4 // 3 + _BODY_OVERHEAD

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        start = time.perf_counter()
        try:
            length = request.headers.get("content-length")
            if length is not None and length.isdigit() and int(length) > max_body:
                response: Response = _error(413, "request body too large")
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            log.info(
                "request",
                extra={
                    "fields": {
                        "event": "request",
                        "method": request.method,
                        "path": request.url.path,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                    }
                },
            )
            return response
        finally:
            request_id_var.reset(token)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(SearchInputError)
    async def _bad_input(request: Request, exc: SearchInputError) -> JSONResponse:
        return _error(400, str(exc))

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        msg = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in errors
        )
        return _error(422, msg or "invalid request")

    @app.exception_handler(ResponseHandlingException)
    @app.exception_handler(UnexpectedResponse)
    async def _store_down(request: Request, exc: Exception) -> JSONResponse:
        log.error("vector store unavailable: %s", exc)
        return _error(503, "search backend unavailable, please retry")

    app.include_router(router)
    return app
