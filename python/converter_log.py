"""Quiet per-edge converter prints unless OSM_TPF2_VERBOSE=1."""
from __future__ import annotations

import builtins
import os

verbose = os.environ.get("OSM_TPF2_VERBOSE", "").strip().lower() in ("1", "true", "yes")


def bind_print(*keep_prefixes: str):
    real = builtins.print
    prefixes = tuple(keep_prefixes)

    def p(*args, **kwargs):
        if verbose:
            return real(*args, **kwargs)
        if not args:
            return None
        text = str(args[0])
        for pref in prefixes:
            if text.startswith(pref):
                return real(*args, **kwargs)
        return None

    return p


def vprint(*args, **kwargs):
    if verbose:
        builtins.print(*args, **kwargs)
