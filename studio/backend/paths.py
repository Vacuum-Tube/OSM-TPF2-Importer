"""Detect TPF2 install, Steam libraries, Workshop, and heightmap folders."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import atomic

STEAM_APP = "1066780"
_VDF_PATH = re.compile(r'"path"\s+"([^"]+)"', re.I)
_EXE_NAMES = ("TransportFever2.exe", "TransportFever2")
GAME_CONFIG = {
    "tpf2": {
        "app_id": "1066780",
        "label": "Transport Fever 2",
        "names": ("Transport Fever 2", "TransportFever2"),
        "executables": ("TransportFever2.exe", "TransportFever2"),
    },
    "tf3": {
        "app_id": "3493540",
        "label": "Transport Fever 3",
        "names": ("Transport Fever 3", "TransportFever3"),
        "executables": ("TransportFever3.exe", "TransportFever3"),
    },
}


def discover_game(repo_root: Path, game_id: str = "tpf2", hint_game: str = "") -> dict:
    """Find a selected Transport Fever installation without changing game-specific tools."""
    config = GAME_CONFIG.get(game_id)
    if not config:
        return {"ok": False, "error": f"Unknown Transport Fever game: {game_id}"}

    repo_root = Path(repo_root).resolve()
    steam_dir = _steam_install()
    libraries = _steam_libraries(steam_dir)
    game = _find_game_for(repo_root, hint_game, libraries, config)
    if game:
        library = _library_from_game(game)
        if library and library not in libraries:
            libraries.insert(0, library)
        if not steam_dir:
            steam_dir = _steam_install_near(libraries)
    else:
        library = libraries[0] if libraries else None

    mods_dir = game / "mods" if game else None
    if mods_dir and not mods_dir.is_dir():
        mods_dir = None
    workshop = None
    for root in (library, *libraries):
        if not root:
            continue
        candidate = root / "steamapps" / "workshop" / "content" / config["app_id"]
        if candidate.is_dir():
            workshop = candidate
            break
    heightmaps = _find_heightmaps(steam_dir, libraries) if game_id == "tpf2" else None
    exe = _game_exe_for(game, config) if game else None
    ok = bool(game and mods_dir)
    return {
        "ok": ok,
        "game_id": game_id,
        "game_name": config["label"],
        "repo": str(repo_root),
        "game_dir": str(game) if game else "",
        "exe": str(exe) if exe else "",
        "mods_dir": str(mods_dir) if mods_dir else "",
        "steam_dir": str(steam_dir) if steam_dir else "",
        "steam_library": str(library) if library else "",
        "workshop_dir": str(workshop) if workshop else "",
        "heightmaps": str(heightmaps) if heightmaps else "",
        "work_dir": str(repo_root / "studio" / "work"),
        "found": [name for name, value in (("game", game), ("mods", mods_dir), ("workshop", workshop), ("heightmaps", heightmaps)) if value],
        "error": "" if ok else f"Could not find {config['label']}. Browse to its install folder.",
    }


def _game_exe_for(game: Path, config: dict) -> Path | None:
    for name in config["executables"]:
        candidate = game / name
        if candidate.is_file():
            return candidate
    return None


def _is_game_dir_for(path: Path | str | None, config: dict) -> bool:
    candidate = Path(path) if path else None
    if not candidate or not candidate.is_dir():
        return False
    return bool(_game_exe_for(candidate, config))


def _find_game_for(repo_root: Path, hint: str, libraries: list[Path], config: dict) -> Path | None:
    if hint:
        hinted = Path(hint).expanduser()
        if _is_game_dir_for(hinted, config):
            return hinted.resolve()
        parent = hinted.parent if hinted.is_file() else hinted
        if _is_game_dir_for(parent, config):
            return parent.resolve()

    current = repo_root
    for _ in range(8):
        if _is_game_dir_for(current, config):
            return current
        if current.parent == current:
            break
        current = current.parent
    if repo_root.parent.name.lower() == "mods" and _is_game_dir_for(repo_root.parent.parent, config):
        return repo_root.parent.parent.resolve()

    for library in libraries:
        for name in config["names"]:
            candidate = library / "steamapps" / "common" / name
            if _is_game_dir_for(candidate, config):
                return candidate.resolve()
        manifest = library / "steamapps" / f"appmanifest_{config['app_id']}.acf"
        if manifest.is_file():
            install_dir = _acf_installdir(manifest)
            if install_dir:
                candidate = library / "steamapps" / "common" / install_dir
                if _is_game_dir_for(candidate, config):
                    return candidate.resolve()
    return None


def discover(repo_root: Path, hint_game: str = "") -> dict:
    """Find every folder Studio needs from the game / Steam layout."""
    notes: list[str] = []
    repo_root = Path(repo_root).resolve()

    steam_dir = _steam_install()
    libraries = _steam_libraries(steam_dir)
    game = _find_game(repo_root, hint_game, libraries)
    if game:
        notes.append("game")
        lib = _library_from_game(game)
        if lib and lib not in libraries:
            libraries.insert(0, lib)
        if not steam_dir:
            steam_dir = _steam_install_near(libraries)

    steam_library = _library_from_game(game) if game else (libraries[0] if libraries else None)
    mods_dir = (game / "mods") if game else None
    if mods_dir:
        mods_dir.mkdir(parents=True, exist_ok=True)
        notes.append("mods")

    workshop = _workshop_dir(game, steam_library, libraries)
    if workshop:
        notes.append("workshop")

    heightmaps = _find_heightmaps(steam_dir, libraries)
    if heightmaps:
        notes.append("heightmaps")

    exe = _game_exe(game) if game else None
    ok = bool(game and mods_dir)
    return {
        "ok": ok,
        "repo": str(repo_root),
        "game_dir": str(game) if game else "",
        "exe": str(exe) if exe else "",
        "mods_dir": str(mods_dir) if mods_dir else "",
        "steam_dir": str(steam_dir) if steam_dir else "",
        "steam_library": str(steam_library) if steam_library else "",
        "workshop_dir": str(workshop) if workshop else "",
        "heightmaps": str(heightmaps) if heightmaps else "",
        "work_dir": str(repo_root / "studio" / "work"),
        "found": notes,
        "error": "" if ok else (
            "Could not find Transport Fever 2. Browse to the folder that contains TransportFever2.exe."
        ),
    }


def detect(repo_root: Path) -> dict:
    return discover(repo_root)


def apply_game_hint(repo_root: Path, game_dir: str) -> dict:
    return discover(repo_root, hint_game=game_dir)


def is_game_dir(path: Path | str | None) -> bool:
    p = Path(path) if path else None
    if not p or not p.is_dir():
        return False
    if _game_exe(p):
        return True
    name = p.name.lower()
    if "transport fever" in name and (p / "res").is_dir() and (p / "mods").is_dir():
        return True
    return False


def _game_exe(game: Path) -> Path | None:
    for name in _EXE_NAMES:
        trial = game / name
        if trial.is_file():
            return trial
    return None


def _find_game(repo_root: Path, hint: str, libraries: list[Path]) -> Path | None:
    if hint:
        hinted = Path(hint)
        if is_game_dir(hinted):
            return hinted.resolve()
        parent = hinted.parent if hinted.is_file() else hinted
        if is_game_dir(parent):
            return parent.resolve()

    here = repo_root
    for _ in range(8):
        if is_game_dir(here):
            return here
        if here.parent == here:
            break
        here = here.parent

    if repo_root.parent.name.lower() == "mods" and is_game_dir(repo_root.parent.parent):
        return repo_root.parent.parent.resolve()

    for lib in libraries:
        for name in ("Transport Fever 2", "TransportFever2"):
            trial = lib / "steamapps" / "common" / name
            if is_game_dir(trial):
                return trial.resolve()
        acf = lib / "steamapps" / f"appmanifest_{STEAM_APP}.acf"
        if acf.is_file():
            installdir = _acf_installdir(acf)
            if installdir:
                trial = lib / "steamapps" / "common" / installdir
                if is_game_dir(trial):
                    return trial.resolve()
    return None


def _acf_installdir(acf: Path) -> str:
    try:
        text = acf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = re.search(r'"installdir"\s+"([^"]+)"', text)
    return m.group(1) if m else ""


def _library_from_game(game: Path | None) -> Path | None:
    if not game:
        return None
    parts = [p.lower() for p in game.parts]
    if "steamapps" in parts and "common" in parts:
        try:
            return game.parent.parent.parent.resolve()
        except Exception:
            return None
    return None


def _workshop_dir(game: Path | None, steam_library: Path | None, libraries: list[Path]) -> Path | None:
    roots: list[Path] = []
    for item in (steam_library, *libraries):
        if item and item not in roots:
            roots.append(item)
    if game and "steamapps" in str(game).lower():
        try:
            roots.append(game.parents[2])
        except IndexError:
            pass
    for lib in roots:
        trial = lib / "steamapps" / "workshop" / "content" / STEAM_APP
        if trial.is_dir():
            return trial
    return None


def _steam_install() -> Path | None:
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                raw, _ = winreg.QueryValueEx(key, "SteamPath")
                p = Path(str(raw).replace("/", "\\"))
                if _is_steam_root(p):
                    return p.resolve()
        except OSError:
            pass
    for trial in (
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
        Path(r"D:\Steam"),
        Path(r"E:\Steam"),
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
    ):
        if _is_steam_root(trial):
            return trial.resolve()
    return None


def _is_steam_root(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (path / "steam.exe").is_file() or (path / "steamapps" / "libraryfolders.vdf").is_file()


def _steam_install_near(libraries: list[Path]) -> Path | None:
    for lib in libraries:
        if _is_steam_root(lib):
            return lib
        vdf = lib / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            for p in _vdf_paths(vdf):
                if _is_steam_root(p):
                    return p
    return _steam_install()


def _steam_libraries(steam_dir: Path | None) -> list[Path]:
    found: list[Path] = []

    def add(p: Path | None) -> None:
        if not p:
            return
        p = Path(p)
        if not p.is_dir():
            return
        rp = p.resolve()
        if rp not in found:
            found.append(rp)

    add(steam_dir)
    if steam_dir:
        for vdf in (
            steam_dir / "steamapps" / "libraryfolders.vdf",
            steam_dir / "config" / "libraryfolders.vdf",
        ):
            if vdf.is_file():
                for p in _vdf_paths(vdf):
                    add(p)
    return found


def _vdf_paths(vdf: Path) -> list[Path]:
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for raw in _VDF_PATH.findall(text):
        p = Path(raw.replace("\\\\", "\\"))
        if p.is_dir():
            out.append(p)
    return out


def _find_heightmaps(steam_dir: Path | None, libraries: list[Path]) -> Path | None:
    roots = []
    for item in (steam_dir, *libraries):
        if item:
            roots.append(item / "userdata")
            roots.append(item)
    extra = [
        Path(r"C:\Program Files (x86)\Steam\userdata"),
        Path(r"C:\Program Files\Steam\userdata"),
    ]
    seen: set[Path] = set()
    matches: list[Path] = []
    for root in roots + extra:
        if not root.is_dir() or root in seen:
            continue
        seen.add(root)
        try:
            hits = list(root.glob(f"*/{STEAM_APP}/local/heightmaps"))
        except OSError:
            continue
        matches.extend(hits)
        if not hits:
            for local in root.glob(f"*/{STEAM_APP}/local"):
                matches.append(local / "heightmaps")
    if not matches:
        return None
    existing = [p for p in matches if p.is_dir()]
    pool = existing or matches

    def score(p: Path) -> tuple:
        pngs = 0
        mtime = 0.0
        try:
            probe = p if p.exists() else p.parent
            mtime = probe.stat().st_mtime if probe.exists() else 0.0
            if p.is_dir():
                for child in p.iterdir():
                    if child.suffix.lower() == ".png":
                        pngs += 1
                        mtime = max(mtime, child.stat().st_mtime)
        except OSError:
            pass
        return (pngs, mtime)

    return max(pool, key=score)


def load_settings(work_dir: Path) -> dict:
    path = work_dir / "settings.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_settings(work_dir: Path, data: dict) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    atomic.write_text(work_dir / "settings.json", json.dumps(data, indent=2) + "\n")
    return data
