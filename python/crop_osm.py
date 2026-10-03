"""Optional OSM crop helper.

Studio Convert crops extracts without osmosis. This CLI still uses osmosis
if you have it; otherwise print how to crop from OSM-TPF2 Studio.
"""
import sys

import read_osm

# python crop_osm.py infile.osm minlat,minlon,maxlat,maxlon
if len(sys.argv) < 3:
    print("Usage: python crop_osm.py <file.osm|.osm.bz2|.pbf> minlat,minlon,maxlat,maxlon")
    print("Prefer OSM-TPF2 Studio: Crop to yellow box (no osmosis).")
    sys.exit(1)

infile = sys.argv[1]
coords = [float(x) for x in sys.argv[2].split(",")]
if len(coords) != 4:
    print("Bounds must be minlat,minlon,maxlat,maxlon")
    sys.exit(1)
bounds = dict(zip(["minlat", "minlon", "maxlat", "maxlon"], coords))
try:
    read_osm.crop_bounds(infile, bounds)
except FileNotFoundError:
    print("osmosis is not installed. Use OSM-TPF2 Studio → Crop to yellow box instead.")
    sys.exit(1)
except Exception as exc:
    print(exc)
    print("Studio Convert crops country extracts to the yellow box without osmosis.")
    sys.exit(1)
