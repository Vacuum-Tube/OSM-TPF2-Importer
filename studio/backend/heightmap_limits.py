"""Shared heightmap resolution limits without importing the raster pipeline."""
from __future__ import annotations

import math

MIN_HEIGHTMAP_PIXELS = 257
MAX_HEIGHTMAP_PIXELS = 6145


def validate_heightmap_pixels(pixels: int) -> int:
    try:
        numeric_pixels = float(pixels)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Enter a whole-number heightmap pixel size.") from exc
    if (
        isinstance(pixels, bool)
        or not math.isfinite(numeric_pixels)
        or not numeric_pixels.is_integer()
    ):
        raise ValueError("Enter a whole-number heightmap pixel size.")
    if not MIN_HEIGHTMAP_PIXELS <= numeric_pixels <= MAX_HEIGHTMAP_PIXELS:
        raise ValueError(
            f"Heightmap pixels must be between {MIN_HEIGHTMAP_PIXELS} and "
            f"{MAX_HEIGHTMAP_PIXELS}. Larger grids scale quadratically and can exceed "
            "8 GiB of peak temporary memory; this cap includes the largest current TPF2 preset."
        )
    return int(numeric_pixels)
