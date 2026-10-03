"""Conservative request pacing for public OpenStreetMap services."""
from __future__ import annotations

import email.utils
import math
import threading
import time
from datetime import timezone
from urllib.parse import urlparse

from .jobs import JobCancelled

_MIN_INTERVAL_SECONDS = 1.1
_LOCK = threading.Lock()
_LAST_REQUEST: dict[str, float] = {}
_COOLDOWN_UNTIL: dict[str, float] = {}


def note_host_cooldown(url: str, retry_after: str | None) -> None:
    host = (urlparse(url).hostname or "").lower()
    if (
        (not host.endswith("openstreetmap.org") and not host.endswith("overpass-api.de"))
        or not retry_after
    ):
        return

    try:
        delay = float(retry_after)
    except ValueError:
        try:
            retry_at = email.utils.parsedate_to_datetime(retry_after)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            delay = retry_at.timestamp() - time.time()
        except (TypeError, ValueError, OverflowError, OSError):
            return
    if not math.isfinite(delay):
        return
    deadline = time.monotonic() + max(0.0, delay)
    with _LOCK:
        _COOLDOWN_UNTIL[host] = max(_COOLDOWN_UNTIL.get(host, 0.0), deadline)


def wait_for_request_slot(url: str, cancel=None) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host.endswith("openstreetmap.org") and not host.endswith("overpass-api.de"):
        return

    while True:
        with _LOCK:
            now = time.monotonic()
            cooldown = _COOLDOWN_UNTIL.get(host, 0.0)
            if cooldown <= now:
                _COOLDOWN_UNTIL.pop(host, None)
                cooldown = now
            delay = max(
                _MIN_INTERVAL_SECONDS - (now - _LAST_REQUEST.get(host, 0.0)),
                cooldown - now,
            )
            if delay <= 0:
                _LAST_REQUEST[host] = now
                return
        if cancel is not None:
            if cancel.wait(min(delay, 0.2)):
                raise JobCancelled()
        else:
            time.sleep(min(delay, 0.2))
