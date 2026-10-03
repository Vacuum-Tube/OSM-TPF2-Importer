"""Detect installed TPF2 mods and open Steam Workshop pages (no unofficial downloads)."""
from __future__ import annotations

import html as html_lib
import re
import time
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import quote

from . import bounds as B
from . import osmdata_needs as N

STEAM_APP = "1066780"
UA = "OSM-TPF2-Studio/1.0 (workshop search, personal TPF2 rebuild)"
GERMAN_SKIP = re.compile(
    r"\b(german|deutsch|deutschland|berlin|hamburg|autobahnkreuz|connum|"
    r"ks-signal|h/?v-signal|signalkomponenten|hv69)\b",
    re.I,
)
# Steam Workshop browse HTML (2026): title is img alt and/or the filedetails link text.
ID_IMG_ALT_RE = re.compile(
    r'sharedfiles/filedetails/\?id=(\d+)"[^>]*>\s*<img[^>]*\balt="([^"]*)"',
    re.I,
)
ID_LINK_TEXT_RE = re.compile(
    r'sharedfiles/filedetails/\?id=(\d+)">([^<]{2,160})</a>',
    re.I,
)
RELEVANT = re.compile(
    r"sweden|swedish|svensk|"
    r"street|roads?|tram|track|signal|crossing|bridge|railway|"
    r"railroad|catenary|overhead|station|airport|footpath|pavement|slope|"
    r"transport fever",
    re.I,
)
NOISE = re.compile(
    r"apartment|building pack|era [abc]\b|ai addon|"
    r"locomotive|\b loco\b|vectron|\btrain\b|wagon|coach|class\s+[a-z0-9]|x2000|"
    r"archipelago|\bmap\b|asset of|street builder",
    re.I,
)
QUERY_ALIASES = {
    "street": ("street", "road", "town"),
    "tram": ("tram",),
    "signal": ("signal",),
    "track": ("track", "rail", "catenary"),
    "crossing": ("crossing",),
    "airport": ("airport", "runway", "taxiway"),
}

# when = osmdata features that make this pack worth subscribing
CATALOG = [
    {"id": "2243862504", "name": "Swedish modern signals 1.1", "use": "signals-se", "when": ["signals", "tracks"], "steam": True, "region": "SE"},
    {"id": "2243864500", "name": "Swedish track / catenary", "use": "tracks-se", "when": ["tracks", "electrified"], "steam": True, "region": "SE"},
    {"id": "2243933428", "name": "Swedish modern level crossings", "use": "crossings-se", "when": ["tracks", "signals", "crossings"], "steam": True, "region": "SE"},
    {"id": "1935575411", "name": "Swedish towns and street names 1", "use": "names-se", "when": ["towns"], "steam": True, "region": "SE"},
    {"id": "1935575685", "name": "Swedish towns and street names 2", "use": "names-se", "when": ["towns"], "steam": True, "region": "SE"},
    {"id": "1933747406", "name": "Marc's Street and Trampack", "use": "streets", "when": ["streets", "urban", "tram"], "steam": True},
    {"id": "1968514713", "name": "ext.roads footpaths standalone", "use": "streets", "when": ["footways"], "steam": True},
    {"id": "2021038808", "name": "Street fine tuning", "use": "streets", "when": ["footways", "streets"], "steam": True},
    {"id": "2363493916", "name": "Freestyle train station", "use": "streets-bridges", "when": ["bridges", "footways"], "steam": True},
    {"id": "1943578742", "name": "SMP 2.0", "use": "streets", "when": ["urban", "streets"], "steam": True},
    {"id": "2232249704", "name": "Airport Roads", "use": "airport", "when": ["airport"], "steam": True},
    {"id": "2187434173", "name": "TFMR 2.0 Bridge", "use": "bridges", "when": ["bridges"], "steam": True},
    {"id": "1939805466", "name": "Bridge Type-1", "use": "bridges", "when": ["bridges"], "steam": True},
    {"id": "1983390040", "name": "Old Track", "use": "tracks", "when": ["disused"], "steam": True},
    {"id": "2072274420", "name": "Ballast", "use": "tracks", "when": ["tracks"], "steam": True},
    {"id": "2294246900", "name": "Signal Distance", "use": "signals", "when": ["signals", "tracks"], "steam": True},
    {"id": "2247194383", "name": "Spacky Trees conifers", "use": "forests", "when": ["forests"], "steam": True},
    {"id": "2014569888", "name": "Water Textures", "use": "water", "when": ["water"], "steam": True},
    {"id": "2763516913", "name": "Ingo's textures pavement", "use": "paver", "when": ["grounds"], "steam": True},
    {"id": "3432184100", "name": "Ingo's Vegetation Extended", "use": "paver", "when": ["grounds", "forests"], "steam": True},
    {"id": "2161175689", "name": "Realistic Railway Slopes", "use": "prep", "when": ["prep_track", "tracks"], "steam": True},
    {"id": "2206802861", "name": "Maximum Street Slopes", "use": "prep", "when": ["prep_street", "streets", "motorway"], "steam": True},
    {"id": "2558586098", "name": "Realistic Track Curve Speeds", "use": "prep", "when": ["prep_track", "tracks", "highspeed"], "steam": True},
]

FOLDER_HINTS = {
    "snowball_forester": "forests",
    "Paver_": "paver",
    "unixroot_natural_environment": "tracks",
    "vt_natural_environment": "tracks",
    "RTP-Roads": "streets",
    "eis_os_commonapi": "core",
    "eis_os_trackpackage": "tracks",
}

CATALOG_BY_ID = {item["id"]: item for item in CATALOG}


def _mods_dir(game_dir: Path) -> Path:
    return game_dir / "mods"


def _workshop_dir(game: Path, steam_library: str | None) -> Path | None:
    candidates = []
    if steam_library:
        candidates.append(Path(steam_library))
    if "steamapps" in str(game).lower():
        candidates.extend([game.parents[2], game.parents[1]])
    for lib in candidates:
        for rel in (
            Path("steamapps") / "workshop" / "content" / STEAM_APP,
            Path("workshop") / "content" / STEAM_APP,
        ):
            trial = lib / rel
            if trial.is_dir():
                return trial
    return None


def installed_workshop_ids(game_dir: str, steam_library: str | None = None) -> set[str]:
    game = Path(game_dir)
    wdir = _workshop_dir(game, steam_library)
    if not wdir:
        return set()
    return {p.name for p in wdir.iterdir() if p.is_dir() and p.name.isdigit()}


def scan(game_dir: str, steam_library: str | None = None) -> dict:
    game = Path(game_dir)
    mods = _mods_dir(game)
    installed_folders = []
    if mods.is_dir():
        installed_folders = [p.name for p in mods.iterdir() if p.is_dir()]

    ws_ids = installed_workshop_ids(game_dir, steam_library)
    rows = []
    for item in CATALOG:
        rows.append({**item, "installed": item["id"] in ws_ids})

    folder_hits = []
    for folder in installed_folders:
        for hint, use in FOLDER_HINTS.items():
            if folder.startswith(hint) or hint in folder:
                folder_hits.append({"folder": folder, "use": use, "installed": True})
                break

    missing = [r for r in rows if not r["installed"]]
    return {
        "workshop_ids": sorted(ws_ids),
        "mod_folders": installed_folders,
        "catalog": rows,
        "local_packs": folder_hits,
        "missing_steam": missing,
        "workshop_search": "https://steamcommunity.com/workshop/browse/?appid=1066780&searchtext=",
    }


def open_workshop(file_id: str) -> None:
    webbrowser.open(f"steam://url/CommunityFilePage/{file_id}")


def open_missing(game_dir: str, steam_library: str | None = None) -> dict:
    data = scan(game_dir, steam_library)
    for item in data["missing_steam"][:12]:
        open_workshop(item["id"])
    return {"opened": len(data["missing_steam"][:12]), "total_missing": len(data["missing_steam"])}


def search_workshop(query: str) -> None:
    webbrowser.open(
        "https://steamcommunity.com/workshop/browse/?appid=1066780&searchtext=" + quote(query)
    )


def _parse_workshop_titles(raw: str) -> list[tuple[str, str]]:
    titles: dict[str, str] = {}
    for fid, title in ID_IMG_ALT_RE.findall(raw):
        title = html_lib.unescape(title).strip()
        if fid not in titles and title:
            titles[fid] = title
    for fid, title in ID_LINK_TEXT_RE.findall(raw):
        title = html_lib.unescape(title).strip()
        if fid not in titles and title:
            titles[fid] = title
    return list(titles.items())


def _keep_search_hit(title: str, query: str, region: str | None = None) -> bool:
    if len(title) < 8:
        return False
    if NOISE.search(title):
        return False
    if region == "SE" and GERMAN_SKIP.search(title):
        return False
    q = (query or "").lower().strip()
    if q.startswith("swedish"):
        if not re.search(r"sweden|swedish|svensk", title, re.I):
            return False
        topic = q.replace("swedish", "", 1).strip()
        words = QUERY_ALIASES.get(topic, (topic,) if topic else ())
        if words and not any(w in title.lower() for w in words):
            return False
    return bool(RELEVANT.search(title))


def search_workshop_listings(query: str, limit: int = 8, region: str | None = None) -> list[dict]:
    url = (
        f"https://steamcommunity.com/workshop/browse/?appid={STEAM_APP}"
        f"&searchtext={quote(query)}&browsesort=trend&section=readytouseitems"
        "&childpublishedfileid=0&actualsort=trend&p=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        raw = resp.read().decode("utf-8", "replace")
    out = []
    seen = set()
    for fid, title in _parse_workshop_titles(raw):
        if fid in seen or fid in CATALOG_BY_ID:
            continue
        if not _keep_search_hit(title, query, region=region):
            continue
        seen.add(fid)
        out.append({"id": fid, "name": title, "use": f"search:{query}", "steam": True, "source": "workshop-search"})
        if len(out) >= limit:
            break
    return out


def recommend_for_map(
    osmdata_path: Path,
    game_dir: str,
    steam_library: str | None = None,
    search_workshop_web: bool = True,
    progress=None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    def note(msg: str, percent=None) -> None:
        if not progress:
            return
        try:
            progress(msg, percent)
        except TypeError:
            progress(msg)

    note("Reading osmdata.lua…", 5)
    stats = N.analyze_osmdata(osmdata_path, progress=progress)
    features = set(stats.get("features") or [])
    region = B.region_for(lat, lon) if lat is not None and lon is not None else None
    note("Matching Workshop catalog to map contents…", 70)

    wanted = []
    for item in CATALOG:
        when = item.get("when") or []
        if when and features.isdisjoint(when):
            continue
        if not when:
            continue
        need_region = item.get("region")
        if need_region and need_region != region:
            continue
        row = {**item, "reason": _reason(item["when"], stats)}
        wanted.append(row)

    extra = []
    if search_workshop_web:
        queries = N.searches_for(list(features), region=region)
        for i, query in enumerate(queries):
            note(f"Workshop search: {query}", 72 + 18 * (i / max(1, len(queries))))
            try:
                hits = search_workshop_listings(query, limit=3, region=region)
            except Exception as exc:
                extra.append({"error": str(exc), "query": query})
                continue
            for hit in hits:
                hit["reason"] = f"Steam search “{query}”"
                extra.append(hit)
            time.sleep(0.35)

    seen = {w["id"] for w in wanted}
    extras_ok = []
    for hit in extra:
        if hit.get("error"):
            extras_ok.append(hit)
            continue
        if hit["id"] in seen:
            continue
        seen.add(hit["id"])
        extras_ok.append(hit)

    ws_ids = installed_workshop_ids(game_dir, steam_library) if game_dir else set()
    rows = []
    for row in wanted + [h for h in extras_ok if h.get("id")]:
        row = dict(row)
        row["installed"] = row["id"] in ws_ids
        rows.append(row)

    missing = [r for r in rows if not r.get("installed")]
    return {
        "ok": True,
        "stats": stats,
        "features": sorted(features),
        "recommended": rows,
        "missing": missing,
        "search_errors": [h for h in extras_ok if h.get("error")],
        "vanilla_fallback": True,
    }


def subscribe_ids(file_ids: list[str], limit: int = 12) -> dict:
    ids = []
    seen = set()
    for fid in file_ids:
        fid = str(fid)
        if fid.isdigit() and fid not in seen:
            seen.add(fid)
            ids.append(fid)
    opened = ids[:limit]
    for fid in opened:
        open_workshop(fid)
        time.sleep(0.2)
    return {"ok": True, "opened": len(opened), "ids": opened, "total": len(ids)}


def _reason(when: list[str], stats: dict) -> str:
    bits = []
    labels = {
        "streets": f"{stats.get('streets', 0)} streets",
        "urban": f"{stats.get('urban', 0)} urban streets",
        "motorway": f"{stats.get('motorway', 0)} motorway edges",
        "footways": f"{stats.get('footways', 0)} foot/cycle ways",
        "tracks": f"{stats.get('tracks', 0)} tracks",
        "tram": f"{stats.get('tram', 0)} tram edges",
        "subway": f"{stats.get('subway', 0)} subway/light rail",
        "disused": f"{stats.get('disused', 0)} disused tracks",
        "highspeed": "high-speed tracks",
        "electrified": "electrified tracks",
        "signals": f"{stats.get('signals', 0)} signals",
        "signals_se": "Swedish (SE-SJ) signals",
        "crossings": "level crossings",
        "bridges": f"{stats.get('bridges', 0)} bridges",
        "airport": f"{stats.get('airport', 0)} runway/taxiway",
        "water": f"{stats.get('water', 0)} streams",
        "forests": f"{stats.get('forests', 0)} forests",
        "grounds": f"{stats.get('grounds', 0)} ground areas",
        "towns": f"{stats.get('towns', 0)} towns",
        "prep_street": "street slopes",
        "prep_track": "track slopes",
    }
    for key in when:
        if stats.get(key) or key in {"prep_street", "prep_track", "crossings", "highspeed", "electrified", "signals_se"}:
            if key in labels:
                bits.append(labels[key])
    return " · ".join(bits[:3]) or "used by this map"
