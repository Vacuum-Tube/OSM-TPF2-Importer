import os
import re
import subprocess
from osmread import parse_file, Node, Way, Relation

osmosis_path = "osmosis\\bin\\osmosis"  # sry unix, please adjust...

_BOUNDS_TAG = re.compile(br"<bounds\b([^>]*)/?>")
_ATTR = re.compile(r"""(\w+)\s*=\s*["']([^"']*)["']""")


def crop_bounds(filename, bounds):
    extension = os.path.splitext(filename)[-1]
    if extension == ".pbf":
        read_comm = "--read-pbf"
    elif extension == ".osm":
        read_comm = "--read-xml"
    elif extension == ".bz2":
        read_comm = "--read-xml"
    else:
        assert 0, "Unknown OSM File Extension: " + extension
    filename_new = filename + "_crop.osm"
    print(f"Extracting bounding box area from '{filename}' via osmosis ...")
    complprocess = subprocess.run(
        [
            osmosis_path,
            read_comm,
            f"file={filename}",
            "--bounding-box",
            f"top={bounds['maxlat']}",
            f"left={bounds['minlon']}",
            f"bottom={bounds['minlat']}",
            f"right={bounds['maxlon']}",
            "completeWays=yes",
            "completeRelations=no",
            "--write-xml",
            filename_new,
        ],
        check=False,
    )
    complprocess.check_returncode()
    print(f"Saved to '{filename_new}'")
    return filename_new


def isinbounds(bounds, lat, lon):
    return bounds["minlat"] <= lat <= bounds["maxlat"] and bounds["minlon"] <= lon <= bounds["maxlon"]


def _is_xml_osm(filename):
    lower = str(filename).lower()
    return (
        lower.endswith(".osm")
        or lower.endswith(".xml")
        or lower.endswith(".osm.xml")
        or lower.endswith(".osm.bz2")
        or lower.endswith(".bz2")
        or lower.endswith(".osm.gz")
        or lower.endswith(".gz")
    )


def read_bounds(filename):
    """Scan the OSM XML header for <bounds> without parsing the whole file."""
    if not _is_xml_osm(filename):
        return None
    from osmread import _open
    with _open(filename) as fh:
        head = fh.read(262144)
        match = _BOUNDS_TAG.search(head)
        if match is None:
            match = _BOUNDS_TAG.search(head + fh.read(1024 * 1024 - 262144))
    if match is None:
        raise AssertionError("OSM file has no <bounds> element in the first 1 MB")
    attr = match.group(1).decode("utf-8", "replace")
    parsed = dict(_ATTR.findall(attr))
    bounds = {}
    for key in ("minlat", "minlon", "maxlat", "maxlon"):
        if key not in parsed:
            raise AssertionError("OSM <bounds> missing " + key)
        bounds[key] = float(parsed[key])
    return bounds


def _resolve_bounds(filename, bounds):
    file_bounds = None
    try:
        file_bounds = read_bounds(filename)
        if file_bounds:
            print("Bounds of osm file:", file_bounds)
    except AssertionError as exc:
        print("OSM header bounds:", exc)
    use = bounds or file_bounds
    if use is None:
        raise AssertionError(
            "No map bounds: pass the Studio yellow box, or include <bounds> in the OSM file"
        )
    if bounds:
        print("Using Studio/map bounds for out-of-bounds flags:", bounds)
    return use


def _bounds_close(a, b, eps=0.0008):
    if not a or not b:
        return False
    try:
        return all(abs(float(a[k]) - float(b[k])) <= eps for k in ("minlat", "minlon", "maxlat", "maxlon"))
    except (KeyError, TypeError, ValueError):
        return False


def _already_cropped(filename, bounds):
    """True when the file header is already the yellow box (Studio crop / Overpass)."""
    try:
        file_bounds = read_bounds(filename)
    except AssertionError:
        return False
    return _bounds_close(file_bounds, bounds)


def _read_one_pass(filename, use):
    print("One-pass load (file already cropped to this box)")
    nodes = {}
    ways = {}
    relations = {}
    n = 0
    for entity in parse_file(filename):
        n += 1
        if n % 500000 == 0:
            print(f"Load {n} objects, kept nodes {len(nodes)}")
        if isinstance(entity, Node):
            if not isinbounds(use, entity.lat, entity.lon):
                entity.tags["outofbounds"] = True
            nodes[entity.id] = entity
        elif isinstance(entity, Way):
            ways[entity.id] = entity
        elif isinstance(entity, Relation):
            relations[entity.id] = entity
    print(f"Loaded {len(nodes)} Nodes / {len(ways)} Ways / {len(relations)} Relations")
    return nodes, ways, relations


def read(filename, bounds=None):
    print(f"Read osm data from '{filename}' ...")
    use = _resolve_bounds(filename, bounds)
    assert str(filename).lower().endswith((".osm", ".pbf", ".xml", ".bz2", ".gz")), "File type needs to be .osm / .osm.bz2 / .pbf"
    if _already_cropped(filename, use):
        return _read_one_pass(filename, use)

    in_ids = set()
    keep_ways = set()
    needed = set()
    keep_rels = set()
    n = 0
    for entity in parse_file(filename):
        n += 1
        if n % 500000 == 0:
            print(f"Scan {n} objects, in-box nodes {len(in_ids)}")
        if isinstance(entity, Node):
            if isinbounds(use, entity.lat, entity.lon):
                in_ids.add(entity.id)
        elif isinstance(entity, Way):
            refs = entity.nodes
            if refs and any(nid in in_ids for nid in refs):
                keep_ways.add(entity.id)
                needed.update(refs)
        elif isinstance(entity, Relation):
            keep = False
            for member in entity.members:
                if member.type is Way and member.member_id in keep_ways:
                    keep = True
                    break
                if member.type is Node and member.member_id in in_ids:
                    keep = True
                    break
            if keep:
                keep_rels.add(entity.id)
    needed |= in_ids
    print(f"Keep {len(needed)} nodes / {len(keep_ways)} ways / {len(keep_rels)} relations")

    nodes = {}
    ways = {}
    relations = {}
    n = 0
    for entity in parse_file(filename):
        n += 1
        if n % 500000 == 0:
            print(f"Load {n} objects, kept nodes {len(nodes)}")
        if isinstance(entity, Node):
            if entity.id not in needed:
                continue
            if not isinbounds(use, entity.lat, entity.lon):
                entity.tags["outofbounds"] = True
            nodes[entity.id] = entity
        elif isinstance(entity, Way):
            if entity.id in keep_ways:
                ways[entity.id] = entity
        elif isinstance(entity, Relation):
            if entity.id in keep_rels:
                relations[entity.id] = entity
    print(f"Loaded {len(nodes)} Nodes / {len(ways)} Ways / {len(relations)} Relations")
    return nodes, ways, relations


def read_building_ways(filename, bounds=None):
    """Two-pass parse: closed building ways in the box, then only the nodes they reference."""
    print(f"Read building footprints from '{filename}' ...")
    use = _resolve_bounds(filename, bounds)
    assert str(filename).lower().endswith((".osm", ".pbf", ".xml", ".bz2", ".gz")), "File type needs to be .osm / .osm.bz2 / .pbf"
    cropped = _already_cropped(filename, use)
    if cropped:
        print("Building parse: file already cropped; skip in-box node scan")

    in_ids = set()
    if not cropped:
        for entity in parse_file(filename):
            if isinstance(entity, Node) and isinbounds(use, entity.lat, entity.lon):
                in_ids.add(entity.id)

    ways = {}
    needed = set()
    for entity in parse_file(filename):
        if not isinstance(entity, Way):
            continue
        b = entity.tags.get("building")
        if not b or b == "no":
            continue
        wnodes = entity.nodes
        if len(wnodes) < 4 or wnodes[0] != wnodes[-1]:
            continue
        if not cropped and not any(nid in in_ids for nid in wnodes):
            continue
        ways[entity.id] = entity
        needed.update(wnodes)
        if len(ways) % 25000 == 0:
            print(f"Building ways so far: {len(ways)}")
    print(f"Building ways: {len(ways)} / nodes needed: {len(needed)}")

    nodes = {}
    scanned = 0
    for entity in parse_file(filename):
        if not isinstance(entity, Node):
            continue
        scanned += 1
        if scanned % 500000 == 0:
            print(f"Scanned {scanned} nodes, kept {len(nodes)}")
        if entity.id not in needed:
            continue
        if not isinbounds(use, entity.lat, entity.lon):
            entity.tags["outofbounds"] = True
        nodes[entity.id] = entity
    print(f"Loaded {len(nodes)} building nodes / {len(ways)} ways")
    return nodes, ways
