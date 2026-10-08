import json
import logging

import pytest

from vio.models import SearchRequest
from vio.observability.context import request_id_var
from vio.observability.logging import JsonFormatter
from vio.search.pipeline import SearchService
from vio.store.qdrant import ProductStore


def _format(record: logging.LogRecord) -> dict[str, object]:
    out: dict[str, object] = json.loads(JsonFormatter().format(record))
    return out


def test_json_formatter_includes_request_id_and_fields() -> None:
    record = logging.LogRecord("vio.test", logging.INFO, __file__, 1, "hello %s", ("x",), None)
    record.fields = {"event": "search", "variant": "bm25"}
    token = request_id_var.set("rid-7")
    try:
        entry = _format(record)
    finally:
        request_id_var.reset(token)
    assert entry["msg"] == "hello x"
    assert entry["request_id"] == "rid-7"
    assert entry["event"] == "search" and entry["variant"] == "bm25"


def test_search_emits_structured_event(
    memory_store: ProductStore, caplog: pytest.LogCaptureFixture
) -> None:
    from vio.config import Settings
    from vio.embeddings.fake import fake_encoders
    from vio.search.rerank import FakeReranker

    svc = SearchService(memory_store, fake_encoders(), FakeReranker(), Settings(_env_file=None))
    with caplog.at_level(logging.INFO, logger="vio.search.pipeline"):
        svc.search(SearchRequest(query="laptop", variant="hybrid"))
    [rec] = [r for r in caplog.records if r.getMessage() == "search"]
    fields = rec.fields  # type: ignore[attr-defined]
    assert fields["variant"] == "hybrid" and fields["query"] == "laptop"
    assert {"total_ms", "retrieve_ms"} <= set(fields["timings_ms"])
