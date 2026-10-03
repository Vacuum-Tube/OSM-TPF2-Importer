"""Shared job control for Studio background work."""
from __future__ import annotations

from threading import Event


class JobCancelled(Exception):
    def __init__(self, message: str = "Cancelled"):
        super().__init__(message)


def scale_progress(progress, lo: float, hi: float):
    """Remap 0–100 progress into [lo, hi] so nested jobs do not reset the bar."""
    if progress is None:
        return None

    def wrap(msg: str, pct=None) -> None:
        if pct is None:
            progress(msg, None)
            return
        try:
            p = float(pct)
        except (TypeError, ValueError):
            progress(msg, None)
            return
        progress(msg, lo + (max(0.0, min(100.0, p)) / 100.0) * (hi - lo))

    return wrap


def raise_if_cancelled(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise JobCancelled()
