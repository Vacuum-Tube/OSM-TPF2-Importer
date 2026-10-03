"""Read converted osmdata.lua and decide which Workshop packs the map needs."""
from __future__ import annotations

import re
import time
from collections import Counter
from pathlib import Path

# Unique lua `type = "..."` values that mean a street (highway) in osmdata.lua
STREET_TYPES = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "residential", "living_street",
    "unclassified", "service", "pedestrian", "footway", "cycleway",
    "path", "track", "bridleway", "raceway", "construction",
}
TRACK_TYPES = {
    "rail", "tram", "subway", "light_rail", "construction",
    "disused", "narrow_gauge", "preserved", "miniature",
}
FOOT_TYPES = {"footway", "path", "cycleway", "pedestrian", "track", "bridleway"}
URBAN_TYPES = {"residential", "living_street", "pedestrian", "tertiary", "service"}

TYPE_RE = re.compile(r'^\s*type\s*=\s*"([^"]+)"')
TRAM_RE = re.compile(r"^\s*tram\s*=\s*true")
SIGNAL_RE = re.compile(r"^\s*signal\s*=\s*\{")
BRIDGE_RE = re.compile(r'^\s*bridge\s*=\s*"(?!no)')
TUNNEL_RE = re.compile(r'^\s*tunnel\s*=\s*"(?!no)')
SE_RE = re.compile(r"SE-SJ")
ELECTRIFIED_RE = re.compile(r'^\s*electrified\s*=\s*"(?!no)(?!false)')
GAUGE_RE = re.compile(r"^\s*gauge\s*=\s*(\d+)")
SPEED_RE = re.compile(r"^\s*speed\s*=\s*(\d+)")
OBJECT_RE = re.compile(r'^\s*type\s*=\s*"(tree|fountain|bollard|litfass)"')
NAME_RE = re.compile(r"name\s*=")
TOWNS_HDR = "towns = {"
FORESTS_HDR = "forests = {"
GROUNDS_HDR = "grounds = {"
NODES_HDR = "nodes = {"
SHRUBS_HDR = "shrubs = {"
OBJECTS_HDR = "objects = {"
POLYGON_HDR = "polygon ="


def _scan_files(path: Path) -> list[Path]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4000]
    except OSError:
        return [path]
    if "osmdata_" in head and "require" in head:
        chunks = []
        for name in (
            "osmdata_edges.lua",
            "osmdata_towns.lua",
            "osmdata_areas.lua",
            "osmdata_objects.lua",
            "osmdata_nodes.lua",
            "osmdata_buildings.lua",
        ):
            p = path.parent / name
            if p.is_file():
                chunks.append(p)
        if chunks:
            return chunks
    return [path]


def analyze_osmdata(path: Path, progress=None) -> dict:
    """Single-pass scan. Does not load the whole Lua table into memory."""
    files = _scan_files(path)
    path = Path(path)

    types = Counter()
    objects = Counter()
    signals = 0
    signals_se = 0
    tram_edges = 0
    bridges = 0
    tunnels = 0
    electrified = 0
    highspeed = 0
    towns = 0
    forests = 0
    grounds = 0
    ctx = None
    forest_block = False
    ground_block = False
    town_block = False
    n = 0
    last_note = time.monotonic()
    total = max(1, sum(f.stat().st_size for f in files))
    seen = 0

    def emit(msg: str, pct) -> None:
        if not progress:
            return
        try:
            progress(msg, pct)
        except TypeError:
            progress(msg)

    emit("Reading osmdata.lua…", 8)
    for scan in files:
        town_block = scan.name == "osmdata_towns.lua"
        forest_block = False
        ground_block = False
        ctx = None
        with scan.open("r", encoding="utf-8", errors="replace", buffering=1024 * 1024) as fh:
            while True:
                line = fh.readline()
                if not line:
                    break
                n += 1
                now = time.monotonic()
                if now - last_note >= 0.45:
                    last_note = now
                    pos = seen + fh.tell()
                    emit(
                        f"Reading {scan.name}… {pos / 1e6:.1f}/{total / 1e6:.1f} MB",
                        8 + 60 * pos / total,
                    )
                if TOWNS_HDR in line:
                    town_block = True
                elif town_block and NODES_HDR in line and scan.name != "osmdata_towns.lua":
                    town_block = False
                elif town_block and NAME_RE.search(line):
                    towns += 1

                if FORESTS_HDR in line:
                    forest_block = True
                elif forest_block and (SHRUBS_HDR in line or GROUNDS_HDR in line):
                    forest_block = False
                elif forest_block and POLYGON_HDR in line:
                    forests += 1

                if GROUNDS_HDR in line:
                    ground_block = True
                elif ground_block and OBJECTS_HDR in line:
                    ground_block = False
                elif ground_block and POLYGON_HDR in line:
                    grounds += 1

                s = line.lstrip()
                if s.startswith("street = {"):
                    ctx = "street"
                    continue
                if s.startswith("track = {"):
                    ctx = "track"
                    continue
                if SIGNAL_RE.match(s):
                    ctx = "signal"
                    signals += 1
                    continue

                m = TYPE_RE.match(s)
                if m:
                    types[m.group(1)] += 1
                    om = OBJECT_RE.match(s)
                    if om:
                        objects[om.group(1)] += 1
                if TRAM_RE.match(s):
                    tram_edges += 1
                if SE_RE.search(line):
                    signals_se += 1
                if BRIDGE_RE.match(s):
                    bridges += 1
                if TUNNEL_RE.match(s):
                    tunnels += 1
                if ELECTRIFIED_RE.match(s) and ctx == "track":
                    electrified += 1
                sm = SPEED_RE.match(s)
                if sm and ctx == "track" and int(sm.group(1)) >= 160:
                    highspeed += 1
        seen += scan.stat().st_size

    emit("Finished reading osmdata.lua", 68)
    street_n = sum(types[t] for t in STREET_TYPES)
    track_n = sum(types[t] for t in TRACK_TYPES)
    foot_n = sum(types[t] for t in FOOT_TYPES)
    urban_n = sum(types[t] for t in URBAN_TYPES)
    motorway_n = types["motorway"] + types["motorway_link"] + types["trunk"] + types["trunk_link"]
    water_n = types["waterstream"]
    airport_n = types["aeroway"]
    tram_n = types["tram"] + tram_edges
    subway_n = types["subway"] + types["light_rail"]
    disused_n = types["disused"]

    features = []
    def add(name, n):
        if n:
            features.append(name)

    add("towns", towns)
    add("streets", street_n)
    add("urban", urban_n)
    add("motorway", motorway_n)
    add("footways", foot_n)
    add("tracks", track_n)
    add("tram", tram_n)
    add("subway", subway_n)
    add("disused", disused_n)
    add("highspeed", highspeed)
    add("electrified", electrified)
    add("signals", signals)
    add("signals_se", signals_se)
    add("crossings", signals)  # crossing mods useful whenever signals/tracks exist
    add("bridges", bridges)
    add("tunnels", tunnels)
    add("airport", airport_n)
    add("water", water_n)
    add("forests", forests)
    add("grounds", grounds)
    if track_n:
        features.append("tracks")
        if not signals:
            features.append("signals")  # still want signal pack on a railway map
    if street_n:
        features.append("prep_street")
    if track_n:
        features.append("prep_track")

    features = sorted(set(features))
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "towns": towns,
        "streets": street_n,
        "urban": urban_n,
        "motorway": motorway_n,
        "footways": foot_n,
        "tracks": track_n,
        "tram": tram_n,
        "subway": subway_n,
        "disused": disused_n,
        "highspeed": highspeed,
        "electrified": electrified,
        "signals": signals,
        "signals_se": signals_se,
        "bridges": bridges,
        "tunnels": tunnels,
        "airport": airport_n,
        "water": water_n,
        "forests": forests,
        "grounds": grounds,
        "objects": dict(objects),
        "type_counts": dict(types.most_common(40)),
        "features": features,
    }


def searches_for(features: list[str], region: str | None = None) -> list[str]:
    q = []
    feat = set(features)
    if "tram" in feat:
        q.append("tram street")
    if "streets" in feat:
        q.append("street")
    if "signals" in feat or "tracks" in feat:
        q.append("signal")
    if "tracks" in feat:
        q.append("track")
    if "airport" in feat:
        q.append("airport road")
    if "crossings" in feat or "tracks" in feat:
        q.append("crossing")
    if region == "SE":
        extra = []
        if "tram" in feat:
            extra.append("swedish tram")
        if "streets" in feat:
            extra.append("swedish street")
        if "signals" in feat or "tracks" in feat:
            extra.append("swedish signal")
        if "tracks" in feat:
            extra.append("swedish track")
        q = extra + q
    seen = set()
    out = []
    for item in q:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:5]
