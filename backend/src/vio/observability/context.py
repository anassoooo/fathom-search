"""Per-request context (request ID) available to logging anywhere in the call stack."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
