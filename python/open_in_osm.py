import os


# use this (preferably in a console) to see the exact location of the bound coordinates in a OSM map

def open_in_osm(lat, lon):
    # os.startfile(f"https://www.openstreetmap.org/#map=16/{lat}/{lon}")
    os.startfile(f"https://www.openstreetmap.org/note/new?lat={lat}&lon={lon}#map=16/{lat}/{lon}")


open_in_osm(bounds["minlat"], bounds["minlon"])
open_in_osm(bounds["maxlat"], bounds["minlon"])
open_in_osm(bounds["minlat"], bounds["maxlon"])
open_in_osm(bounds["maxlat"], bounds["maxlon"])
