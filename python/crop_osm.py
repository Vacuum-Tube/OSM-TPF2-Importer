import read_osm

bounds = {
    "minlat": 49.9829, "minlon": 8.48095,
    "maxlat": 50.2037, "maxlon": 8.8260,
}
INFILE = "hessen-220101.osm.pbf"

# USE THIS to crop the bounds via osmosis tool from a larger OSM data file, e.g. GeoFabrik
# you need to place osmosis in this folder and install java (and for unix adjust path separator in read_osm.py)
# due to an issue with osmread package, you need to comment out the line with _changeset in osmread/parser/xml.py (if you don't use my environment)
# more info in osmosis/README

read_osm.crop_bounds(INFILE, bounds)
# will create a file INFILE + '_crop.osm'
