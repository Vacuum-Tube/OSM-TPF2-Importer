# Install Osmosis (optional)

Download [Osmosis](https://wiki.openstreetmap.org/wiki/Osmosis) and put it here (replace folder). Version 0.48.3 can be
downloaded [here](https://github.com/openstreetmap/osmosis/releases/download/0.48.3/osmosis-0.48.3.zip). Since it is
based on Java, you need to have Java installed.

You need Osmosis when you have a OSM file that has more data than the bounds from your map area. You may want to crop it
to your area, otherwise files get very big and osm_importer might build things outside your map. This tool also converts
.pbf to .osm (xml).

If you have a specific OSM file that is already cropped to your area (e.g. from web export), you don't need this step.
However, some sites e.g. by [GeoFabrik](https://download.geofabrik.de/) provide predefined OSM files from certain areas.
This creates the possibility to use data from a past point in
time ([not possible via OSM api](https://wiki.openstreetmap.org/wiki/History_API_and_Database)).

You can run it with [crop_osm.py](../crop_osm.py)