"""pywebview JS bridge for OSM-TPF2 Studio."""
from __future__ import annotations

import threading
import time
import uuid
import webbrowser
from pathlib import Path

import webview

from . import bounds as B
from . import convert as C
from . import heightmap as H
from . import heightmap_limits as HL
from . import install as I
from . import mods as M
from . import osm_fetch as O
from . import osm_file as F
from . import overlay as V
from . import paths as P
from .jobs import JobCancelled


def _preview_data_url(path, max_px: int = 720) -> str:
    if not path:
        return ""
    try:
        import base64
        from io import BytesIO

        from PIL import Image

        img = Image.open(path)
        img.thumbnail((max_px, max_px))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=72)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return ""


class StudioApi:
    _window = None

    def __init__(self, repo_root: Path, ui_root: Path | None = None):
        self.repo = Path(repo_root)
        self.ui_root = Path(ui_root) if ui_root else self.repo / "studio" / "ui"
        self.work = self.repo / "studio" / "work"
        self.work.mkdir(parents=True, exist_ok=True)
        saved = P.load_settings(self.work)
        target_game = saved.get("target_game", "tpf2")
        if target_game not in P.GAME_CONFIG:
            target_game = "tpf2"
        game_dirs = saved.get("game_dirs") if isinstance(saved.get("game_dirs"), dict) else {}
        hint = game_dirs.get(target_game) or (saved.get("game_dir") if target_game == "tpf2" else "")
        found = P.discover_game(self.repo, target_game, hint_game=hint or "")
        self.state = dict(found)
        self.state["target_game"] = target_game
        self.state["game_dirs"] = dict(game_dirs)
        for k in (
            "size_key", "center_lat", "center_lon", "options", "osm_path", "osmdata_path",
        ):
            if saved.get(k):
                self.state[k] = saved[k]
        if found.get("ok"):
            self._apply_discovered(found, keep_heightmaps=True)
        self.state.setdefault("size_key", "huge")
        lat, lon = self.state.get("center_lat"), self.state.get("center_lon")
        if lat is None or lon is None or B.is_legacy_center(lat, lon):
            self.state.pop("center_lat", None)
            self.state.pop("center_lon", None)
            self.state["place_set"] = False
        else:
            self.state["place_set"] = True
        self.state["options"] = I.merge_options(self.state.get("options"))
        self.state.setdefault("osm_path", str(self.work / "map.osm"))
        self.state.setdefault("osmdata_path", str(self.work / "osmdata.lua"))
        if saved.get("file_box") and saved.get("box_minlat") is not None:
            self.state["file_box"] = True
            for key in ("box_minlat", "box_minlon", "box_maxlat", "box_maxlon"):
                if saved.get(key) is not None:
                    self.state[key] = saved[key]
            self.state["place_set"] = True
            self.state.setdefault("center_lat", (float(saved["box_minlat"]) + float(saved["box_maxlat"])) / 2)
            self.state.setdefault("center_lon", (float(saved["box_minlon"]) + float(saved["box_maxlon"])) / 2)
        if not self.state.get("place_set") and saved.get("center_lat") is not None:
            self._persist()
        self.jobs: dict[str, dict] = {}
        self._active: str | None = None

    def open_mode(self, mode: str) -> dict:
        pages = {
            "start": "start.html",
            "osm": ("index.html", "tpf2"),
            "tpf2": ("index.html", "tpf2"),
            "tf3": ("index.html", "tf3"),
            "tf3_converter": ("tf3_converter.html", None),
        }
        route = pages.get(str(mode))
        if not route:
            return {"ok": False, "error": f"Unknown Studio mode: {mode}"}
        if isinstance(route, tuple):
            page, game_id = route
            if game_id:
                self.select_game(game_id)
        else:
            page = route
        target = self.ui_root / page
        if not target.is_file():
            return {"ok": False, "error": f"Studio page not found: {target}"}
        url = target.resolve().as_uri()
        if isinstance(route, tuple) and route[1]:
            url += f"?game={route[1]}"
        return {"ok": True, "url": url}

    def select_game(self, game_id: str) -> dict:
        if game_id not in P.GAME_CONFIG:
            return {"ok": False, "error": f"Unknown Transport Fever game: {game_id}"}
        if game_id != self.state.get("target_game"):
            for key in ("game_dir", "mods_dir", "workshop_dir", "exe", "steam_library"):
                self.state[key] = ""
            self.state["heightmaps"] = "" if game_id == "tf3" else self.state.get("heightmaps", "")
        self.state["target_game"] = game_id
        found = self._ensure_paths()
        return {
            "ok": True,
            "game_id": game_id,
            "game_name": P.GAME_CONFIG[game_id]["label"],
            "paths": found,
            "supported_features": {
                "osm_download": True,
                "heightmap_export": True,
                "satellite_overlay": True,
                "in_game_osm_import": game_id == "tpf2",
            },
        }

    def _persist(self) -> None:
        P.save_settings(self.work, {
            "target_game": self.state.get("target_game", "tpf2"),
            "game_dirs": self.state.get("game_dirs", {}),
            "game_dir": self.state.get("game_dir"),
            "steam_library": self.state.get("steam_library"),
            "steam_dir": self.state.get("steam_dir"),
            "workshop_dir": self.state.get("workshop_dir"),
            "heightmaps": self.state.get("heightmaps"),
            "size_key": self.state.get("size_key"),
            "center_lat": self.state.get("center_lat") if self.state.get("place_set") else None,
            "center_lon": self.state.get("center_lon") if self.state.get("place_set") else None,
            "place_set": bool(self.state.get("place_set")),
            "options": self.state.get("options"),
            "osm_path": self.state.get("osm_path"),
            "osmdata_path": self.state.get("osmdata_path"),
            "file_box": bool(self.state.get("file_box")),
            "box_minlat": self.state.get("box_minlat") if self.state.get("file_box") else None,
            "box_minlon": self.state.get("box_minlon") if self.state.get("file_box") else None,
            "box_maxlat": self.state.get("box_maxlat") if self.state.get("file_box") else None,
            "box_maxlon": self.state.get("box_maxlon") if self.state.get("file_box") else None,
        })

    def _job(self, fn, kind: str = "", label: str = "") -> dict:
        if self._active:
            running = self.jobs.get(self._active)
            if running and running.get("status") == "running":
                return {
                    "ok": False,
                    "error": f"Busy: {running.get('label') or 'another job'} is still running. Wait until it finishes.",
                }
        jid = uuid.uuid4().hex[:12]
        started = time.time()
        rec = {
            "id": jid,
            "status": "running",
            "ok": None,
            "log": "Starting…",
            "kind": kind,
            "label": label or kind or "Job",
            "stage": "Starting…",
            "percent": -1,
            "started": started,
            "elapsed": 0,
            "detail": "",
            "cancel": threading.Event(),
        }
        self.jobs[jid] = rec
        self._active = jid

        def progress(msg: str, percent=None) -> None:
            rec["stage"] = str(msg)[:400]
            rec["log"] = rec["stage"]
            if percent is not None:
                rec["percent"] = max(-1, min(100, float(percent)))
            rec["elapsed"] = round(time.time() - started, 1)
            prev = rec.get("detail") or ""
            line = rec["stage"]
            if not prev.endswith(line):
                rec["detail"] = (prev + "\n" + line).strip()[-2500:]

        def wrap():
            try:
                result = fn(progress, rec["cancel"])
                result = result or {}
                kind_s, label_s, started_at = rec["kind"], rec["label"], rec["started"]
                rec.update(result)
                rec["kind"] = kind_s
                rec["label"] = label_s
                rec["started"] = started_at
                rec["elapsed"] = round(time.time() - started_at, 1)
                if result.get("cancelled"):
                    rec["status"] = "cancelled"
                    rec["ok"] = False
                    rec["stage"] = result.get("error") or "Stopped."
                    rec["log"] = rec["stage"]
                elif result.get("ok"):
                    rec["status"] = "done"
                    rec["percent"] = 100
                    if not rec.get("stage") or rec["stage"] == "Starting…":
                        rec["stage"] = "Done."
                    rec["log"] = rec["stage"]
                else:
                    rec["status"] = "error"
                    rec["stage"] = result.get("error") or rec.get("stage") or "Failed"
                    rec["log"] = rec["stage"]
            except JobCancelled:
                rec.update({
                    "ok": False,
                    "cancelled": True,
                    "error": "Cancelled",
                    "status": "cancelled",
                    "stage": "Stopped.",
                    "log": "Stopped.",
                    "elapsed": round(time.time() - started, 1),
                })
            except Exception as exc:
                rec.update({
                    "ok": False,
                    "error": str(exc),
                    "status": "error",
                    "stage": str(exc),
                    "log": str(exc),
                    "elapsed": round(time.time() - started, 1),
                })
            finally:
                if self._active == jid:
                    self._active = None

        threading.Thread(target=wrap, daemon=True).start()
        return {"job_id": jid, "ok": True}

    def cancel_job(self, job_id: str = "") -> dict:
        rec = self.jobs.get(job_id) if job_id else None
        if not rec and self._active:
            rec = self.jobs.get(self._active)
        if not rec or rec.get("status") != "running":
            return {"ok": False, "error": "No running job"}
        ev = rec.get("cancel")
        if ev is not None:
            ev.set()
        rec["stage"] = "Stopping…"
        rec["log"] = "Stopping…"
        return {"ok": True}

    def get_bootstrap(self) -> dict:
        size_key = self.state.get("size_key", "huge")
        meters = B.MAP_SIZES[size_key]["meters"]
        box = self._current_box(size_key)
        place_set = bool(box)
        scale = B.scale_factors(box, meters) if box else None
        osm_url = B.osm_export_url(box) if box else "https://www.openstreetmap.org/"
        lua = self._osmdata_file()
        return {
            "paths": {
                "repo": self.state.get("repo"),
                "game_dir": self.state.get("game_dir"),
                "mods_dir": self.state.get("mods_dir"),
                "steam_library": self.state.get("steam_library"),
                "steam_dir": self.state.get("steam_dir"),
                "work_dir": str(self.work),
                "osm_path": self.state.get("osm_path"),
                "osmdata_path": str(lua) if lua else "",
                "workshop_dir": self.state.get("workshop_dir"),
                "heightmaps": self.state.get("heightmaps"),
                "exe": self.state.get("exe"),
            },
            "map_sizes": B.MAP_SIZES,
            "heightmap_max_pixels": HL.MAX_HEIGHTMAP_PIXELS,
            "target_game": self.state.get("target_game", "tpf2"),
            "game_name": P.GAME_CONFIG[self.state.get("target_game", "tpf2")]["label"],
            "supported_features": {
                "osm_download": True,
                "heightmap_export": True,
                "satellite_overlay": True,
                "in_game_osm_import": self.state.get("target_game", "tpf2") == "tpf2",
            },
            "size_key": size_key,
            "place_set": place_set,
            "file_box": bool(self.state.get("file_box")),
            "view": dict(B.DEFAULT_VIEW),
            "box": box,
            "scale": scale,
            "options": I.merge_options(self.state.get("options")),
            "osm_url": osm_url,
            "work": self.work_status(),
        }

    def _current_box(self, size_key: str | None = None) -> dict | None:
        size_key = size_key or self.state.get("size_key", "huge")
        meters = B.MAP_SIZES.get(size_key, B.MAP_SIZES["huge"])["meters"]
        if self.state.get("file_box") and self.state.get("box_minlat") is not None:
            box = B.box_from_corners(
                float(self.state["box_minlat"]),
                float(self.state["box_minlon"]),
                float(self.state["box_maxlat"]),
                float(self.state["box_maxlon"]),
            )
            box["meters"] = meters
            return box
        if self.state.get("place_set") and self.state.get("center_lat") is not None:
            return B.box_from_center(float(self.state["center_lat"]), float(self.state["center_lon"]), meters)
        return None

    def _adopt_file_box(self, box: dict, size_key: str | None = None) -> None:
        self.state["file_box"] = True
        self.state["box_minlat"] = float(box["minlat"])
        self.state["box_minlon"] = float(box["minlon"])
        self.state["box_maxlat"] = float(box["maxlat"])
        self.state["box_maxlon"] = float(box["maxlon"])
        self.state["center_lat"] = float(box.get("center_lat") or (box["minlat"] + box["maxlat"]) / 2)
        self.state["center_lon"] = float(box.get("center_lon") or (box["minlon"] + box["maxlon"]) / 2)
        self.state["place_set"] = True
        if size_key:
            self.state["size_key"] = size_key
        elif box.get("suggested_size") in B.MAP_SIZES:
            self.state["size_key"] = box["suggested_size"]
        self._persist()

    def _apply_discovered(self, found: dict, keep_heightmaps: bool = True) -> dict:
        for key in (
            "game_dir", "mods_dir", "steam_library", "steam_dir",
            "workshop_dir", "heightmaps", "exe",
        ):
            if key == "heightmaps" and keep_heightmaps:
                existing = self.state.get("heightmaps")
                if existing:
                    p = Path(existing)
                    if p.is_dir() or (p.parent.is_dir() and "heightmaps" in str(p).replace("\\", "/")):
                        continue
            if found.get(key):
                self.state[key] = found[key]
        game_id = self.state.get("target_game", "tpf2")
        self.state.setdefault("game_dirs", {})[game_id] = self.state.get("game_dir", "")
        self._persist()
        return found

    def _ensure_paths(self, hint: str = "", keep_heightmaps: bool = True) -> dict:
        game_id = self.state.get("target_game", "tpf2")
        game_dirs = self.state.setdefault("game_dirs", {})
        found = P.discover_game(
            self.repo,
            game_id,
            hint_game=hint or game_dirs.get(game_id) or self.state.get("game_dir") or "",
        )
        if found.get("ok"):
            self._apply_discovered(found, keep_heightmaps=keep_heightmaps)
        return found

    def discover_paths(self, game_dir: str = "") -> dict:
        return self._ensure_paths(game_dir, keep_heightmaps=True)

    def set_paths(self, game_dir: str, steam_library: str = "") -> dict:
        found = self._ensure_paths(game_dir)
        if steam_library:
            self.state["steam_library"] = steam_library
            self._persist()
            found["steam_library"] = steam_library
        found["ok"] = bool(self.state.get("game_dir"))
        if not found.get("ok") and game_dir:
            label = P.GAME_CONFIG[self.state.get("target_game", "tpf2")]["label"]
            found["error"] = f"Not a {label} folder: {game_dir}"
        return found

    def compute_box(self, lat: float, lon: float, size_key: str) -> dict:
        if size_key not in B.MAP_SIZES:
            return {"ok": False, "error": f"Unknown size {size_key}"}
        self.state["center_lat"] = float(lat)
        self.state["center_lon"] = float(lon)
        self.state["place_set"] = True
        self.state["size_key"] = size_key
        self.state["file_box"] = False
        for key in ("box_minlat", "box_minlon", "box_maxlat", "box_maxlon"):
            self.state.pop(key, None)
        meters = B.MAP_SIZES[size_key]["meters"]
        box = B.box_from_center(float(lat), float(lon), meters)
        self._persist()
        return {
            "ok": True,
            "box": box,
            "scale": B.scale_factors(box, meters),
            "size": B.MAP_SIZES[size_key],
            "osm_url": B.osm_export_url(box),
            "area_deg2": B.bbox_area_deg2(box),
        }

    def set_size_key(self, size_key: str) -> dict:
        if size_key not in B.MAP_SIZES:
            return {"ok": False, "error": f"Unknown size {size_key}"}
        self.state["size_key"] = size_key
        self._persist()
        box = self._current_box(size_key)
        meters = B.MAP_SIZES[size_key]["meters"]
        if not box:
            return {"ok": True, "size": B.MAP_SIZES[size_key], "size_key": size_key}
        return {
            "ok": True,
            "box": box,
            "scale": B.scale_factors(box, meters),
            "size": B.MAP_SIZES[size_key],
            "osm_url": B.osm_export_url(box),
            "size_key": size_key,
            "file_box": bool(self.state.get("file_box")),
        }

    def geocode(self, query: str) -> list:
        return O.geocode(query)

    def pick_folder(self) -> dict:
        result = self._dialog(folder=True)
        if not result:
            return {"ok": False, "cancelled": True}
        path = result[0]
        return {"ok": True, "path": path}

    def pick_osm_file(self) -> dict:
        result = self._dialog(
            folder=False,
            file_types=(
                "OSM (*.osm;*.xml;*.osm.bz2;*.bz2;*.osm.gz;*.gz;*.pbf)",
                "All files (*.*)",
            ),
        )
        if not result:
            return {"ok": False, "cancelled": True}
        self.state["osm_path"] = result[0]
        info = self.inspect_osm(result[0])
        adopted = False
        bounds = info.get("bounds")
        if bounds and not self.state.get("place_set") and F.should_adopt(bounds):
            self._adopt_file_box(bounds)
            adopted = True
        elif bounds and not self.state.get("place_set") and not info.get("warning"):
            info["warning"] = (
                "This OSM file covers more ground than a TPF2 map. "
                "Search or Shift-click the area you want; convert crops to the yellow box."
            )
        self._persist()
        return {"ok": True, "path": result[0], "adopted": adopted, **info}

    def pick_tf3_source(self, folder: bool = True) -> dict:
        if folder:
            result = self._dialog(folder=True)
        else:
            result = self._dialog(
                folder=False,
                file_types=("Mod metadata (*.lua;*.json)", "All files (*.*)"),
            )
        if not result:
            return {"ok": False, "cancelled": True}
        return {"ok": True, "path": result[0]}

    def pick_tf3_destination(self) -> dict:
        result = self._dialog(folder=True)
        if not result:
            return {"ok": False, "cancelled": True}
        return {"ok": True, "path": result[0]}

    def convert_tf3_mod(
        self,
        source: str,
        destination: str,
        name: str = "",
        author: str = "",
    ) -> dict:
        from .tf3_converter_core import convert_mod, inspect_mod

        source_path = Path(source).expanduser()
        if not destination.strip():
            return {"ok": False, "error": "Choose an output folder."}
        destination_path = Path(destination).expanduser()
        if not source_path.exists():
            return {"ok": False, "error": f"Source path does not exist: {source_path}"}
        if not source_path.is_dir() and source_path.suffix.lower() not in {".lua", ".json"}:
            return {"ok": False, "error": "Source must be a mod folder, .lua file, or .json file."}
        source_root = source_path.resolve() if source_path.is_dir() else source_path.resolve().parent
        destination_resolved = destination_path.resolve()
        if (
            destination_resolved == source_root
            or destination_resolved.is_relative_to(source_root)
            or source_root.is_relative_to(destination_resolved)
        ):
            return {"ok": False, "error": "Choose an output folder outside the source mod folder."}
        if destination_path.exists():
            if not destination_path.is_dir():
                return {"ok": False, "error": "Output path exists and is not a folder."}
            if any(destination_path.iterdir()):
                return {"ok": False, "error": "Output folder is not empty. Choose a new or empty folder."}

        try:
            inspect_mod(source_path)
        except (OSError, ValueError, TypeError) as exc:
            return {"ok": False, "error": f"Could not read mod metadata: {exc}"}

        def job(progress, cancel=None):
            progress("Reading legacy mod metadata…", 5)
            result = convert_mod(
                source_path,
                destination_path,
                name=name.strip() or None,
                author=author.strip() or None,
            )
            progress("Wrote TF3 metadata and copied source files.", 100)
            return {"ok": True, **result}

        return self._job(job, kind="tf3-convert", label="Convert mod metadata for TF3")

    def _dialog(self, folder=False, file_types=None):
        if not self._window:
            return None
        file_types = file_types or tuple()
        if hasattr(webview, "FileDialog"):
            kind = webview.FileDialog.FOLDER if folder else webview.FileDialog.OPEN
            kwargs = {"directory": str(self.work)}
            if not folder:
                kwargs["file_types"] = file_types
            return self._window.create_file_dialog(kind, **kwargs)
        kind = webview.FOLDER_DIALOG if folder else webview.OPEN_DIALOG
        if folder:
            return self._window.create_file_dialog(kind)
        return self._window.create_file_dialog(kind, file_types=file_types)

    def download_osm(self, box: dict, mode: str = "filtered", force_refresh: bool = False) -> dict:
        dest = Path(self.state.get("osm_path") or (self.work / "map.osm"))

        def job(progress, cancel=None):
            result = O.download_bbox(
                box,
                dest,
                mode=mode,
                progress=progress,
                cancel=cancel,
                force_refresh=force_refresh,
            )
            if result.get("ok"):
                self.state["osm_path"] = result["path"]
                self._persist()
            return result

        return self._job(job, kind="osm", label="OSM download")

    def convert(self, box: dict, size_key: str, osm_path: str = "", buildings_only: bool = False) -> dict:
        if self.state.get("target_game", "tpf2") != "tpf2":
            return {
                "ok": False,
                "error": "The osmdata.lua converter and in-game OSM importer are currently TPF2-only.",
            }
        osm = Path(osm_path or self.state.get("osm_path") or (self.work / "map.osm"))
        if buildings_only:
            out = self.work / "osmdata_buildings.lua"
        else:
            out = Path(self.state.get("osmdata_path") or (self.work / "osmdata.lua"))
        if not box or not box.get("minlat"):
            box = self._current_box(size_key)
        if (not box or not box.get("minlat")) and osm.is_file():
            peeked = F.peek_bounds(osm)
            if peeked:
                self._adopt_file_box(peeked, size_key or peeked.get("suggested_size"))
                box = self._current_box(size_key)
        if not box or not box.get("minlat"):
            return {
                "ok": False,
                "error": "Search a place, Shift-click the map, or pick an OSM file that has a <bounds> header.",
            }
        size_key = size_key or self.state.get("size_key", "huge")
        meters = B.MAP_SIZES.get(size_key, B.MAP_SIZES["huge"])["meters"]

        def job(progress, cancel=None):
            result = C.run_converter(
                self.repo / "python",
                osm,
                out,
                meters,
                box,
                progress=progress,
                cancel=cancel,
                buildings_only=bool(buildings_only),
            )
            if result.get("ok") and not buildings_only:
                self.state["osmdata_path"] = result.get("out") or str(out)
                self._persist()
            return result

        label = "Buildings sidecar" if buildings_only else "Convert to osmdata.lua"
        return self._job(job, kind="convert", label=label)

    def convert_buildings(self, box: dict | None = None, size_key: str = "", osm_path: str = "") -> dict:
        return self.convert(box or {}, size_key, osm_path, buildings_only=True)

    def crop_osm(self, box: dict | None = None, size_key: str = "", osm_path: str = "") -> dict:
        from . import osm_crop as Crop

        osm = Path(osm_path or self.state.get("osm_path") or (self.work / "map.osm"))
        box = box if box and box.get("minlat") else self._current_box(size_key)
        if not box or not box.get("minlat"):
            return {"ok": False, "error": "Search a place or Shift-click the map first."}
        if not osm.is_file():
            return {"ok": False, "error": f"OSM file missing: {osm}"}
        size_key = size_key or self.state.get("size_key", "huge")
        meters = B.MAP_SIZES.get(size_key, B.MAP_SIZES["huge"])["meters"]

        def job(progress, cancel=None):
            result = Crop.prepare(
                osm,
                box,
                self.work,
                map_meters=meters,
                progress=progress,
                cancel=cancel,
            )
            if result.get("ok") and result.get("cropped"):
                self.state["osm_path"] = result["path"]
                self._persist()
            return result

        return self._job(job, kind="crop", label="Crop OSM to yellow box")

    def download_geofabrik(self) -> dict:
        box = self._current_box()

        def job(progress, cancel=None):
            result = O.download_geofabrik_bz2(self.work, box, progress=progress, cancel=cancel)
            if result.get("ok") and result.get("path"):
                self.state["osm_path"] = result["path"]
                self._persist()
            return result

        return self._job(job, kind="geofabrik", label="Geofabrik extract")

    def job_status(self, job_id: str) -> dict:
        rec = self.jobs.get(job_id)
        if not rec:
            return {"status": "unknown", "error": "No such job", "ok": False}
        st = {k: v for k, v in rec.items() if k != "cancel"}
        started = st.get("started") or time.time()
        if st.get("status") == "running":
            st["elapsed"] = round(time.time() - started, 1)
            kind = st.get("kind")
            if kind == "heightmap":
                prog = self.work / "heightmap" / "progress.txt"
                if prog.is_file():
                    msg = prog.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                    if msg:
                        st["stage"] = msg[-1][-400:]
                        st["log"] = st["stage"]
            elif kind == "mods":
                prog = self.work / "mods" / "progress.txt"
                if prog.is_file():
                    msg = prog.read_text(encoding="utf-8", errors="replace").strip()
                    if msg:
                        st["stage"] = msg[-400:]
                        st["log"] = st["stage"]
            elif kind == "convert":
                log = self.work / "convert.log"
                if not log.is_file():
                    log = self.repo / "python" / "log.txt"
                if log.is_file():
                    with log.open("rb") as fh:
                        fh.seek(0, 2)
                        size = fh.tell()
                        fh.seek(max(0, size - 8000))
                        chunk = fh.read().decode("utf-8", "replace")
                    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
                    if lines:
                        st["stage"] = lines[-1][-400:]
                        st["log"] = st["stage"]
                        st["detail"] = "\n".join(lines[-12:])
                        parsed = C.percent_from_log(lines[-1])
                        if parsed >= 0:
                            prev = st.get("percent")
                            st["percent"] = parsed if prev is None or prev < 0 else max(prev, parsed)
        return st

    def converter_log_tail(self) -> str:
        for log in (self.work / "convert.log", self.repo / "python" / "log.txt"):
            if not log.is_file():
                continue
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(lines[-50:])
        return ""

    def scan_mods(self) -> dict:
        if self.state.get("target_game", "tpf2") != "tpf2":
            return {"ok": False, "error": "Workshop mod matching is currently supported for TPF2 only."}
        found = self._ensure_paths()
        game = self.state.get("game_dir")
        if not game:
            return {"ok": False, "error": found.get("error") or "Could not find Transport Fever 2."}
        data = M.scan(game, self.state.get("steam_library") or None)
        data["ok"] = True
        data["paths"] = {
            "game_dir": game,
            "mods_dir": self.state.get("mods_dir"),
            "workshop_dir": self.state.get("workshop_dir"),
        }
        return data

    def open_workshop(self, file_id: str) -> dict:
        M.open_workshop(str(file_id))
        return {"ok": True}

    def open_missing_mods(self) -> dict:
        if self.state.get("target_game", "tpf2") != "tpf2":
            return {"ok": False, "error": "Workshop mod matching is currently supported for TPF2 only."}
        found = self._ensure_paths()
        game = self.state.get("game_dir")
        if not game:
            return {"ok": False, "error": found.get("error") or "Could not find Transport Fever 2."}
        return {"ok": True, **M.open_missing(game, self.state.get("steam_library") or None)}

    def search_workshop(self, query: str) -> dict:
        M.search_workshop(query or "street")
        return {"ok": True}

    def _work_osmdata(self) -> Path | None:
        for candidate in (self.state.get("osmdata_path"), self.work / "osmdata.lua"):
            if candidate:
                p = Path(candidate)
                if p.is_file():
                    return p
        return None

    def _osmdata_file(self) -> Path | None:
        game = Path(self.state.get("game_dir") or "")
        mods = Path(self.state.get("mods_dir") or "") if self.state.get("mods_dir") else (game / "mods" if game else None)
        live = None
        if mods:
            live = mods / "osm_importer_1" / "res" / "scripts" / "osm_importer" / "osmdata.lua"
        for candidate in (
            self.state.get("osmdata_path"),
            self.work / "osmdata.lua",
            live,
        ):
            if candidate:
                p = Path(candidate)
                if p.is_file():
                    return p
        return None

    def recommend_mods_from_map(self, subscribe: bool = True) -> dict:
        if self.state.get("target_game", "tpf2") != "tpf2":
            return {"ok": False, "error": "Workshop mod matching is currently supported for TPF2 only."}
        self._ensure_paths()
        lua = self._osmdata_file()
        if not lua:
            return {
                "ok": False,
                "error": "Convert OSM to osmdata.lua first, then press Find & subscribe mods for this map.",
            }
        dest = self.work / "mods"
        dest.mkdir(parents=True, exist_ok=True)

        def job(progress, cancel=None):
            (dest / "progress.txt").write_text("Starting…", encoding="utf-8")

            def both(msg: str, percent=None) -> None:
                (dest / "progress.txt").write_text(msg, encoding="utf-8")
                progress(msg, percent)

            result = M.recommend_for_map(
                lua,
                self.state.get("game_dir") or "",
                self.state.get("steam_library") or None,
                search_workshop_web=True,
                progress=both,
                lat=self.state.get("center_lat") if self.state.get("place_set") else None,
                lon=self.state.get("center_lon") if self.state.get("place_set") else None,
            )
            missing = result.get("missing") or []
            catalog_missing = [row for row in missing if row.get("source") != "workshop-search"]
            opened = {"opened": 0, "ids": []}
            if subscribe and catalog_missing:
                both(
                    f"Opening Steam subscribe for {min(12, len(catalog_missing))} missing catalog packs…",
                    92,
                )
                opened = M.subscribe_ids([row["id"] for row in catalog_missing], limit=12)
            result["subscribed"] = opened
            result["catalog_missing"] = catalog_missing
            result["path"] = str(lua)
            both("Done.", 100)
            return result

        return self._job(job, kind="mods", label="Mods for this map")

    def download_overlay(self, box: dict, zoom: int | None = None) -> dict:
        dest = self.work / "overlay"

        def job(progress, cancel=None):
            z = int(zoom) if zoom else None
            return V.download_overlay(box, dest, zoom=z, progress=progress, cancel=cancel)

        return self._job(job, kind="overlay", label="Satellite overlay")

    def download_heightmap(
        self,
        box: dict,
        size_key: str,
        strip_vegetation: bool = True,
        copy_to_game: bool = True,
        output_pixels: int | None = None,
    ) -> dict:
        dest = self.work / "heightmap"
        if self.state.get("target_game", "tpf2") == "tf3":
            if output_pixels is None:
                return {
                    "ok": False,
                    "error": "Enter the required TF3 heightmap pixel size. TPF2 presets are not assumed to match TF3.",
                }
            try:
                pixels = HL.validate_heightmap_pixels(output_pixels)
            except ValueError as exc:
                return {"ok": False, "error": str(exc)}
            copy_to_game = False
        else:
            pixels = B.MAP_SIZES.get(size_key, B.MAP_SIZES["huge"])["heightmap"]

        def job(progress, cancel=None):
            hm = ""
            if copy_to_game:
                progress("Finding TPF2 folders…", 1)
                found = self._ensure_paths()
                hm = found.get("heightmaps") or self.state.get("heightmaps") or ""
            if copy_to_game and hm:
                progress(f"Heightmaps: {hm}", 3)
            return H.generate_heightmap(
                box,
                int(pixels),
                dest,
                heightmaps_dir=Path(hm) if (copy_to_game and hm) else None,
                strip_vegetation=bool(strip_vegetation),
                copy_to_game=bool(copy_to_game and hm),
                progress=progress,
                cancel=cancel,
            )

        return self._job(job, kind="heightmap", label="Heightmap")

    def install(self, options: dict | None = None, game_dir: str = "") -> dict:
        if self.state.get("target_game", "tpf2") != "tpf2":
            return {
                "ok": False,
                "error": "The in-game OSM Importer installer is TPF2-only; no TF3-compatible importer is available yet.",
            }
        if options:
            self.state["options"] = I.merge_options(self.state.get("options"), options)
            self._persist()
        found = self._ensure_paths(game_dir)
        if not found.get("ok") or not self.state.get("mods_dir"):
            return {
                "ok": False,
                "error": found.get("error") or "Could not find Transport Fever 2 mods folder.",
            }
        mods = Path(self.state["mods_dir"])
        lua = self._work_osmdata()

        def job(progress, cancel=None):
            progress(f"Game: {self.state.get('game_dir')}", 2)
            progress(f"Mods: {mods}", 4)
            if self.state.get("workshop_dir"):
                progress(f"Workshop: {self.state.get('workshop_dir')}", 5)
            result = I.install_mod(
                self.repo,
                mods,
                lua,
                I.merge_options(self.state.get("options")),
                progress=progress,
            )
            result["paths"] = {
                "game_dir": self.state.get("game_dir"),
                "mods_dir": str(mods),
                "workshop_dir": self.state.get("workshop_dir") or "",
                "heightmaps": self.state.get("heightmaps") or "",
                "target": result.get("target") or "",
            }
            return result

        return self._job(job, kind="install", label="Install into Mods")

    def save_options(self, options: dict) -> dict:
        self.state["options"] = I.merge_options(self.state.get("options"), options)
        self._persist()
        return {"ok": True}

    def launch_game(self) -> dict:
        game_id = self.state.get("target_game", "tpf2")
        app_id = P.GAME_CONFIG[game_id]["app_id"]
        webbrowser.open(f"steam://rungameid/{app_id}")
        return {"ok": True}

    def open_osm_org(self, box: dict) -> dict:
        webbrowser.open(B.osm_export_url(box))
        return {"ok": True}

    def open_path(self, path: str) -> dict:
        p = Path(path)
        if p.is_file():
            webbrowser.open(p.parent.as_uri())
        elif p.is_dir():
            webbrowser.open(p.as_uri())
        else:
            return {"ok": False, "error": "Path not found"}
        return {"ok": True}

    def inspect_osm(self, path: str = "") -> dict:
        osm = Path(path or self.state.get("osm_path") or "")
        meta = F.file_meta(osm)
        if not meta:
            return {"ok": False, "error": f"OSM file missing: {osm}"}
        bounds = F.peek_bounds(osm)
        yellow = self._current_box()
        overlap = F.overlap_ratio(yellow, bounds) if yellow and bounds else None
        warning = ""
        if bounds and yellow and overlap is not None and overlap < 0.5:
            warning = (
                f"This OSM extract overlaps only {round(overlap * 100)}% of the yellow box. "
                "Use extract bounds, or the converter will crop/miss data."
            )
        elif bounds and not F.should_adopt(bounds):
            warning = (
                f"OSM <bounds> span about {bounds.get('span_m') or '?'} m — larger than a TPF2 map. "
                "Keep the yellow square where you want the map; convert will crop this file."
            )
        elif not bounds:
            warning = "No <bounds> tag in the first 1 MB. Convert will use the yellow box only."
        return {
            "ok": True,
            "path": meta["path"],
            "osm": meta,
            "bounds": bounds,
            "overlap": overlap,
            "warning": warning,
        }

    def use_osm_bounds(self, path: str = "") -> dict:
        info = self.inspect_osm(path)
        if not info.get("ok"):
            return info
        bounds = info.get("bounds")
        if not bounds:
            return {"ok": False, "error": "OSM file has no <bounds> header to adopt."}
        if info.get("osm"):
            self.state["osm_path"] = info["osm"]["path"]
        self._adopt_file_box(bounds)
        box = self._current_box()
        size_key = self.state.get("size_key", "huge")
        return {
            "ok": True,
            "adopted": True,
            "box": box,
            "scale": B.scale_factors(box, B.MAP_SIZES[size_key]["meters"]) if box else None,
            "size": B.MAP_SIZES[size_key],
            "osm_url": B.osm_export_url(box) if box else "",
            "size_key": size_key,
            "warning": info.get("warning") or "",
        }

    def _box_payload(self, box: dict | None) -> dict | None:
        if not box:
            return None
        size_key = self.state.get("size_key", "huge")
        meters = B.MAP_SIZES[size_key]["meters"]
        return {
            "ok": True,
            "box": box,
            "scale": B.scale_factors(box, meters),
            "size": B.MAP_SIZES[size_key],
            "osm_url": B.osm_export_url(box),
            "size_key": size_key,
            "file_box": bool(self.state.get("file_box")),
        }

    def _live_osmdata(self) -> Path | None:
        game = Path(self.state.get("game_dir") or "")
        mods = Path(self.state.get("mods_dir") or "") if self.state.get("mods_dir") else (game / "mods" if game else None)
        if not mods:
            return None
        p = mods / "osm_importer_1" / "res" / "scripts" / "osm_importer" / "osmdata.lua"
        return p if p.is_file() else None

    def work_status(self) -> dict:
        osm = Path(self.state.get("osm_path") or (self.work / "map.osm"))
        work_lua = self._work_osmdata()
        live_lua = self._live_osmdata()
        buildings = self.work / "osmdata_buildings.lua"
        yellow = self._current_box()
        osm_meta = F.file_meta(osm)
        osm_bounds = F.peek_bounds(osm) if osm_meta else None
        overlap = F.overlap_ratio(yellow, osm_bounds) if yellow and osm_bounds else None
        replace, note = (False, "no Studio osmdata.lua")
        if work_lua and live_lua:
            replace, note = I.should_replace_osmdata(work_lua, live_lua)
        elif work_lua and not live_lua:
            replace, note = True, "live osmdata.lua missing"
        box = yellow
        gf = O.geofabrik_for(box.get("center_lat") if box else None, box.get("center_lon") if box else None)
        warning = ""
        if osm_bounds and yellow and overlap is not None and overlap < 0.5:
            warning = f"OSM extract overlaps {round(overlap * 100)}% of the yellow box."
        elif osm_bounds and not F.should_adopt(osm_bounds):
            warning = (
                f"OSM file spans about {osm_bounds.get('span_m')} m. "
                "Convert crops to the yellow TPF2 square."
            )
        return {
            "ok": True,
            "osm": osm_meta,
            "osm_bounds": osm_bounds,
            "overlap": overlap,
            "warning": warning,
            "work_lua": F.file_meta(work_lua),
            "work_loader": F.looks_like_loader(work_lua) if work_lua else False,
            "live_lua": F.file_meta(live_lua),
            "buildings": F.file_meta(buildings if buildings.is_file() else None),
            "install": {"replace": replace, "note": note},
            "geofabrik": gf,
            "file_box": bool(self.state.get("file_box")),
            "place_set": bool(self.state.get("place_set")),
            "adoptable": bool(osm_bounds and F.should_adopt(osm_bounds)),
            "cropped": F.file_meta(self.work / "map_cropped.osm"),
            "pipeline": self._pipeline(osm_meta, work_lua, live_lua),
        }

    def _pipeline(self, osm_meta, work_lua, live_lua) -> dict:
        hm = self.work / "heightmap" / "preview_hillshade.png"
        ov = next(iter(sorted((self.work / "overlay").glob("overlay_z*.png"))), None) if (self.work / "overlay").is_dir() else None
        live_mod = None
        mods = self.state.get("mods_dir")
        if mods:
            live_mod = Path(mods) / "osm_importer_1" / "mod.lua"
        return {
            "place": bool(self._current_box()),
            "osm": bool(osm_meta),
            "convert": bool(work_lua),
            "heightmap": bool(hm.is_file()),
            "overlay": bool(ov and Path(ov).is_file()),
            "install": bool(live_mod and live_mod.is_file()),
            "live_osmdata": bool(live_lua),
        }

    def terrain_previews(self) -> dict:
        hm = self.work / "heightmap" / "preview_hillshade.png"
        overlay_dir = self.work / "overlay"
        ov = overlay_dir / "preview_overlay.jpg"
        if not ov.is_file() and overlay_dir.is_dir():
            pngs = [p for p in overlay_dir.glob("overlay_z*.png") if "_flip" not in p.name and "tile_" not in p.name]
            if pngs:
                ov = max(pngs, key=lambda p: p.stat().st_mtime)
            else:
                ov = None
        elif not ov.is_file():
            ov = None
        return {
            "ok": True,
            "heightmap": _preview_data_url(hm) if hm.is_file() else "",
            "overlay": _preview_data_url(ov) if ov else "",
            "heightmap_path": str(hm) if hm.is_file() else "",
            "overlay_path": str(ov) if ov else "",
        }

    def preview_install(self) -> dict:
        return self.work_status()

    def open_geofabrik(self) -> dict:
        box = self._current_box()
        gf = O.geofabrik_for(
            box.get("center_lat") if box else None,
            box.get("center_lon") if box else None,
        )
        webbrowser.open(gf["url"])
        return {"ok": True, **gf}
