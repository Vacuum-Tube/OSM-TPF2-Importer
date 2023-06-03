from pyproj import Transformer
from geopy import distance as gd


class Coord2metric:

    def __init__(self, bounds, length):
        distlat = gd.geodesic((bounds["minlat"], bounds["minlon"]), (bounds["maxlat"], bounds["minlon"])).m
        distlon1 = gd.geodesic((bounds["minlat"], bounds["minlon"]), (bounds["minlat"], bounds["maxlon"])).m
        distlon2 = gd.geodesic((bounds["maxlat"], bounds["minlon"]), (bounds["maxlat"], bounds["maxlon"])).m
        print(f"Distance of bounds: lon={distlon1:.0f}-{distlon2:.0f}m , lat={distlat:.0f}m")
        self.latlon2mercator = Transformer.from_crs("epsg:4326", "epsg:3857").transform
        bl = self.latlon2mercator(bounds["minlat"], bounds["minlon"])
        tr = self.latlon2mercator(bounds["maxlat"], bounds["maxlon"])
        self.length_x = length[0]  # map size in m for correct scaling
        self.length_y = length[1]
        self.center_x = (tr[0] + bl[0]) / 2
        self.center_y = (tr[1] + bl[1]) / 2
        self.dist_x = tr[0] - bl[0]
        self.dist_y = tr[1] - bl[1]

    def latlon2metricoffset(self, lat, lon):
        x, y = self.latlon2mercator(lat, lon)
        return ((x - self.center_x) / self.dist_x * self.length_x,
                (y - self.center_y) / self.dist_y * self.length_y)
