import os, sys
import luadata
from datetime import datetime

import read_osm
import convert_data
import optimize_edges
import sort_edges
from lua_remove_nil import lua_remove_nil

#################################################

# redirect log to file; comment out to write in console
sys.stdout = open('log.txt', 'w', encoding='utf-8')
sys.stderr = sys.stdout

print("#" * 16 + "  OSM-TPF2 CONVERTER  " + "#" * 16)
print("Startup:", datetime.now())
start = datetime.now()

# assert len(sys.argv) == 5, "Expect 4 Arguments when using the exe"

#################################################

# set Input and Output file
INFILE = "map.osm"
if len(sys.argv) > 1:
    INFILE = sys.argv[1]
OUTFILE = "osmdata.lua"
if len(sys.argv) > 2:
    OUTFILE = sys.argv[2]

# define Map Bounds
bounds_length = (24576, 24576)  # tpf2 map size
if len(sys.argv) > 3:
    bounds_length = tuple(map(int, sys.argv[3].split(',')))
    assert len(bounds_length) == 2
bounds = {  # set bounds manually
    "minlat": 49.9829, "minlon": 8.48095,
    "maxlat": 50.2037, "maxlon": 8.8260,
}
# bounds = read_osm.read_bounds(INFILE)  # use bounds of osm file
if len(sys.argv) > 4:
    coords = map(float, sys.argv[4].split(','))
    bounds = dict((key, c) for key, c in zip(["minlat", "minlon", "maxlat", "maxlon"], coords))
print("Map Bounds defined:", bounds)

#################################################

# 1. Parse osm xml data and put in dicts
print("=" * 16 + " Parse OSM XML data " + "=" * 16)
nodes, ways, relations = read_osm.read(INFILE)

# 2. Convert osm data to relevant data for TPF2
print("=" * 16 + " Convert/Transform data " + "=" * 16)
data = convert_data.convert(nodes, ways, relations, bounds, bounds_length)

# 3. Do optimizations for edges (shorting, curving)
print("=" * 16 + " Optimize Edges/geometry " + "=" * 16)
optimize_edges.optimize(data)

# 4. Sort edges by (street)type, so more important streets get built first
print("=" * 16 + " Sort Edges " + "=" * 16)
data["edges"] = sort_edges.sort(data["edges"])

# 5. remove nil values, makes file shorter
data = lua_remove_nil(data)

#################################################

print("=" * 16 + " Write Lua file " + "=" * 16)
luadata.write(OUTFILE, data, indent="\t")
print(f"Successfully converted OSM data to: '{OUTFILE}'")
print("\n  ".join([f"Data contains:",
                   f"Towns: {len(data['towns'])}",
                   f"Nodes: {len(data['nodes'])}",
                   f"Edges: {len(data['edges'])}",
                   f"Areas: {sum(len(area) for area in data['areas'].values())}",
                   f"Objects: {len(data['objects'])}"
                   ]))
print(f"Execution time: {datetime.now() - start} s")
