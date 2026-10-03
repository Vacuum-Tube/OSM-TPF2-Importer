"""Inspect local OSM extracts without parsing the whole file."""
from __future__ import annotations

import bz2
import gzip
import re
from datetime import datetime
from pathlib import Path

from . import bounds as B

_BOUNDS_TAG = re.compile(br"<bounds\b([^>]*)/?>")
_ATTR = re.compile(r"""(\w+)\s*=\s*["']([^"']*)["']""")


def file_meta(path: Path | str | None) -> dict | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    st = p.stat()
    return {
        "path": str(p),
        "bytes": st.st_size,
        "mtime": st.st_mtime,
        "mtime_label": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "mb": round(st.st_size / 1e6, 1),
        "kind": classify(p),
    }


def classify(path: Path | str) -> str:
    name = Path(path).name.lower()
    if name.endswith(".pbf") or name.endswith(".osm.pbf"):
        return "pbf"
    if name.endswith(".bz2"):
        return "bz2"
    if name.endswith(".gz"):
        return "gz"
    if name.endswith(".osm") or name.endswith(".xml"):
        return "osm"
    return "other"


def open_osm_bytes(path: Path, mode: str = "rb"):
    kind = classify(path)
    if kind == "bz2":
        return bz2.open(path, mode)
    if kind == "gz":
        return gzip.open(path, mode)
    return Path(path).open(mode)


def peek_bounds(path: Path | str) -> dict | None:
    p = Path(path)
    if not p.is_file():
        return None
    kind = classify(p)
    if kind == "pbf":
        return None
    try:
        with open_osm_bytes(p) as fh:
            head = fh.read(262144)
            match = _BOUNDS_TAG.search(head)
            if match is None:
                match = _BOUNDS_TAG.search(head + fh.read(1024 * 1024 - 262144))
    except OSError:
        return None
    if match is None:
        return None
    attr = match.group(1).decode("utf-8", "replace")
    parsed = dict(_ATTR.findall(attr))
    try:
        box = B.box_from_corners(
            float(parsed["minlat"]),
            float(parsed["minlon"]),
            float(parsed["maxlat"]),
            float(parsed["maxlon"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    span = max(box["real_m"]["lat_m"], box["real_m"]["lon_south_m"], box["real_m"]["lon_north_m"])
    box["suggested_size"] = B.nearest_size_key(span)
    box["span_m"] = round(span)
    return box


def overlap_ratio(a: dict | None, b: dict | None) -> float:
    if not a or not b:
        return 0.0
    minlat = max(a["minlat"], b["minlat"])
    minlon = max(a["minlon"], b["minlon"])
    maxlat = min(a["maxlat"], b["maxlat"])
    maxlon = min(a["maxlon"], b["maxlon"])
    if minlat >= maxlat or minlon >= maxlon:
        return 0.0
    inter = (maxlat - minlat) * (maxlon - minlon)
    area_a = abs(a["maxlat"] - a["minlat"]) * abs(a["maxlon"] - a["minlon"])
    if area_a <= 0:
        return 0.0
    return inter / area_a


def should_adopt(box: dict | None) -> bool:
    """True when the extract is about the size of a TPF2 map, not a country dump."""
    if not box:
        return False
    span = box.get("span_m")
    if not span:
        real = box.get("real_m") or {}
        span = max(real.get("lat_m") or 0, real.get("lon_south_m") or 0, real.get("lon_north_m") or 0)
    max_m = max(info["meters"] for info in B.MAP_SIZES.values())
    return 500 < float(span) <= max_m * 1.2


def needs_crop(path: Path | str | None, box: dict | None, map_meters: int | None = None) -> bool:
    """Country-sized or compressed extracts should be cropped to the yellow box first."""
    p = Path(path) if path else None
    if not p or not p.is_file() or not box:
        return False
    kind = classify(p)
    if kind == "pbf":
        return True
    if kind in {"bz2", "gz"}:
        return True
    file_box = peek_bounds(p)
    if file_box and should_adopt(file_box):
        return False
    if file_box and map_meters:
        span = file_box.get("span_m") or 0
        if span > float(map_meters) * 1.15:
            return True
    return p.stat().st_size > 80_000_000


def looks_like_loader(path: Path | str | None) -> bool:
    if not path:
        return False
    p = Path(path)
    if not p.is_file():
        return False
    try:
        head = p.read_bytes()[:1600]
    except OSError:
        return False
    return b"osmdata_" in head and b"require" in head
