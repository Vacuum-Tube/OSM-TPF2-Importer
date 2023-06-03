import subprocess

from osmread import parse_file, Node, Way, Relation
import os
import xml.etree.ElementTree as xmlt

osmosis_path = ""


def filter_osmosis(self, path_to_osm_file: str, bounding_box):  # unused
    top = bounding_box[0]
    left = bounding_box[1]
    bottom = bounding_box[2]
    right = bounding_box[3]

    path = os.path.dirname(path_to_osm_file)
    file = os.path.basename(path_to_osm_file)
    # raw_filename = os.path.splitext(os.path.splitext(file)[0])[0]  # currently assuming 2 extensions
    extension = os.path.splitext(file)[-1]
    if extension == ".pbf":
        read_comm = '--read-pbf'
    elif extension == ".osm":
        read_comm = '--read-xml'
    elif extension == ".bz2":
        read_comm = '--read-xml'
    else:
        assert 0, "Unknown OSM File Extension: " + extension
    extracted_filename = os.path.join(path, '_filtered')
    print("Extracting bounding box area from *.osm file. This may take a while ...")
    complprocess = subprocess.run([osmosis_path, read_comm,  # 'enableDateParsing=no',
                                   'file={}'.format(path_to_osm_file),
                                   '--bounding-box', 'top={}'.format(str(top)), 'left={}'.format(str(left)),
                                   'bottom={}'.format(str(bottom)), 'right={}'.format(str(right)),
                                   '--write-xml', extracted_filename], shell=True)
    complprocess.check_returncode()


def isinbounds(bounds, lat, lon):
    return bounds['minlat'] <= lat <= bounds['maxlat'] and bounds['minlon'] <= lon <= bounds['maxlon']


def read(filename, skip_outliers=False):  # leads to missing node reference in ways/relations, not supported yet
    print(f"Read osm data from '{filename}' ...")

    tree = xmlt.parse(filename)
    root = tree.getroot()
    if root[0].tag == "bounds":  # from osm main api
        boundstag = root[0]
    else:  # from OVerpass
        assert root[0].tag == "note"
        assert root[2].tag == "bounds"
        boundstag = root[2]
    bounds = dict((k, float(v)) for k, v in boundstag.attrib.items())

    nodes = {}
    ways = {}
    relations = {}
    for entity in parse_file(filename):
        tags = entity.tags
        if isinstance(entity, Node):
            if not skip_outliers or isinbounds(bounds, entity.lat, entity.lon):
                nodes[entity.id] = entity
        elif isinstance(entity, Way):
            ways[entity.id] = entity
        elif isinstance(entity, Relation):
            relations[entity.id] = entity

    print(f"Loaded {len(nodes)} Nodes and {len(ways)} Ways and {len(relations)} Relations")
    return nodes, ways, relations, bounds
