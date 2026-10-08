import io
from collections.abc import Sequence
from pathlib import Path

import pytest
from PIL import Image
from qdrant_client import QdrantClient
from typer.testing import CliRunner

from vio.cli import app
from vio.embeddings import Encoders
from vio.embeddings.fake import fake_encoders
from vio.ingest.images import ImageSource
from vio.ingest.loader import load_products
from vio.ingest.pipeline import ingest
from vio.store.qdrant import ProductStore


def _store() -> ProductStore:
    return ProductStore(QdrantClient(location=":memory:"), "ingest_test")


def test_loader_reports_invalid_and_duplicate_rows(tmp_path: Path, fixture_csv: Path) -> None:
    lines = fixture_csv.read_text(encoding="utf-8").splitlines()
    bad = tmp_path / "bad.csv"
    # duplicate of row 0, plus a row with a rating of 9
    bad.write_text(
        "\n".join([*lines[:3], lines[1], lines[2].replace(",4.3,", ",9,")]) + "\n",
        encoding="utf-8",
    )
    report = load_products(bad)
    assert report.rows_read == 4
    assert len(report.products) == 2
    assert report.duplicates == 1
    assert len(report.invalid) == 1 and "rating" in report.invalid[0][1]


def test_loader_limit(fixture_csv: Path) -> None:
    assert len(load_products(fixture_csv, limit=5).products) == 5


def test_ingest_then_rerun_skips_existing(fixture_csv: Path) -> None:
    store, enc = _store(), fake_encoders()
    products = load_products(fixture_csv).products
    first = ingest(products, store, enc, ImageSource(None), batch_size=10)
    assert (first.upserted, first.skipped_existing) == (24, 0)
    second = ingest(products, store, enc, ImageSource(None), batch_size=10)
    assert (second.upserted, second.skipped_existing) == (0, 24)
    assert store.count() == 24


def test_ingest_uses_local_images_and_survives_corrupt_ones(
    tmp_path: Path, fixture_csv: Path
) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(buf, format="JPEG")
    (tmp_path / "0.jpg").write_bytes(buf.getvalue())
    (tmp_path / "1.png").write_bytes(b"not an image")

    class StrictImageEncoder:
        """Like CLIP: fails on bytes that aren't a decodable image."""

        dim = 32

        def embed_images(self, images: Sequence[bytes]) -> list[list[float]]:
            for b in images:
                Image.open(io.BytesIO(b)).verify()
            return [[1.0] + [0.0] * 31 for _ in images]

        def embed_text(self, text: str) -> list[float]:
            return [1.0] + [0.0] * 31

    enc = fake_encoders()
    enc = Encoders(dense=enc.dense, sparse=enc.sparse, image=StrictImageEncoder())
    store = _store()
    report = ingest(load_products(fixture_csv, limit=3).products, store, enc, ImageSource(tmp_path))
    assert report.with_image == 1
    assert report.image_errors == 1
    assert report.upserted == 3


def test_cli_ingest_with_fake_encoders(fixture_csv: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from vio.config import get_settings

    monkeypatch.setenv("QDRANT_URL", ":memory:")
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(app, ["ingest", "--csv", str(fixture_csv), "--fake-encoders"])
    finally:
        get_settings.cache_clear()
    assert result.exit_code == 0, result.output
    assert "Upserted 24" in result.output
    assert "Collection now holds 24 points" in result.output


def test_cli_requires_exactly_one_source() -> None:
    result = CliRunner().invoke(app, ["ingest"])
    assert result.exit_code != 0
