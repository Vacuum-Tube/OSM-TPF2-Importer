"""Crop a Geofabrik/Overpass extract to the TPF2 yellow box (no osmosis)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from . import osm_file as F
from .jobs import JobCancelled, raise_if_cancelled

_META = "map_cropped.json"
_OUT = "map_cropped.osm"


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _in_box(box: dict, lat: float, lon: float) -> bool:
    return box["minlat"] <= lat <= box["maxlat"] and box["minlon"] <= lon <= box["maxlon"]


def _box_key(box: dict) -> dict:
    return {
        "minlat": round(float(box["minlat"]), 7),
        "minlon": round(float(box["minlon"]), 7),
        "maxlat": round(float(box["maxlat"]), 7),
        "maxlon": round(float(box["maxlon"]), 7),
    }


def cached_crop(source: Path, dest_dir: Path, box: dict) -> Path | None:
    dest_dir = Path(dest_dir)
    out = dest_dir / _OUT
    meta_path = dest_dir / _META
    if not out.is_file() or not meta_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    src = Path(source).resolve()
    try:
        st = src.stat()
    except OSError:
        return None
    if str(meta.get("source") or "") != str(src):
        return None
    if int(meta.get("mtime") or 0) != int(st.st_mtime):
        return None
    if int(meta.get("size") or 0) != int(st.st_size):
        return None
    if meta.get("box") != _box_key(box):
        return None
    if out.stat().st_size < 200:
        return None
    return out


def prepare(source: Path, box: dict, dest_dir: Path, map_meters: int | None = None, progress=None, cancel=None) -> dict:
    source = Path(source)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    def note(msg: str, pct=None) -> None:
        if progress:
            progress(msg, pct)

    if F.classify(source) == "pbf":
        return _crop_pbf(source, dest_dir, box, note=note, cancel=cancel)

    if not F.needs_crop(source, box, map_meters):
        note("OSM already map-sized; skip crop.", 12)
        return {"ok": True, "path": str(source), "cropped": False, "cached": False}

    hit = cached_crop(source, dest_dir, box)
    if hit:
        note(f"Using cached crop ({hit.stat().st_size / 1e6:.1f} MB).", 14)
        return {"ok": True, "path": str(hit), "cropped": True, "cached": True}

    try:
        out, written = crop_xml(source, dest_dir / _OUT, box, progress=progress, cancel=cancel)
    except JobCancelled:
        return {"ok": False, "cancelled": True, "error": "Cancelled"}
    _write_meta(source, dest_dir, box, out, written)
    return {
        "ok": True,
        "path": str(out),
        "cropped": True,
        "cached": False,
        "bytes": out.stat().st_size,
        "written": written,
    }


def _crop_pbf(source: Path, dest_dir: Path, box: dict, note=None, cancel=None) -> dict:
    osmium = shutil.which("osmium")
    if not osmium:
        return {
            "ok": False,
            "error": (
                "PBF extracts need OSM XML. Download the .osm.bz2 from Geofabrik, "
                "or install osmium-tool and retry."
            ),
        }
    out = dest_dir / _OUT
    bbox = f"{box['minlon']},{box['minlat']},{box['maxlon']},{box['maxlat']}"
    if note:
        note("Cropping PBF with osmium…", 8)
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(
            [osmium, "extract", "-b", bbox, "--overwrite", "-o", str(out), str(source)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            **kw,
        )
    except OSError as exc:
        return {"ok": False, "error": f"osmium failed to start: {exc}"}
    try:
        while proc.poll() is None:
            raise_if_cancelled(cancel)
            time.sleep(0.35)
    except JobCancelled:
        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            try:
                proc.kill()
            except OSError:
                pass
        return {"ok": False, "cancelled": True, "error": "Cancelled"}
    if proc.returncode != 0 or not out.is_file():
        return {"ok": False, "error": "osmium extract failed"}
    _write_meta(source, dest_dir, box, out)
    return {"ok": True, "path": str(out), "cropped": True, "cached": False, "bytes": out.stat().st_size}


def _write_meta(source: Path, dest_dir: Path, box: dict, out: Path, written: dict | None = None) -> None:
    st = source.stat()
    payload = {
        "source": str(source.resolve()),
        "mtime": int(st.st_mtime),
        "size": int(st.st_size),
        "box": _box_key(box),
        "out": str(out),
        "out_bytes": out.stat().st_size,
        "written": written or {},
    }
    (dest_dir / _META).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _release(elem) -> None:
    # Never clear nd/tag/member first — that wipes refs before the parent way/relation ends.
    if _local(elem.tag) in {"node", "way", "relation", "bounds"}:
        elem.clear()


def crop_xml(source: Path, dest: Path, box: dict, progress=None, cancel=None) -> tuple[Path, dict]:
    source = Path(source)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    def note(msg: str, pct=None) -> None:
        if progress:
            progress(msg, pct)

    note("Crop pass 1: find nodes/ways in the yellow box…", 8)
    in_ids: set[int] = set()
    keep_ways: set[int] = set()
    needed: set[int] = set()
    keep_rels: set[int] = set()
    n = 0
    stream = F.open_osm_bytes(source)
    try:
        context = ET.iterparse(stream, events=("end",))
        for _, elem in context:
            raise_if_cancelled(cancel)
            n += 1
            if n % 250000 == 0:
                note(f"Scan {n:,} OSM objects · in-box nodes {len(in_ids):,}…", min(48, 8 + n / 8e6 * 40))
            tag = _local(elem.tag)
            if tag == "node":
                try:
                    lat = float(elem.get("lat"))
                    lon = float(elem.get("lon"))
                    nid = int(elem.get("id"))
                except (TypeError, ValueError):
                    elem.clear()
                    continue
                if _in_box(box, lat, lon):
                    in_ids.add(nid)
            elif tag == "way":
                refs = []
                for child in elem:
                    if _local(child.tag) == "nd":
                        try:
                            refs.append(int(child.get("ref")))
                        except (TypeError, ValueError):
                            continue
                if refs and any(ref in in_ids for ref in refs):
                    keep_ways.add(int(elem.get("id")))
                    needed.update(refs)
            elif tag == "relation":
                keep = False
                try:
                    rid = int(elem.get("id"))
                except (TypeError, ValueError):
                    elem.clear()
                    continue
                for child in elem:
                    if _local(child.tag) != "member":
                        continue
                    try:
                        ref = int(child.get("ref"))
                    except (TypeError, ValueError):
                        continue
                    kind = child.get("type")
                    if kind == "way" and ref in keep_ways:
                        keep = True
                        break
                    if kind == "node" and (ref in in_ids or ref in needed):
                        keep = True
                        break
                if keep:
                    keep_rels.add(rid)
            _release(elem)
    finally:
        try:
            stream.close()
        except OSError:
            pass

    needed |= in_ids
    note(
        f"Keep {len(needed):,} nodes, {len(keep_ways):,} ways, {len(keep_rels):,} relations. Writing crop…",
        52,
    )

    tmp = dest.with_name(dest.name + ".part")
    written = {"node": 0, "way": 0, "relation": 0}
    n = 0
    stream = F.open_osm_bytes(source)
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as out:
            out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            out.write('<osm version="0.6" generator="OSM-TPF2-Studio">\n')
            out.write(
                f'  <bounds minlat="{box["minlat"]}" minlon="{box["minlon"]}" '
                f'maxlat="{box["maxlat"]}" maxlon="{box["maxlon"]}"/>\n'
            )
            context = ET.iterparse(stream, events=("end",))
            for _, elem in context:
                raise_if_cancelled(cancel)
                n += 1
                if n % 250000 == 0:
                    note(
                        f"Write {n:,} · nodes {written['node']:,} ways {written['way']:,}…",
                        min(88, 52 + n / 8e6 * 30),
                    )
                tag = _local(elem.tag)
                if tag == "node":
                    try:
                        nid = int(elem.get("id"))
                    except (TypeError, ValueError):
                        elem.clear()
                        continue
                    if nid in needed:
                        out.write(_node_xml(elem))
                        written["node"] += 1
                elif tag == "way":
                    try:
                        wid = int(elem.get("id"))
                    except (TypeError, ValueError):
                        elem.clear()
                        continue
                    if wid in keep_ways:
                        out.write(_way_xml(elem))
                        written["way"] += 1
                elif tag == "relation":
                    try:
                        rid = int(elem.get("id"))
                    except (TypeError, ValueError):
                        elem.clear()
                        continue
                    if rid in keep_rels:
                        out.write(_rel_xml(elem))
                        written["relation"] += 1
                _release(elem)
            out.write("</osm>\n")
    except JobCancelled:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        try:
            stream.close()
        except OSError:
            pass

    tmp.replace(dest)
    note(
        f"Cropped to {dest.name} ({dest.stat().st_size / 1e6:.1f} MB) · "
        f"{written['node']:,} nodes / {written['way']:,} ways / {written['relation']:,} relations",
        92,
    )
    return dest, written


def _tags_xml(elem) -> str:
    bits = []
    for child in elem:
        if _local(child.tag) != "tag":
            continue
        k = child.get("k")
        v = child.get("v")
        if k is None or v is None:
            continue
        bits.append(f'    <tag k="{_esc(k)}" v="{_esc(v)}"/>\n')
    return "".join(bits)


def _node_xml(elem) -> str:
    nid = elem.get("id")
    lat = elem.get("lat")
    lon = elem.get("lon")
    tags = _tags_xml(elem)
    if not tags:
        return f'  <node id="{_esc(nid)}" lat="{_esc(lat)}" lon="{_esc(lon)}"/>\n'
    return (
        f'  <node id="{_esc(nid)}" lat="{_esc(lat)}" lon="{_esc(lon)}">\n'
        f"{tags}"
        "  </node>\n"
    )


def _way_xml(elem) -> str:
    bits = [f'  <way id="{_esc(elem.get("id"))}">\n']
    for child in elem:
        name = _local(child.tag)
        if name == "nd":
            bits.append(f'    <nd ref="{_esc(child.get("ref"))}"/>\n')
        elif name == "tag":
            bits.append(f'    <tag k="{_esc(child.get("k"))}" v="{_esc(child.get("v"))}"/>\n')
    bits.append("  </way>\n")
    return "".join(bits)


def _rel_xml(elem) -> str:
    bits = [f'  <relation id="{_esc(elem.get("id"))}">\n']
    for child in elem:
        name = _local(child.tag)
        if name == "member":
            bits.append(
                f'    <member type="{_esc(child.get("type"))}" ref="{_esc(child.get("ref"))}" '
                f'role="{_esc(child.get("role") or "")}"/>\n'
            )
        elif name == "tag":
            bits.append(f'    <tag k="{_esc(child.get("k"))}" v="{_esc(child.get("v"))}"/>\n')
    bits.append("  </relation>\n")
    return "".join(bits)
