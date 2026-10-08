import time
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def timed(timings: dict[str, float], stage: str) -> Iterator[None]:
    """Record the wall-clock duration of a block in milliseconds under `stage`."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] = round((time.perf_counter() - start) * 1000, 2)
