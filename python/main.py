import os
import sys
import luadata
import read_osm
import convert_data
import optimize_edges
import sort_edges
from lua_remove_nil import lua_remove_nil

# USE THIS to redirect output to file
log_file = 'output.txt'
sys.stdout = open(log_file, 'w')


def open_in_osm(lat, lon):
    # os.startfile(f"https://www.openstreetmap.org/#map=16/{lat}/{lon}")
    os.startfile(f"https://www.openstreetmap.org/note/new?lat={lat}&lon={lon}#map=16/{lat}/{lon}")


INFILE = "map5.osm"
# INFILE = "map-frankfurt20230409.osm"
# INFILE = "mapbounds_test.osm"
OUTFILE = "osmdata.lua"

# 1. Parse osm xml data and put to dicts
nodes, ways, relations, bounds = read_osm.read(INFILE)
bounds = {  # set bounds manually, otherwise bounds of .osm file are used
    "minlat": 49.9829, "minlon": 8.48095,
    "maxlat": 50.2037, "maxlon": 8.8260,
}
# open_in_osm(bounds["minlat"],bounds["minlon"])
# open_in_osm(bounds["maxlat"],bounds["minlon"])
# open_in_osm(bounds["minlat"],bounds["maxlon"])
# open_in_osm(bounds["maxlat"],bounds["maxlon"])
print("Bounds:", bounds)
bounds_length = (4096 * 6, 4096 * 6)  # meglomaniac map: 6

# 2. Convert osm data to relevant data for TPF2
data = convert_data.convert(nodes, ways, relations, bounds, bounds_length)

# 3. Make some optimizations for edges (shorting, curving)
optimize_edges.optimize(data)

# 4. Sort edges by (street)type, so more important streets get built first
data["edges"] = sort_edges.sort(data["edges"])

# 5. remove nil values, makes file shorter
data = lua_remove_nil(data)

luadata.write(OUTFILE, data, indent="\t")
print(f"Successfully converted OSM data to: '{OUTFILE}'")
print("\n  ".join([f"Data contains:",
                   f"Towns: {len(data['towns'])}",
                   f"Nodes: {len(data['nodes'])}",
                   f"Edges: {len(data['edges'])}",
                   f"Areas: {sum(len(area) for area in data['areas'].values())}",
                   f"Objects: {len(data['objects'])}"
                   ]))
