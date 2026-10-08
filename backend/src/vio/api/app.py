"""FastAPI application factory."""

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

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
from vio.search.pipeline import SearchInputError, SearchService

log = logging.getLogger(__name__)

# base64 inflates by 4/3; leave headroom for the rest of the JSON body.
_BODY_OVERHEAD = 64 * 1024


def build_service(settings: Settings) -> SearchService:
    from vio.embeddings.fastembed_impl import build_encoders
    from vio.search.rerank import FastEmbedReranker
    from vio.store.qdrant import ProductStore, create_client

    return SearchService(
        ProductStore(create_client(settings), settings.qdrant_collection),
        build_encoders(settings),
        FastEmbedReranker(settings.rerank_model, settings.model_cache_dir, settings.onnx_threads),
        settings,
    )


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message, "request_id": request_id_var.get()}, status_code=status)


def create_app(
    service: SearchService | None = None, settings: Settings | None = None, *, warmup: bool = True
) -> FastAPI:
    settings = settings or get_settings()

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
        try:
            length = request.headers.get("content-length")
            if length is not None and length.isdigit() and int(length) > max_body:
                response: Response = _error(413, "request body too large")
            else:
                response = await call_next(request)
            response.headers["X-Request-ID"] = rid
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
