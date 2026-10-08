import urllib.request

import pytest

from vio.config import Settings


@pytest.mark.integration
def test_qdrant_is_ready() -> None:
    url = Settings().qdrant_url.rstrip("/") + "/readyz"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
