"""Download Esri World Imagery tiles covering the map box and stitch a PNG overlay."""
from __future__ import annotations

import math
import urllib.request
from io import BytesIO
from pathlib import Path

from .jobs import JobCancelled, raise_if_cancelled

from PIL import Image

UA = "OSM-TPF2-Studio/1.0 (Esri World Imagery overlay, personal use)"
TILE = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
    "MapServer/tile/{z}/{y}/{x}"
)


def _deg2num(lat, lon, z):
    x, y = _deg2num_float(lat, lon, z)
    return int(x), int(y)


def _deg2num_float(lat, lon, z):
    lat_rad = math.radians(lat)
    n = 2.0 ** z
    xtile = (lon + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def _tile_span(box: dict, zoom: int) -> tuple[int, int, int, int, int, int]:
    x0, y1 = _deg2num(box["minlat"], box["minlon"], zoom)
    x1, y0 = _deg2num(box["maxlat"], box["maxlon"], zoom)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return x0, x1, y0, y1, x1 - x0 + 1, y1 - y0 + 1


def _crop_to_box(mosaic: Image.Image, box: dict, zoom: int, x0: int, y0: int) -> Image.Image:
    fx_w, fy_s = _deg2num_float(box["minlat"], box["minlon"], zoom)
    fx_e, fy_n = _deg2num_float(box["maxlat"], box["maxlon"], zoom)
    left = (min(fx_w, fx_e) - x0) * 256
    right = (max(fx_w, fx_e) - x0) * 256
    top = (min(fy_n, fy_s) - y0) * 256
    bottom = (max(fy_n, fy_s) - y0) * 256
    w, h = mosaic.size
    left_i = max(0, min(w - 1, int(math.floor(left))))
    top_i = max(0, min(h - 1, int(math.floor(top))))
    right_i = max(left_i + 1, min(w, int(math.ceil(right))))
    bottom_i = max(top_i + 1, min(h, int(math.ceil(bottom))))
    return mosaic.crop((left_i, top_i, right_i, bottom_i))


def auto_zoom(box: dict, max_tiles: int = 80) -> int:
    for z in range(16, 10, -1):
        *_, nx, ny = _tile_span(box, z)
        if nx * ny <= max_tiles:
            return z
    return 11


def _save_png(img: Image.Image, path: Path) -> None:
    tmp = path.with_name(path.name + ".part")
    img.save(tmp, "PNG")
    tmp.replace(path)


def download_overlay(box: dict, dest_dir: Path, zoom: int | None = None, progress=None, cancel=None) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)

    def note(msg: str, pct=None) -> None:
        if progress:
            progress(msg, pct)

    if zoom is None:
        zoom = auto_zoom(box)
    x0, x1, y0, y1, nx, ny = _tile_span(box, zoom)
    total = nx * ny
    note(f"Overlay z{zoom}: {nx}×{ny} tiles…", 2)
    if total > 256:
        return {"ok": False, "error": f"Too many tiles ({nx}x{ny}). Lower zoom or shrink the box."}

    mosaic = Image.new("RGB", (nx * 256, ny * 256))
    done = 0
    try:
        for i, x in enumerate(range(x0, x1 + 1)):
            for j, y in enumerate(range(y0, y1 + 1)):
                raise_if_cancelled(cancel)
                url = TILE.format(z=zoom, x=x, y=y)
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        tile = Image.open(BytesIO(resp.read())).convert("RGB")
                except JobCancelled:
                    raise
                except Exception as exc:
                    return {"ok": False, "error": f"Tile {x},{y}: {exc}"}
                mosaic.paste(tile, (i * 256, j * 256))
                done += 1
                note(f"Tile {done}/{total} (z{zoom})", 4 + 82 * done / max(1, total))
    except JobCancelled:
        return {"ok": False, "cancelled": True, "error": "Cancelled"}

    note("Cropping overlay to yellow box…", 88)
    mosaic = _crop_to_box(mosaic, box, zoom, x0, y0)

    note("Saving overlay PNG…", 90)
    out = dest_dir / f"overlay_z{zoom}.png"
    _save_png(mosaic, out)
    flipped = mosaic.transpose(Image.FLIP_TOP_BOTTOM)
    out_flip = dest_dir / f"overlay_z{zoom}_tpf_flip.png"
    _save_png(flipped, out_flip)
    preview = mosaic.copy()
    preview.thumbnail((720, 720))
    prev_path = dest_dir / "preview_overlay.jpg"
    tmp_prev = prev_path.with_name(prev_path.name + ".part")
    preview.save(tmp_prev, "JPEG", quality=72)
    tmp_prev.replace(prev_path)

    tiles_dir = dest_dir / "tiles_4096"
    tiles_dir.mkdir(exist_ok=True)
    tw, th = mosaic.size
    tile_paths = []
    size = 4096
    gy = 0
    for y in range(0, th, size):
        gx = 0
        for x in range(0, tw, size):
            crop = mosaic.crop((x, y, min(x + size, tw), min(y + size, th)))
            canvas = Image.new("RGB", (size, size), (30, 40, 30))
            canvas.paste(crop, (0, 0))
            canvas_flip = canvas.transpose(Image.FLIP_TOP_BOTTOM)
            p = tiles_dir / f"tile_{gx}_{gy}.png"
            pf = tiles_dir / f"tile_{gx}_{gy}_flip.png"
            _save_png(canvas, p)
            _save_png(canvas_flip, pf)
            tile_paths.append(str(p))
            gx += 1
        gy += 1

    meta = dest_dir / "overlay_meta.txt"
    meta.write_text(
        "\n".join([
            "Source: Esri World Imagery (Esri, Maxar, Earthstar Geographics)",
            "Use only as a personal overlay. Keep this attribution with the map.",
            f"bbox={box['minlon']},{box['minlat']},{box['maxlon']},{box['maxlat']}",
            f"zoom={zoom}",
            f"png={out}",
            f"png_tpf_flipped={out_flip}",
            "TPF2 terrain textures must be 4096x4096 DDS (BC1/DXT1, vertically flipped, mipmaps).",
            "Convert the *_flip.png tiles in GIMP/Paint.NET to DDS BC1.",
            f"tiles={len(tile_paths)}",
        ]),
        encoding="utf-8",
    )
    note(f"Overlay ready {tw}×{th} px", 100)
    return {
        "ok": True,
        "png": str(out),
        "png_flip": str(out_flip),
        "preview": str(prev_path),
        "width": tw,
        "height": th,
        "zoom": zoom,
        "tiles": tile_paths,
        "meta": str(meta),
        "attribution": "Esri, Maxar, Earthstar Geographics",
    }
