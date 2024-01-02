import os, sys
import luadata

import read_osm
import convert_data
import optimize_edges
import sort_edges
from lua_remove_nil import lua_remove_nil

# redirect log to file; comment out to write in console
# log_file = 'log.txt'
# sys.stdout = open(log_file, 'w')

#################################################

# set Input and Output file
# INFILE = "map7.osm"
# INFILE = "map-frankfurt20230409.osm"
INFILE = "hessen-220101.osm.pbf_crop.osm"
OUTFILE = "osmdata.lua"

# define Map Bounds
bounds_length = (24576, 24576)  # tpf2 map size
bounds = {  # set bounds manually
    "minlat": 49.9829, "minlon": 8.48095,
    "maxlat": 50.2037, "maxlon": 8.8260,
}
# bounds = read_osm.read_bounds(INFILE)  # use bounds of osm file
print("Bounds:", bounds)

#################################################

# 1. Parse osm xml data and put in dicts
nodes, ways, relations = read_osm.read(INFILE)

# 2. Convert osm data to relevant data for TPF2
data = convert_data.convert(nodes, ways, relations, bounds, bounds_length)

# 3. Do optimizations for edges (shorting, curving)
optimize_edges.optimize(data)

# 4. Sort edges by (street)type, so more important streets get built first
data["edges"] = sort_edges.sort(data["edges"])

# 5. remove nil values, makes file shorter
data = lua_remove_nil(data)

#################################################

# write to output
luadata.write(OUTFILE, data, indent="\t")
print(f"Successfully converted OSM data to: '{OUTFILE}'")
print("\n  ".join([f"Data contains:",
                   f"Towns: {len(data['towns'])}",
                   f"Nodes: {len(data['nodes'])}",
                   f"Edges: {len(data['edges'])}",
                   f"Areas: {sum(len(area) for area in data['areas'].values())}",
                   f"Objects: {len(data['objects'])}"
                   ]))
