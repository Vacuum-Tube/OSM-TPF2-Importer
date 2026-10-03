"""Run the existing Python converter with studio bounds."""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from .jobs import JobCancelled, raise_if_cancelled, scale_progress
from . import osm_crop as Crop

_CONVERTER_MODULES = (
    "osm_tpf2_converter",
    "convert_data",
    "optimize_edges",
    "cubic_spline",
    "read_osm",
    "sort_edges",
    "graph_tools",
    "coord2metric",
    "lua_remove_nil",
    "vec2",
    "osmread",
    "converter_log",
)

_CONVERT_MARKERS = (
    ("Crop pass", 6),
    ("Cropped to", 14),
    ("Using cached crop", 12),
    ("Parse OSM XML", 16),
    ("One-pass load", 18),
    ("Read osm data", 12),
    ("Extracting bounding", 10),
    ("Loaded ", 22),
    ("Convert/Transform", 30),
    ("Places found", 38),
    ("Optimize Edges", 45),
    ("Split long", 50),
    ("Create Graphs", 55),
    ("Remove Nodes with high", 62),
    ("Remove unnecessary", 65),
    ("Remove short Edges", 68),
    ("Calculate Tangents", 74),
    ("Align Tangents", 78),
    ("Adjust Signals", 80),
    ("Sort Edges", 84),
    ("Write Lua", 90),
    ("Write Lua chunk", 92),
    ("Buildings kept", 86),
    ("Parse building ways", 20),
    ("Convert footprints", 55),
    ("Successfully converted", 100),
    ("Successfully wrote buildings", 100),
)

_STAT_PATTERNS = (
    ("towns", re.compile(r"Towns:\s+(\d+)")),
    ("nodes", re.compile(r"Nodes:\s+(\d+)")),
    ("edges", re.compile(r"Edges:\s+(\d+)")),
    ("areas", re.compile(r"Areas:\s+(\d+)")),
    ("objects", re.compile(r"Objects:\s+(\d+)")),
    ("buildings", re.compile(r"Buildings:\s+(\d+)")),
)


def percent_from_log(line: str) -> int:
    text = line or ""
    pct = -1
    for marker, value in _CONVERT_MARKERS:
        if marker in text:
            pct = value
    return pct


def stats_from_log(text: str) -> dict:
    stats: dict = {}
    for key, pat in _STAT_PATTERNS:
        match = pat.search(text or "")
        if match:
            stats[key] = int(match.group(1))
    return stats


def _watch_log(path: Path, progress, stop: threading.Event) -> None:
    pos = 0
    while not stop.wait(0.35):
        if not path.is_file():
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
        except OSError:
            continue
        lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
        if not lines:
            continue
        last = lines[-1]
        if progress:
            pct = percent_from_log(last)
            progress(last[:400], pct if pct >= 0 else None)


def _log_tail(path: Path, lines: int = 40) -> str:
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def _popen_kwargs() -> dict:
    kw: dict = {}
    if sys.platform == "win32":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return kw


def _kill(proc: subprocess.Popen) -> None:
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=4)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


def run_converter(
    python_dir: Path,
    osm_file: Path,
    out_lua: Path,
    map_meters: int,
    box: dict | None,
    timeout: int = 7200,
    progress=None,
    cancel=None,
    buildings_only: bool = False,
) -> dict:
    main_py = python_dir / "main.py"
    if not main_py.is_file():
        return {"ok": False, "error": f"Converter not found: {main_py}"}
    if not osm_file.is_file():
        return {"ok": False, "error": f"OSM file missing: {osm_file}"}

    if box:
        cropped = Crop.prepare(
            osm_file,
            box,
            out_lua.parent,
            map_meters=map_meters,
            progress=scale_progress(progress, 4, 14),
            cancel=cancel,
        )
        if cropped.get("cancelled"):
            return cropped
        if not cropped.get("ok"):
            return cropped
        osm_file = Path(cropped["path"])
        if progress and cropped.get("cropped"):
            extra = "cached crop" if cropped.get("cached") else "cropped OSM"
            progress(f"Convert {extra}: {osm_file.name}", 15)

    log = out_lua.parent / "convert.log"
    out_lua.parent.mkdir(parents=True, exist_ok=True)
    size_mb = osm_file.stat().st_size / 1e6
    label = "buildings sidecar" if buildings_only else "converter"
    if progress:
        progress(f"Starting {label} ({size_mb:.1f} MB OSM)…", 16 if box else 2)

    bbox_arg = None
    if box:
        bbox_arg = ",".join(
            str(box[k]) for k in ("minlat", "minlon", "maxlat", "maxlon")
        )
    meters = int(map_meters)

    if not getattr(sys, "frozen", False):
        result = _run_subprocess(
            python_dir,
            main_py,
            osm_file,
            out_lua,
            meters,
            bbox_arg,
            log,
            progress,
            cancel,
            timeout,
            buildings_only,
        )
        if result is not None:
            return result

    return _run_importlib(
        python_dir, osm_file, out_lua, meters, box, log, progress, buildings_only
    )


def _run_subprocess(
    python_dir: Path,
    main_py: Path,
    osm_file: Path,
    out_lua: Path,
    meters: int,
    bbox_arg: str | None,
    log: Path,
    progress,
    cancel,
    timeout: int,
    buildings_only: bool,
) -> dict | None:
    cmd = [
        sys.executable,
        str(main_py),
        str(Path(osm_file).resolve()),
        str(Path(out_lua).resolve()),
        f"{meters},{meters}",
    ]
    if bbox_arg:
        cmd.append(bbox_arg)
    cmd.extend(["--log", str(log.resolve())])
    if buildings_only:
        cmd.append("--buildings")

    env = os.environ.copy()
    python_dir_s = str(python_dir.resolve())
    # Append only — python/ may contain a PyInstaller dump.
    pp = env.get("PYTHONPATH", "")
    parts = [p for p in pp.split(os.pathsep) if p]
    if python_dir_s not in parts:
        parts.append(python_dir_s)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env["PYTHONUNBUFFERED"] = "1"

    stop = threading.Event()
    watcher = threading.Thread(target=_watch_log, args=(log, progress, stop), daemon=True)
    watcher.start()
    try:
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=python_dir_s,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_popen_kwargs(),
            )
        except OSError:
            return None
        started = time.time()
        while proc.poll() is None:
            raise_if_cancelled(cancel)
            if time.time() - started > timeout:
                _kill(proc)
                return {
                    "ok": False,
                    "error": f"Converter timed out after {timeout}s",
                    "log_tail": _log_tail(log),
                }
            time.sleep(0.35)
        tail = _log_tail(log)
        stats = stats_from_log(tail)
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": f"Converter exited with code {proc.returncode}",
                "log_tail": tail,
                **stats,
            }
        ok_mark = "Successfully wrote buildings" if buildings_only else "Successfully converted"
        if ok_mark not in tail and not out_lua.is_file():
            return {"ok": False, "error": "Converter finished without writing output", "log_tail": tail, **stats}
        if progress:
            progress("Convert finished.", 100)
        stats["ok"] = True
        stats["log_tail"] = tail
        stats["out"] = str(out_lua) if out_lua.is_file() else None
        stats["size"] = out_lua.stat().st_size if out_lua.is_file() else 0
        stats["buildings_only"] = buildings_only
        stats["osm"] = str(osm_file)
        return stats
    except JobCancelled:
        if "proc" in locals() and proc.poll() is None:
            _kill(proc)
        if progress:
            progress("Cancelled.", None)
        return {"ok": False, "cancelled": True, "error": "Cancelled", "log_tail": _log_tail(log)}
    finally:
        stop.set()
        watcher.join(timeout=1.5)


def _run_importlib(
    python_dir: Path,
    osm_file: Path,
    out_lua: Path,
    map_meters: int,
    box: dict | None,
    log: Path,
    progress,
    buildings_only: bool,
) -> dict:
    python_dir_s = str(python_dir)
    if python_dir_s not in sys.path:
        sys.path.append(python_dir_s)

    for name in _CONVERTER_MODULES:
        sys.modules.pop(name, None)

    stop = threading.Event()
    watcher = threading.Thread(target=_watch_log, args=(log, progress, stop), daemon=True)
    watcher.start()
    try:
        spec = importlib.util.spec_from_file_location("osm_tpf2_converter", python_dir / "main.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["osm_tpf2_converter"] = mod
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        bounds = None
        if box:
            bounds = {
                "minlat": box["minlat"],
                "minlon": box["minlon"],
                "maxlat": box["maxlat"],
                "maxlon": box["maxlon"],
            }
        fn = getattr(mod, "convert_buildings_only" if buildings_only else "convert_osm", None)
        if not fn:
            return {"ok": False, "error": "Converter entry point missing"}
        stats = fn(
            str(Path(osm_file).resolve()),
            str(Path(out_lua).resolve()),
            (int(map_meters), int(map_meters)),
            bounds,
            log_file=str(log.resolve()),
        )
        tail = _log_tail(log)
        stats = stats or {}
        stats["ok"] = True
        stats["log_tail"] = tail
        stats["out"] = str(out_lua) if out_lua.is_file() else None
        stats["size"] = out_lua.stat().st_size if out_lua.is_file() else 0
        stats["buildings_only"] = buildings_only
        stats["osm"] = str(osm_file)
        if progress:
            progress("Convert finished.", 100)
        return stats
    except Exception as exc:
        if progress:
            progress(str(exc), None)
        return {"ok": False, "error": str(exc), "log_tail": _log_tail(log)}
    finally:
        stop.set()
        watcher.join(timeout=1.5)
