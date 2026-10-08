"""Thread-safe lazy initialization, used to defer loading ML models until first use."""

import threading
from collections.abc import Callable


class Lazy[T]:
    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._value: T | None = None
        self._lock = threading.Lock()

    def get(self) -> T:
        if self._value is None:
            with self._lock:
                if self._value is None:
                    self._value = self._factory()
        return self._value
