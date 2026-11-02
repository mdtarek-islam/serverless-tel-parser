"""Record the container init duration once and flag the first invoke.

Import this module before any heavy dependency so that its clock starts
as early as possible in the container lifecycle. The measured value is a
log field. The under 200 ms cold start figure is a design target only.
"""

from __future__ import annotations

import time

_MODULE_IMPORTED_AT = time.perf_counter()


class ColdStartRecorder:
    """Hold init timing state for one execution environment."""

    def __init__(self, started_at: float | None = None) -> None:
        self._started_at = time.perf_counter() if started_at is None else started_at
        self._init_ms: float | None = None
        self._cold = True

    def mark_init_complete(self) -> float:
        """Store the init duration on the first call. Return the stored value."""
        if self._init_ms is None:
            self._init_ms = (time.perf_counter() - self._started_at) * 1000.0
        return self._init_ms

    @property
    def init_ms(self) -> float | None:
        return self._init_ms

    def take_cold_flag(self) -> bool:
        """Return True for the first invoke in this container, then False."""
        cold, self._cold = self._cold, False
        return cold


RECORDER = ColdStartRecorder(started_at=_MODULE_IMPORTED_AT)
