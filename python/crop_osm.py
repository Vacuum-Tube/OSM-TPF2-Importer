import read_osm

# Use this to crop the bounds via osmosis tool from a larger OSM data file
# you need to place osmosis in this folder and install java (and for unix adjust path separator in read_osm.py)
# more info in osmosis/README

# due to an issue with osmread package, you may need to comment out the line with _changeset in osmread/parser/xml.py (if you don't use my environment)

bounds = {
    "minlat": 49.9829, "minlon": 8.48095,
    "maxlat": 50.2037, "maxlon": 8.8260,
}
INFILE = "hessen-220101.osm.pbf"

read_osm.crop_bounds(INFILE, bounds)
# will create a file INFILE + '_crop.osm'
