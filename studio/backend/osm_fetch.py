"""Download OSM XML for a bounding box via Overpass, with OSM.org export fallback."""
from __future__ import annotations

import email.utils
import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable
from functools import lru_cache
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .jobs import JobCancelled, raise_if_cancelled
from .osm_access import note_host_cooldown, wait_for_request_slot

UA = "OSM-TPF2-Studio/1.3 (+https://github.com/Vacuum-Tube/OSM-TPF2-Importer; personal desktop app)"
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
OSM_EXPORT = "https://api.openstreetmap.org/api/0.6/map?bbox={minlon},{minlat},{maxlon},{maxlat}"
OSM_CACHE_TTL = 6 * 60 * 60
OSM_ATTRIBUTION = (
    "© OpenStreetMap contributors\n"
    "OpenStreetMap data is available under the Open Database License (ODbL): "
    "https://www.openstreetmap.org/copyright\n"
)
GEOFABRIK_HOME = "https://download.geofabrik.de/"
GEOFABRIK_PAGES = {
    "SE": ("Sweden", "https://download.geofabrik.de/europe/sweden.html"),
    "NO": ("Norway", "https://download.geofabrik.de/europe/norway.html"),
    "DK": ("Denmark", "https://download.geofabrik.de/europe/denmark.html"),
    "FI": ("Finland", "https://download.geofabrik.de/europe/finland.html"),
    "DE": ("Germany", "https://download.geofabrik.de/europe/germany.html"),
    "NL": ("Netherlands", "https://download.geofabrik.de/europe/netherlands.html"),
    "BE": ("Belgium", "https://download.geofabrik.de/europe/belgium.html"),
    "FR": ("France", "https://download.geofabrik.de/europe/france.html"),
    "GB": ("Great Britain", "https://download.geofabrik.de/europe/great-britain.html"),
    "UK": ("Great Britain", "https://download.geofabrik.de/europe/great-britain.html"),
    "IE": ("Ireland and Northern Ireland", "https://download.geofabrik.de/europe/ireland-and-northern-ireland.html"),
    "PL": ("Poland", "https://download.geofabrik.de/europe/poland.html"),
    "AT": ("Austria", "https://download.geofabrik.de/europe/austria.html"),
    "CH": ("Switzerland", "https://download.geofabrik.de/europe/switzerland.html"),
    "IT": ("Italy", "https://download.geofabrik.de/europe/italy.html"),
    "ES": ("Spain", "https://download.geofabrik.de/europe/spain.html"),
    "PT": ("Portugal", "https://download.geofabrik.de/europe/portugal.html"),
    "CZ": ("Czechia", "https://download.geofabrik.de/europe/czech-republic.html"),
    "US": ("United States", "https://download.geofabrik.de/north-america/us.html"),
    "CA": ("Canada", "https://download.geofabrik.de/north-america/canada.html"),
    "AU": ("Australia", "https://download.geofabrik.de/australia-oceania/australia.html"),
}


def _query_filtered(box: dict) -> str:
    s, w, n, e = box["minlat"], box["minlon"], box["maxlat"], box["maxlon"]
    return f"""
[out:xml][timeout:480][bbox:{s},{w},{n},{e}];
(
  way["highway"];
  way["railway"];
  way["waterway"];
  way["aeroway"~"^(runway|taxiway)$"];
  way["landuse"];
  way["natural"];
  way["leisure"];
  way["area:highway"];
  relation["landuse"];
  relation["natural"];
  relation["type"="multipolygon"]["landuse"];
  relation["type"="multipolygon"]["natural"];
  node["place"];
  node["natural"="tree"];
  node["amenity"="fountain"];
  node["barrier"="bollard"];
  node["advertising"="column"];
  node["railway"~"^(signal|switch)$"];
  way["building"~"^(house|detached|semidetached_house|semidetached|terrace|apartments|residential|dormitory|bungalow|farm|cabin|commercial|retail|office|supermarket|kiosk|hotel|motel|shop|industrial|warehouse|factory|manufacture|hangar|barn|works)$"];
  way["building"]["shop"];
  way["building"]["office"];
  way["building"]["industrial"];
  way["building"]["residential"];
  way["building"]["building:use"~"^(residential|commercial|retail|industrial)$"];
);
(._;>;);
out meta;
""".strip()


def _query_full(box: dict) -> str:
    s, w, n, e = box["minlat"], box["minlon"], box["maxlat"], box["maxlon"]
    return f"[out:xml][timeout:360];(node({s},{w},{n},{e});<;);out meta;"


def _ensure_bounds(xml: bytes, box: dict) -> bytes:
    if b"<bounds" in xml[:12000]:
        return xml
    tag = (
        f'<bounds minlat="{box["minlat"]}" minlon="{box["minlon"]}" '
        f'maxlat="{box["maxlat"]}" maxlon="{box["maxlon"]}"/>'
    ).encode("ascii")
    match = re.search(br"<osm[^>]*>", xml)
    if not match:
        return xml
    return xml[: match.end()] + b"\n  " + tag + xml[match.end() :]


def _inject_bounds_file(path: Path, box: dict) -> None:
    tag = (
        f'\n  <bounds minlat="{box["minlat"]}" minlon="{box["minlon"]}" '
        f'maxlat="{box["maxlat"]}" maxlon="{box["maxlon"]}"/>'
    ).encode("ascii")
    tmp = path.with_name(path.name + ".bounds.part")
    with path.open("rb") as fh:
        head = fh.read(16384)
        if b"<bounds" in head:
            return
        match = re.search(br"<osm[^>]*>", head)
        if not match:
            return
        split = match.end()
        with tmp.open("wb") as out:
            out.write(head[:split])
            out.write(tag)
            out.write(head[split:])
            shutil.copyfileobj(fh, out)
    tmp.replace(path)


def _looks_like_osm(head: bytes) -> bool:
    sample = head.lstrip()[:800].lower()
    return b"<osm" in sample or b"<?xml" in sample


def _open_url(req: urllib.request.Request, timeout: int):
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code in {429, 503}:
            note_host_cooldown(
                req.full_url,
                exc.headers.get("Retry-After") if exc.headers else None,
            )
        raise


def _download_to(url: str, dest: Path, data: bytes | None, timeout: int, progress=None, cancel=None) -> int:
    def validate_osm(path: Path) -> None:
        with path.open("rb") as fh:
            head = fh.read(800)
        if not _looks_like_osm(head):
            raise RuntimeError("Server did not return OSM XML")

    return _download_raw(
        url,
        dest,
        data,
        timeout,
        progress=progress,
        cancel=cancel,
        validate=validate_osm,
    )


def _download_raw(
    url: str,
    dest: Path,
    data: bytes | None,
    timeout: int,
    progress=None,
    cancel=None,
    validate: Callable[[Path], None] | None = None,
) -> int:
    headers = {"User-Agent": UA}
    if data:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if data else "GET",
    )
    tmp = dest.with_name(dest.name + ".part")
    n = 0
    last_note = 0
    try:
        wait_for_request_slot(url, cancel)
        with _open_url(req, timeout=timeout) as resp, tmp.open("wb") as out:
            while True:
                raise_if_cancelled(cancel)
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                n += len(chunk)
                if progress and n - last_note >= 512 * 1024:
                    last_note = n
                    progress(n)
        if n < 400:
            raise RuntimeError("Empty response")
        with tmp.open("rb") as fh:
            head = fh.read(80)
        sample = head.lstrip()[:80].lower()
        if sample.startswith(b"<!doctype") or sample.startswith(b"<html"):
            raise RuntimeError("Server returned an HTML page instead of the file")
        if validate:
            validate(tmp)
        tmp.replace(dest)
        return n
    except JobCancelled:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def geofabrik_for(lat=None, lon=None, country_code: str | None = None) -> dict:
    code = (country_code or "").upper()
    if not code and lat is not None and lon is not None:
        try:
            from . import bounds as B
            code = B.region_for(lat, lon) or ""
        except Exception:
            code = ""
        if not code:
            rev = reverse_geocode(lat, lon)
            code = (rev.get("country_code") or "").upper()
    page = GEOFABRIK_PAGES.get(code)
    if page:
        bz2 = page[1].replace(".html", "-latest.osm.bz2")
        return {"ok": True, "code": code, "label": page[0], "url": page[1], "bz2": bz2}
    return {"ok": True, "code": code or "", "label": "Geofabrik extracts", "url": GEOFABRIK_HOME, "bz2": ""}


def reverse_geocode(lat: float, lon: float) -> dict:
    try:
        return _reverse_geocode_cached(round(float(lat), 6), round(float(lon), 6))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        return {"error": f"Nominatim reverse lookup failed: {_http_error_message(exc)}"}


@lru_cache(maxsize=256)
def _reverse_geocode_cached(lat: float, lon: float) -> dict:
    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?lat={lat:.6f}&lon={lon:.6f}&format=json&zoom=5"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    wait_for_request_slot(url)
    with _open_url(req, timeout=20) as resp:
        row = json.loads(resp.read().decode("utf-8"))
    addr = row.get("address") or {}
    return {
        "label": row.get("display_name") or "",
        "country": addr.get("country") or "",
        "country_code": (addr.get("country_code") or "").upper(),
    }


def _cache_key(box: dict, mode: str) -> str:
    values = {key: round(float(box[key]), 7) for key in ("minlat", "minlon", "maxlat", "maxlon")}
    payload = json.dumps({"box": values, "mode": mode, "query_version": 1}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cached_osm(cache_file: Path, dest: Path, mode: str, force_refresh: bool) -> dict | None:
    try:
        if force_refresh or time.time() - cache_file.stat().st_mtime > OSM_CACHE_TTL:
            return None
        with cache_file.open("rb") as fh:
            head = fh.read(800)
        if not _looks_like_osm(head) or cache_file.stat().st_size < 400:
            return None
        shutil.copyfile(cache_file, dest)
        return {
            "ok": True,
            "path": str(dest),
            "bytes": dest.stat().st_size,
            "source": "local OSM cache",
            "mode": mode,
            "cached": True,
        }
    except OSError:
        return None


def _store_cache(source: Path, cache_file: Path) -> None:
    tmp = cache_file.with_name(cache_file.name + ".part")
    shutil.copyfile(source, tmp)
    tmp.replace(cache_file)


def _http_error_message(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        if retry_after:
            try:
                seconds = max(0, int(retry_after))
            except ValueError:
                try:
                    seconds = max(0, int(email.utils.parsedate_to_datetime(retry_after).timestamp() - time.time()))
                except (TypeError, ValueError, OverflowError, OSError):
                    seconds = None
            if seconds is not None:
                return f"HTTP {exc.code}; service asks clients to wait {seconds} seconds before retrying."
        return f"HTTP {exc.code}: {exc.reason}"
    return str(exc)


def download_bbox(
    box: dict,
    dest: Path,
    timeout: int = 480,
    mode: str = "filtered",
    progress=None,
    cancel=None,
    force_refresh: bool = False,
) -> dict:
    if mode not in {"filtered", "full"}:
        return {"ok": False, "error": f"Unsupported OSM download mode: {mode}"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = dest.parent / ".osm-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{mode}-{_cache_key(box, mode)}.osm"
    attribution_file = dest.with_name(dest.stem + ".attribution.txt")
    cached = _cached_osm(cache_file, dest, mode, force_refresh)
    if cached:
        note = f"Using cached OSM data from the last {OSM_CACHE_TTL // 3600} hours."
        if progress:
            progress(note, 100)
        cached["attribution"] = str(attribution_file)
        attribution_file.write_text(OSM_ATTRIBUTION, encoding="utf-8")
        return cached

    last_err = None
    query = _query_full(box) if mode == "full" else _query_filtered(box)
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")

    def note(msg: str, pct=None) -> None:
        if progress:
            progress(msg, pct)

    note(f"Building Overpass query ({mode})…", 2)
    raise_if_cancelled(cancel)
    host = urllib.parse.urlparse(OVERPASS_ENDPOINT).hostname or "Overpass"
    note(f"Connecting to official Overpass API ({host})…", 6)

    def bytes_cb(n: int) -> None:
        note(f"{host}: received {n / 1e6:.1f} MB…", min(82, 12 + n / 8e6 * 70))

    try:
        nbytes = _download_to(OVERPASS_ENDPOINT, dest, body, timeout, progress=bytes_cb, cancel=cancel)
        note("Writing map.osm bounds tag…", 92)
        _inject_bounds_file(dest, box)
        cache_warning = None
        try:
            _store_cache(dest, cache_file)
            attribution_file.write_text(OSM_ATTRIBUTION, encoding="utf-8")
        except OSError as local_error:
            cache_warning = f"Data downloaded, but local cache/attribution could not be saved: {local_error}"
        note(f"Saved {nbytes / 1e6:.1f} MB from {host}", 100)
        result = {
            "ok": True,
            "path": str(dest),
            "bytes": nbytes,
            "source": host,
            "mode": mode,
            "cached": False,
            "attribution": str(attribution_file),
        }
        if cache_warning:
            result["warning"] = cache_warning
        return result
    except JobCancelled:
        return {"ok": False, "cancelled": True, "error": "Cancelled"}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        last_err = _http_error_message(exc)
        note(f"{host} failed: {last_err}", 10)
        if isinstance(exc, urllib.error.HTTPError) and (exc.code == 429 or exc.code == 503):
            return {"ok": False, "error": f"Overpass request was rate-limited or temporarily unavailable. {last_err}"}

    bbox = dict(minlon=box["minlon"], minlat=box["minlat"], maxlon=box["maxlon"], maxlat=box["maxlat"])
    area = abs(box["maxlat"] - box["minlat"]) * abs(box["maxlon"] - box["minlon"])
    gf = geofabrik_for(box.get("center_lat"), box.get("center_lon"))
    if area > 0.24:
        return {
            "ok": False,
            "error": (
                (last_err or "Overpass failed")
                + ". Box is larger than the OSM.org export limit (0.25 deg²). "
                "Use a smaller map size, or download a Geofabrik extract and pick it with Use local .osm."
            ),
            "geofabrik": gf,
        }
    try:
        raise_if_cancelled(cancel)
        note("Trying OSM.org export…", 20)

        def bytes_cb(n: int) -> None:
            note(f"OSM.org: received {n / 1e6:.1f} MB…", min(85, 20 + n / 8e6 * 65))

        nbytes = _download_to(OSM_EXPORT.format(**bbox), dest, None, min(timeout, 120), progress=bytes_cb, cancel=cancel)
        _inject_bounds_file(dest, box)
        cache_warning = None
        try:
            _store_cache(dest, cache_file)
            attribution_file.write_text(OSM_ATTRIBUTION, encoding="utf-8")
        except OSError as local_error:
            cache_warning = f"Data downloaded, but local cache/attribution could not be saved: {local_error}"
        note(f"Saved {nbytes / 1e6:.1f} MB from api.openstreetmap.org", 100)
        result = {
            "ok": True,
            "path": str(dest),
            "bytes": nbytes,
            "source": "api.openstreetmap.org",
            "mode": "full",
            "cached": False,
            "attribution": str(attribution_file),
        }
        if cache_warning:
            result["warning"] = cache_warning
        return result
    except JobCancelled:
        return {"ok": False, "cancelled": True, "error": "Cancelled"}
    except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        return {"ok": False, "error": last_err or str(exc), "geofabrik": gf}


def geocode(query: str, limit: int = 8) -> list:
    return _geocode_cached(" ".join(query.split()), int(limit))


@lru_cache(maxsize=256)
def _geocode_cached(query: str, limit: int) -> list:
    q = urllib.parse.urlencode({"q": query, "format": "json", "limit": limit, "addressdetails": 1})
    url = (
        "https://nominatim.openstreetmap.org/search"
        f"?{q}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        wait_for_request_slot(url)
        with _open_url(req, timeout=20) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"Nominatim place search failed: {_http_error_message(exc)}") from exc
    out = []
    for row in rows:
        bb = row.get("boundingbox") or []
        hit = {
            "label": row.get("display_name"),
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "type": row.get("type") or row.get("class") or "",
            "country_code": ((row.get("address") or {}).get("country_code") or "").upper(),
        }
        if len(bb) == 4:
            try:
                hit["minlat"] = float(bb[0])
                hit["maxlat"] = float(bb[1])
                hit["minlon"] = float(bb[2])
                hit["maxlon"] = float(bb[3])
            except (TypeError, ValueError):
                pass
        out.append(hit)
    return out


def download_geofabrik_bz2(dest_dir: Path, box: dict | None = None, progress=None, cancel=None) -> dict:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    def note(msg: str, pct=None) -> None:
        if progress:
            progress(msg, pct)

    gf = geofabrik_for(
        box.get("center_lat") if box else None,
        box.get("center_lon") if box else None,
    )
    url = gf.get("bz2") or ""
    if not url:
        return {
            "ok": False,
            "error": "No Geofabrik .osm.bz2 for this place. Open the extract page and pick a region file.",
            **gf,
        }
    dest = dest_dir / Path(urllib.parse.urlparse(url).path).name
    if gf.get("code") in {"US", "CA", "AU"}:
        note(f"{gf.get('label')} extracts are several GB. Stop if that is not what you wanted.", 3)
    note(f"Downloading {gf.get('label') or 'Geofabrik'} extract…", 4)

    def bytes_cb(n: int) -> None:
        note(f"{dest.name}: {n / 1e6:.1f} MB…", min(92, 6 + n / 40e6 * 80))

    def validate_archive(path: Path) -> None:
        with path.open("rb") as fh:
            head = fh.read(8)
        if head[:3] != b"BZh" and head[:2] != b"\x1f\x8b":
            raise RuntimeError("Download did not look like .bz2/.gz")

    try:
        nbytes = _download_raw(
            url,
            dest,
            None,
            timeout=7200,
            progress=bytes_cb,
            cancel=cancel,
            validate=validate_archive,
        )
    except JobCancelled:
        return {"ok": False, "cancelled": True, "error": "Cancelled", **gf}
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError, OSError) as exc:
        return {"ok": False, "error": str(exc), **gf}
    note(f"Saved {dest.name} ({nbytes / 1e6:.1f} MB)", 100)
    return {
        "ok": True,
        "path": str(dest),
        "bytes": nbytes,
        "source": "download.geofabrik.de",
        **gf,
    }
