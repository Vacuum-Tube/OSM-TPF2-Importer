# Install Osmosis

You need [Osmosis](https://wiki.openstreetmap.org/wiki/Osmosis) when you have a OSM file that has more data than the bounds from your map area. 
You may want to crop it to your area, otherwise files get very big and OSM Importer might build things outside your map. 
The tool can also convert .pbf to .osm (xml).

If you have a dedicated OSM file that is already cropped to your area (e.g. via web export), you don't need this step.
However, some sites e.g. by [GeoFabrik](https://download.geofabrik.de/) provide predefined OSM files from certain areas.
This creates the possibility to use data from a past point in time ([not possible via OSM api](https://wiki.openstreetmap.org/wiki/History_API_and_Database)).

Download [Osmosis](https://wiki.openstreetmap.org/wiki/Osmosis) and insert it here. 
Version 0.48.3 can be downloaded [here](https://github.com/openstreetmap/osmosis/releases/download/0.48.3/osmosis-0.48.3.zip). 
Since it is based on Java, you need to have Java installed.

You can run Osmosis with the help of [crop_osm.py](../crop_osm.py) to perform the cropping.