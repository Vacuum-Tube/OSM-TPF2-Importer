import os
import subprocess
import xml.etree.ElementTree as Xmlt
from osmread import parse_file, Node, Way, Relation

osmosis_path = "osmosis\\bin\\osmosis"  # sry unix, please adjust...


def crop_bounds(filename, bounds):
    path = os.path.dirname(filename)
    file = os.path.basename(filename)
    extension = os.path.splitext(file)[-1]
    if extension == ".pbf":
        read_comm = '--read-pbf'
    elif extension == ".osm":
        read_comm = '--read-xml'
    elif extension == ".bz2":
        read_comm = '--read-xml'
    else:
        assert 0, "Unknown OSM File Extension: " + extension
    filename_new = filename + '_crop.osm'
    print(f"Extracting bounding box area from '{filename}' via osmosis ...")
    complprocess = subprocess.run([osmosis_path, read_comm, f"file={filename}", '--bounding-box',
                                   f"top={bounds['maxlat']}", f"left={bounds['minlon']}", f"bottom={bounds['minlat']}",
                                   f"right={bounds['maxlon']}", "completeWays=yes", "completeRelations=no",
                                   '--write-xml', filename_new], shell=True)
    complprocess.check_returncode()
    print(f"Saved to '{filename_new}'")
    return filename_new


def isinbounds(bounds, lat, lon):
    return bounds['minlat'] <= lat <= bounds['maxlat'] and bounds['minlon'] <= lon <= bounds['maxlon']


def read_bounds(filename):  # read bounds info from osm/xml file
    tree = Xmlt.parse(filename)
    root = tree.getroot()
    if root[0].tag == "bounds":  # from osm main api
        boundstag = root[0]
    else:  # from Overpass
        assert root[0].tag == "note"
        assert root[2].tag == "bounds"
        boundstag = root[2]
    bounds = dict((k, float(v)) for k, v in boundstag.attrib.items())
    return bounds


def read(filename, bounds=None):
    print(f"Read osm data from '{filename}' ...")
    assert filename.endswith(".osm") or filename.endswith(".pbf"), "File type needs to be .osm or .pbf"
    nodes = {}
    ways = {}
    relations = {}
    for entity in parse_file(filename):
        if isinstance(entity, Node):
            # if bounds is None or isinbounds(bounds, entity.lat, entity.lon):  # not working, leads to missing node reference in ways + relations
            nodes[entity.id] = entity
        elif isinstance(entity, Way):
            ways[entity.id] = entity
        elif isinstance(entity, Relation):
            relations[entity.id] = entity
    print(f"Loaded {len(nodes)} Nodes and {len(ways)} Ways and {len(relations)} Relations")
    return nodes, ways, relations
