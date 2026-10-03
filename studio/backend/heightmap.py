"""Build a TPF2 16-bit heightmap for the yellow map square.

Sources (all public, no API key):
  1. Mapzen/Nextzen Terrarium tiles — blended SRTM/NED/EU-DEM/bathymetry
  2. FABDEM v1.2 — Copernicus GLO-30 with forest/buildings removed (30 m DTM)
  3. Copernicus GLO-30 — 30 m DSM if FABDEM is unavailable
  4. AWS Skadi SRTMGL1 (.hgt.gz) — 30 m fallback

Sampling uses the same Web Mercator stretch as python/coord2metric.py so
OSM edges, overlay, and terrain share one lat/lon box.
"""
from __future__ import annotations

import gzip
import io
import math
import re
import shutil
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .jobs import JobCancelled, raise_if_cancelled
from .heightmap_limits import validate_heightmap_pixels

import numpy as np
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

UA = "OSM-TPF2-Studio/1.0 (heightmap, personal TPF2 rebuild)"
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SKADI = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{folder}/{name}.hgt.gz"
COP30 = (
    "https://copernicus-dem-30m.s3.amazonaws.com/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM/"
    "Copernicus_DSM_COG_10_{ns}{lat:02d}_00_{ew}{lon:03d}_00_DEM.tif"
)
FABDEM = (
    "https://huggingface.co/buckets/links-ads/fabdem/resolve/tiles/"
    "{block}/{name}_FABDEM_V1-2.tif"
)
MERC_EXTENT = 20037508.342789244
_PROGRESS_LOCK = threading.Lock()
_PROGRESS_LOCAL = threading.local()
_TILE_RE = re.compile(r"Terrarium tiles (\d+)/(\d+)")


def _heightmap_percent(msg: str) -> float | None:
    m = _TILE_RE.search(msg or "")
    if m:
        a, b = int(m.group(1)), max(1, int(m.group(2)))
        return 8 + 42 * a / b
    text = msg or ""
    if text.startswith("Computing Web Mercator"):
        return 3
    if text.startswith("Terrarium zoom"):
        return 6
    if "Resampling Terrarium" in text:
        return 52
    if "Trying FABDEM" in text or text.startswith("FABDEM "):
        return 58
    if "Copernicus" in text:
        return 64
    if "SRTM" in text:
        return 70
    if "Mixing DTM" in text:
        return 82
    if text.startswith("Done."):
        return 100
    return None


def _progress(dest: Path, msg: str) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    fn = None
    with _PROGRESS_LOCK:
        (dest / "progress.txt").write_text(msg, encoding="utf-8")
        fn = getattr(_PROGRESS_LOCAL, "fn", None)
    if fn:
        fn(msg, _heightmap_percent(msg))


def _get(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last: Exception | None = None
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as exc:
            last = exc
            time.sleep(0.45 * (attempt + 1))
    raise last or RuntimeError(url)


def _cached_get(url: str, path: Path, timeout: int = 60) -> bytes:
    if path.is_file() and path.stat().st_size > 256:
        return path.read_bytes()
    raw = _get(url, timeout=timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(raw)
    tmp.replace(path)
    return raw


def _deg2num(lat: float, lon: float, z: int) -> tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2.0 ** z
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def _tile_range(box: dict, z: int) -> tuple[int, int, int, int]:
    x0, y1 = _deg2num(box["minlat"], box["minlon"], z)
    x1, y0 = _deg2num(box["maxlat"], box["maxlon"], z)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    n = 2 ** z
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(n - 1, x1)
    y1 = min(n - 1, y1)
    return x0, x1, y0, y1


def choose_zoom(box: dict, max_tiles: int = 1600) -> int:
    for z in range(15, 10, -1):
        x0, x1, y0, y1 = _tile_range(box, z)
        if (x1 - x0 + 1) * (y1 - y0 + 1) <= max_tiles:
            return z
    return 11


def _decode_terrarium(png: bytes) -> np.ndarray:
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"), dtype=np.float32)
    h = rgb[:, :, 0] * 256.0 + rgb[:, :, 1] + rgb[:, :, 2] / 256.0 - 32768.0
    h[h < -11000] = np.nan
    return h


def _download_terrarium(box: dict, zoom: int, dest: Path) -> tuple[np.ndarray, dict]:
    x0, x1, y0, y1 = _tile_range(box, zoom)
    nx, ny = x1 - x0 + 1, y1 - y0 + 1
    mosaic = np.full((ny * 256, nx * 256), np.nan, dtype=np.float32)
    jobs = [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    cache = dest / "cache" / "terrarium" / str(zoom)
    done = 0

    def one(xy):
        x, y = xy
        url = TERRARIUM.format(z=zoom, x=x, y=y)
        path = cache / f"{x}_{y}.png"
        try:
            return x, y, _decode_terrarium(_cached_get(url, path, timeout=40))
        except Exception:
            return x, y, None

    done = 0
    pool = ThreadPoolExecutor(max_workers=8)
    try:
        futs = [pool.submit(one, j) for j in jobs]
        for fut in as_completed(futs):
            raise_if_cancelled(getattr(_PROGRESS_LOCAL, "cancel", None))
            x, y, tile = fut.result()
            done += 1
            if done % 8 == 0 or done == len(jobs):
                _progress(dest, f"Terrarium tiles {done}/{len(jobs)} (z{zoom})")
            if tile is None:
                continue
            mosaic[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = tile
    except JobCancelled:
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)

    n = 2 ** zoom
    res = (2 * MERC_EXTENT) / n / 256.0
    meta = {
        "west": -MERC_EXTENT + x0 * 256 * res,
        "north": MERC_EXTENT - y0 * 256 * res,
        "res": res,
        "zoom": zoom,
        "tiles": len(jobs),
    }
    return mosaic, meta


def _resample_mercator(src: np.ndarray, src_meta: dict, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Sample src (north-up, Web Mercator) onto mercator coordinate axes xs, ys."""
    res = src_meta["res"]
    col = (xs - src_meta["west"]) / res
    row = (src_meta["north"] - ys) / res
    cc, rr = np.meshgrid(col, row)
    sampled = ndimage.map_coordinates(
        np.nan_to_num(src, nan=0.0),
        np.array([rr, cc]),
        order=1,
        mode="nearest",
    )
    valid = (
        (rr >= 0) & (rr <= src.shape[0] - 1) &
        (cc >= 0) & (cc <= src.shape[1] - 1) &
        np.isfinite(src[
            np.clip(np.round(rr).astype(int), 0, src.shape[0] - 1),
            np.clip(np.round(cc).astype(int), 0, src.shape[1] - 1),
        ])
    )
    sampled = sampled.astype(np.float32)
    sampled[~valid] = np.nan
    return sampled


def _cop30_specs(box: dict) -> list[tuple[int, str, int, str, int, int]]:
    """lat_abs, ns, lon_abs, ew, south, west as signed degrees of SW corner."""
    out = []
    for lat in range(math.floor(box["minlat"]), math.floor(box["maxlat"]) + 1):
        for lon in range(math.floor(box["minlon"]), math.floor(box["maxlon"]) + 1):
            out.append((
                abs(lat), "N" if lat >= 0 else "S",
                abs(lon), "E" if lon >= 0 else "W",
                lat, lon,
            ))
    return out


def _hem_lat(v: int) -> str:
    return f"{'N' if v >= 0 else 'S'}{abs(v):02d}"


def _hem_lon(v: int) -> str:
    return f"{'E' if v >= 0 else 'W'}{abs(v):03d}"


def _fabdem_block(south: int, west: int) -> str:
    lat0 = int(math.floor(south / 10.0) * 10)
    lon0 = int(math.floor(west / 10.0) * 10)
    return (
        f"{_hem_lat(lat0)}{_hem_lon(lon0)}-{_hem_lat(lat0 + 10)}{_hem_lon(lon0 + 10)}"
        "_FABDEM_V1-2"
    )


def _geo_meta(arr: np.ndarray, south: int, west: int) -> dict:
    h, w = arr.shape
    return {
        "kind": "geo",
        "south": float(south),
        "north": float(south + 1),
        "west": float(west),
        "east": float(west + 1),
        "edge_share": h in {1201, 3601} or w in {1201, 3601},
    }


def _tiff_geo_meta(raw: bytes, arr: np.ndarray, south: int, west: int) -> dict:
    meta = _geo_meta(arr, south, west)
    try:
        import tifffile
        with tifffile.TiffFile(io.BytesIO(raw)) as tif:
            tags = tif.pages[0].tags
            scale = tags.get("ModelPixelScaleTag")
            tie = tags.get("ModelTiepointTag")
            keys = tags.get("GeoKeyDirectoryTag")
            scale_v = scale.value if scale is not None else None
            tie_v = tie.value if tie is not None else None
            keys_v = list(keys.value) if keys is not None else None
        if scale_v is None or tie_v is None:
            return meta
        raster_type = 1
        if keys_v and len(keys_v) > 3:
            n = int(keys_v[3])
            for i in range(4, min(len(keys_v), 4 + n * 4), 4):
                if int(keys_v[i]) == 1025:
                    raster_type = int(keys_v[i + 3])
        meta["origin_x"] = float(tie_v[3])
        meta["origin_y"] = float(tie_v[4])
        meta["sx"] = float(scale_v[0])
        meta["sy"] = abs(float(scale_v[1]))
        meta["raster_type"] = raster_type
    except Exception:
        pass
    return meta


def _read_geotiff(raw: bytes) -> np.ndarray:
    try:
        import tifffile
        arr = np.asarray(tifffile.imread(io.BytesIO(raw)), dtype=np.float32)
    except Exception:
        arr = np.asarray(Image.open(io.BytesIO(raw)), dtype=np.float32)
    if arr.ndim > 2:
        arr = arr[..., 0]
    arr[arr < -1000] = np.nan
    return arr


def _merge_geo(pieces: list[tuple[np.ndarray, dict]], lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    out = np.full(lats.shape, np.nan, dtype=np.float32)
    for arr, meta in pieces:
        sampled = _sample_geo(arr, meta, lats, lons)
        out = np.where(np.isfinite(sampled), sampled, out)
    return out


def _load_fabdem(box: dict, dest: Path) -> list[tuple[np.ndarray, dict]] | None:
    pieces = []
    cache = dest / "cache" / "fabdem"
    for lat, ns, lon, ew, south, west in _cop30_specs(box):
        name = f"{ns}{lat:02d}{ew}{lon:03d}"
        url = FABDEM.format(block=_fabdem_block(south, west), name=name)
        _progress(dest, f"FABDEM {name}")
        try:
            raw = _cached_get(url, cache / f"{name}.tif", timeout=180)
            arr = _read_geotiff(raw)
        except Exception:
            continue
        pieces.append((arr, _tiff_geo_meta(raw, arr, south, west)))
    return pieces or None


def _load_copernicus(box: dict, dest: Path) -> list[tuple[np.ndarray, dict]] | None:
    try:
        import tifffile  # noqa: F401
    except ImportError:
        return None
    pieces = []
    cache = dest / "cache" / "cop30"
    for lat, ns, lon, ew, south, west in _cop30_specs(box):
        name = f"{ns}{lat:02d}{ew}{lon:03d}"
        url = COP30.format(ns=ns, lat=lat, ew=ew, lon=lon)
        _progress(dest, f"Copernicus GLO-30 {name}")
        try:
            raw = _cached_get(url, cache / f"{name}.tif", timeout=180)
            arr = _read_geotiff(raw)
        except Exception:
            continue
        pieces.append((arr, _tiff_geo_meta(raw, arr, south, west)))
    return pieces or None


def _load_srtm(box: dict, dest: Path) -> list[tuple[np.ndarray, dict]] | None:
    pieces = []
    cache = dest / "cache" / "srtm"
    for lat, ns, lon, ew, south, west in _cop30_specs(box):
        name = f"{ns}{lat:02d}{ew}{lon:03d}"
        folder = f"{ns}{lat:02d}"
        url = SKADI.format(folder=folder, name=name)
        _progress(dest, f"SRTM {name}")
        try:
            raw = gzip.decompress(_cached_get(url, cache / f"{name}.hgt.gz", timeout=90))
        except Exception:
            continue
        n = int(round(math.sqrt(len(raw) / 2)))
        arr = np.frombuffer(raw, dtype=">i2").reshape(n, n).astype(np.float32)
        arr[arr < -32000] = np.nan
        pieces.append((arr, _geo_meta(arr, south, west)))
    return pieces or None


def _sample_geo(src: np.ndarray, meta: dict, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Sample a north-up geographic raster onto 2D lat/lon grids."""
    h, w = src.shape
    if "origin_x" in meta and meta.get("sx"):
        col_g = (lons - meta["origin_x"]) / meta["sx"]
        row_g = (meta["origin_y"] - lats) / meta["sy"]
        if meta.get("raster_type", 1) == 1:
            col_g = col_g - 0.5
            row_g = row_g - 0.5
    else:
        south, north, west, east = meta["south"], meta["north"], meta["west"], meta["east"]
        span_y = max(1e-9, north - south)
        span_x = max(1e-9, east - west)
        if meta.get("edge_share"):
            row_g = (north - lats) / span_y * (h - 1)
            col_g = (lons - west) / span_x * (w - 1)
        else:
            row_g = (north - lats) / span_y * h - 0.5
            col_g = (lons - west) / span_x * w - 0.5
    sampled = ndimage.map_coordinates(
        np.nan_to_num(src, nan=0.0),
        np.array([row_g, col_g]),
        order=1,
        mode="nearest",
    ).astype(np.float32)
    ri = np.clip(np.round(row_g).astype(int), 0, h - 1)
    ci = np.clip(np.round(col_g).astype(int), 0, w - 1)
    sampled[~np.isfinite(src[ri, ci])] = np.nan
    if "origin_x" not in meta:
        sampled[(lats < meta["south"]) | (lats > meta["north"]) | (lons < meta["west"]) | (lons > meta["east"])] = np.nan
    else:
        sampled[(row_g < -0.6) | (row_g > h - 0.4) | (col_g < -0.6) | (col_g > w - 0.4)] = np.nan
    return sampled


def _strip_vegetation(detail: np.ndarray, dtm: np.ndarray | None, cell_m: float) -> np.ndarray:
    if dtm is not None:
        diff = detail - dtm
        fused = np.where(np.isfinite(dtm) & (diff > 8.0), dtm, detail)
        fused = np.where(np.isfinite(fused), fused, np.where(np.isfinite(dtm), dtm, detail))
        return fused
    finite = detail[np.isfinite(detail)]
    fill = float(np.nanmedian(finite)) if finite.size else 0.0
    win = max(3, int(round(90.0 / max(cell_m, 1.0))) | 1)
    est = ndimage.median_filter(np.nan_to_num(detail, nan=fill), size=win)
    diff = detail - est
    return np.where(np.isfinite(detail) & (diff > 8.0), est, detail)


def _hillshade(z: np.ndarray, cell: float = 4.0) -> np.ndarray:
    z0 = np.nan_to_num(z, nan=float(np.nanmedian(z)))
    dy, dx = np.gradient(z0, cell)
    slope = np.pi / 2 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    alt = np.radians(45)
    az = np.radians(315)
    shaded = np.sin(alt) * np.sin(slope) + np.cos(alt) * np.cos(slope) * np.cos(az - aspect)
    shaded = np.clip(shaded, 0, 1)
    return (shaded * 255).astype(np.uint8)


def _to_png16(elev: np.ndarray) -> tuple[Image.Image, float, float]:
    finite = elev[np.isfinite(elev)]
    if finite.size == 0:
        raise RuntimeError("Heightmap is empty — DEM download failed.")
    vmin = float(np.min(finite))
    vmax = float(np.max(finite))
    p1, p99 = np.percentile(finite, [0.15, 99.85])
    if vmax - p99 > 80 or p1 - vmin > 80:
        vmin, vmax = float(p1), float(p99)
    if vmax - vmin < 5:
        vmax = vmin + 5
    gray = np.clip((elev - vmin) / (vmax - vmin), 0, 1)
    gray[~np.isfinite(elev)] = 0
    img = Image.fromarray((gray * 65535.0).astype(np.uint16), mode="I;16")
    return img, vmin, vmax


def generate_heightmap(
    box: dict,
    pixels: int,
    dest_dir: Path,
    heightmaps_dir: Path | None = None,
    strip_vegetation: bool = True,
    copy_to_game: bool = True,
    progress=None,
    cancel=None,
) -> dict:
    pixels = validate_heightmap_pixels(pixels)
    dest_dir.mkdir(parents=True, exist_ok=True)
    _PROGRESS_LOCAL.fn = progress
    _PROGRESS_LOCAL.cancel = cancel
    try:
        return _generate_heightmap(
            box, pixels, dest_dir, heightmaps_dir, strip_vegetation, copy_to_game
        )
    except JobCancelled:
        _progress(dest_dir, "Cancelled.")
        return {"ok": False, "cancelled": True, "error": "Cancelled"}
    finally:
        _PROGRESS_LOCAL.fn = None
        _PROGRESS_LOCAL.cancel = None


def _generate_heightmap(
    box: dict,
    pixels: int,
    dest_dir: Path,
    heightmaps_dir: Path | None,
    strip_vegetation: bool,
    copy_to_game: bool,
) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    _progress(dest_dir, "Computing Web Mercator grid (same stretch as OSM converter)…")

    to_merc = Transformer.from_crs("epsg:4326", "epsg:3857").transform
    to_ll = Transformer.from_crs("epsg:3857", "epsg:4326").transform
    west_m, south_m = to_merc(box["minlat"], box["minlon"])
    east_m, north_m = to_merc(box["maxlat"], box["maxlon"])
    xs = np.linspace(west_m, east_m, pixels)
    ys = np.linspace(north_m, south_m, pixels)  # row 0 = north
    mx, my = np.meshgrid(xs, ys)
    lats, lons = to_ll(mx, my)
    del mx, my

    zoom = choose_zoom(box)
    _progress(dest_dir, f"Terrarium zoom {zoom}")
    terr, terr_meta = _download_terrarium(box, zoom, dest_dir)
    _progress(dest_dir, "Resampling Terrarium onto TPF2 grid…")
    detail = _resample_mercator(terr, terr_meta, xs, ys)
    del terr

    sources = [f"Mapzen/Nextzen Terrarium z{zoom} (SRTM + regional DEMs + bathymetry)"]
    dtm = None
    _progress(dest_dir, "Trying FABDEM (forest/buildings removed)…")
    fab = _load_fabdem(box, dest_dir)
    if fab is not None:
        dtm = _merge_geo(fab, lats, lons)
        sources.append("FABDEM v1.2 (Copernicus GLO-30 with trees/buildings removed)")
        del fab
    else:
        _progress(dest_dir, "FABDEM unavailable, trying Copernicus GLO-30…")
        cop = _load_copernicus(box, dest_dir)
        if cop is not None:
            dtm = _merge_geo(cop, lats, lons)
            sources.append("Copernicus DEM GLO-30 (30 m DSM)")
            del cop
        else:
            _progress(dest_dir, "Copernicus unavailable, trying SRTMGL1…")
            srtm = _load_srtm(box, dest_dir)
            if srtm is not None:
                dtm = _merge_geo(srtm, lats, lons)
                sources.append("SRTMGL1 1-arc-second (AWS Skadi)")
                del srtm

    if dtm is not None:
        detail = np.where(np.isfinite(detail), detail, dtm)

    cell_m = abs(east_m - west_m) / max(1, pixels - 1)
    if strip_vegetation:
        _progress(dest_dir, "Mixing DTM + high-res detail, stripping tree/building bumps…")
        elev = _strip_vegetation(detail, dtm, cell_m)
        if dtm is None:
            sources.append("90 m median filter (local DTM estimate from Terrarium)")
    else:
        elev = detail

    if np.isnan(elev).any():
        mask = ~np.isfinite(elev)
        known = np.where(np.isfinite(elev), elev, 0.0)
        w = np.isfinite(elev).astype(np.float32)
        k = ndimage.gaussian_filter(known, 2.0)
        ww = ndimage.gaussian_filter(w, 2.0)
        filled = np.divide(k, np.maximum(ww, 1e-6))
        elev = np.where(mask, filled, elev)

    img, vmin, vmax = _to_png16(elev)
    name = (
        f"OSM_{box['center_lat']:.4f}_{box['center_lon']:.4f}_"
        f"{pixels}px.png"
    )
    out = dest_dir / name
    tmp = out.with_name(out.name + ".part")
    img.save(tmp, format="PNG")
    tmp.replace(out)
    flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
    out_flip = dest_dir / name.replace(".png", "_flipped.png")
    tmpf = out_flip.with_name(out_flip.name + ".part")
    flipped.save(tmpf, format="PNG")
    tmpf.replace(out_flip)

    shade = _hillshade(elev, cell=max(cell_m, 1.0))
    preview = Image.fromarray(shade, mode="L")
    if max(preview.size) > 1400:
        preview.thumbnail((1400, 1400))
    preview_path = dest_dir / "preview_hillshade.png"
    preview.save(preview_path)

    finite = elev[np.isfinite(elev)]
    water_hint = float(np.percentile(finite, 2))
    if water_hint < 8:
        water_hint = min(2.0, max(-2.0, float(np.percentile(finite, 8))))

    copied = ""
    if copy_to_game and heightmaps_dir:
        _progress(dest_dir, "Copying heightmap into TPF2 folder…")
        heightmaps_dir = Path(heightmaps_dir)
        heightmaps_dir.mkdir(parents=True, exist_ok=True)
        target = heightmaps_dir / name
        tmp = target.with_name(target.name + ".part")
        shutil.copy2(out, tmp)
        tmp.replace(target)
        copied = str(target)

    notes = dest_dir / "import_notes.txt"
    notes.write_text(
        "\n".join([
            "TPF2 heightmap — OSM-TPF2 Studio",
            f"pixels={pixels}x{pixels}  (4 m cells, meters={(pixels - 1) * 4})",
            f"bbox={box['minlon']},{box['minlat']},{box['maxlon']},{box['maxlat']}",
            "Web Mercator stretch matches the OSM converter (EPSG:3857).",
            f"PNG 16-bit grayscale: {out.name}",
            f"Map editor IMPORT → Range min = {vmin:.1f}   max = {vmax:.1f}",
            f"Suggested water level ≈ {water_hint:.1f} m  (one flat plane for the whole map)",
            f"Elevation in data: {float(np.min(finite)):.1f} … {float(np.max(finite)):.1f} m",
            "Sources:",
            *[f"  - {s}" for s in sources],
            "If north/south looks mirrored after import, use the *_flipped.png file.",
            "Copy the PNG into Steam userdata …/1066780/local/heightmaps then Refresh in the editor.",
            "Attribution: Mapzen/Nextzen elevation tiles; FABDEM v1.2 (Hawker et al., CC BY-NC-SA);",
            "Copernicus DEM GLO-30 © European Union; SRTM NASA/NGA.",
        ]),
        encoding="utf-8",
    )
    _progress(dest_dir, f"Done. Range {vmin:.1f}–{vmax:.1f} m → {out.name}")
    return {
        "ok": True,
        "png": str(out),
        "png_flip": str(out_flip),
        "preview": str(preview_path),
        "notes": str(notes),
        "copied": copied,
        "pixels": pixels,
        "min_m": round(vmin, 2),
        "max_m": round(vmax, 2),
        "water_m": round(water_hint, 2),
        "zoom": zoom,
        "sources": sources,
        "path": str(out),
    }
