"""TPF2 map sizes and geographic rectangles (1:1 scale)."""
from __future__ import annotations

import math

from geopy.distance import geodesic

# Exact 1:1 edge lengths in meters (wiki: meters = (px-1)*4)
MAP_SIZES = {
    "tiny": {"label": "Tiny", "meters": 4096, "heightmap": 1025, "experimental": True},
    "small": {"label": "Small", "meters": 8192, "heightmap": 2049, "experimental": False},
    "medium": {"label": "Medium", "meters": 11264, "heightmap": 2817, "experimental": False},
    "large": {"label": "Large", "meters": 14336, "heightmap": 3585, "experimental": False},
    "very_large": {"label": "Very Large", "meters": 16384, "heightmap": 4097, "experimental": False},
    "huge": {"label": "Huge", "meters": 20480, "heightmap": 5121, "experimental": True},
    "megalomaniac": {"label": "Megalomaniac", "meters": 24576, "heightmap": 6145, "experimental": True},
}

# No city default. Studio starts on a world view until the user searches or clicks.
DEFAULT_VIEW = {"lat": 20.0, "lon": 0.0, "zoom": 2}

# Old factory centers (Partille / Greater Gothenburg). Ignore if still in settings.json.
_LEGACY_CENTERS = (
    (57.700713, 12.17156),
)

# Workshop pack matching only — not political borders.
# Simple rectangles overlap (Øresund, etc.); keep Sweden only and reverse-geocode elsewhere.
REGION_BOXES = {
    "SE": {"minlat": 55.0, "maxlat": 69.4, "minlon": 10.5, "maxlon": 24.2},
}


def is_legacy_center(lat, lon) -> bool:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    for a, b in _LEGACY_CENTERS:
        if abs(lat_f - a) < 1e-5 and abs(lon_f - b) < 1e-5:
            return True
    return False


def region_for(lat, lon) -> str | None:
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    for code, box in REGION_BOXES.items():
        if box["minlat"] <= lat_f <= box["maxlat"] and box["minlon"] <= lon_f <= box["maxlon"]:
            return code
    return None


def box_from_center(lat: float, lon: float, meters: int) -> dict:
    """Square box in meters around a WGS84 center, geodesic on each axis."""
    half = meters / 2.0
    dlat = half / 111320.0
    minlat, maxlat = lat - dlat, lat + dlat
    dlon = half / (111320.0 * max(0.2, abs(math.cos(math.radians(lat)))))
    minlon, maxlon = lon - dlon, lon + dlon
    return {
        "minlat": minlat,
        "minlon": minlon,
        "maxlat": maxlat,
        "maxlon": maxlon,
        "center_lat": lat,
        "center_lon": lon,
        "meters": meters,
        "real_m": real_span(minlat, minlon, maxlat, maxlon),
    }


def box_from_corners(minlat: float, minlon: float, maxlat: float, maxlon: float) -> dict:
    return {
        "minlat": minlat,
        "minlon": minlon,
        "maxlat": maxlat,
        "maxlon": maxlon,
        "center_lat": (minlat + maxlat) / 2,
        "center_lon": (minlon + maxlon) / 2,
        "real_m": real_span(minlat, minlon, maxlat, maxlon),
    }


def real_span(minlat, minlon, maxlat, maxlon) -> dict:
    lat_m = geodesic((minlat, minlon), (maxlat, minlon)).m
    lon_s = geodesic((minlat, minlon), (minlat, maxlon)).m
    lon_n = geodesic((maxlat, minlon), (maxlat, maxlon)).m
    return {
        "lat_m": round(lat_m),
        "lon_south_m": round(lon_s),
        "lon_north_m": round(lon_n),
    }


def scale_factors(box: dict, map_meters: int) -> dict:
    real = box.get("real_m") or real_span(box["minlat"], box["minlon"], box["maxlat"], box["maxlon"])
    lon_avg = (real["lon_south_m"] + real["lon_north_m"]) / 2
    return {
        "x": round(map_meters / max(1, lon_avg), 3),
        "y": round(map_meters / max(1, real["lat_m"]), 3),
        "real": real,
    }


def osm_export_url(box: dict, zoom: int = 14) -> str:
    c_lat = (box["minlat"] + box["maxlat"]) / 2
    c_lon = (box["minlon"] + box["maxlon"]) / 2
    return (
        f"https://www.openstreetmap.org/#map={zoom}/{c_lat:.6f}/{c_lon:.6f}"
        f"&layers=D"
    )


def bbox_area_deg2(box: dict) -> float:
    return abs(box["maxlat"] - box["minlat"]) * abs(box["maxlon"] - box["minlon"])


def nearest_size_key(meters: float) -> str:
    """Closest official TPF2 map edge length to a measured ground span."""
    return min(MAP_SIZES.items(), key=lambda kv: abs(kv[1]["meters"] - float(meters)))[0]
