# sorting order, edges will be build in this order by type

railtypes = [  # https://wiki.openstreetmap.org/wiki/Key:railway
    "rail",
    "light_rail",
    "subway",
    "tram",
    "narrow_gauge",
    "miniature",
    "preserved",
    "disused",
    "construction",
]

highwaytypes = [  # https://wiki.openstreetmap.org/wiki/Key:highway
    "aeroway",
    # actual streets
    "raceway",
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
    "primary",
    "primary_link",
    "secondary",
    "secondary_link",
    "tertiary",
    "tertiary_link",
    "residential",
    "living_street",
    "unclassified",
    "service",
    "construction",
    # paths
    "pedestrian",
    "footway",
    "cycleway",
    "path",
    "track",
    "bridleway",
    # streams
    "waterstream",
]
# move types to ignoredtypes to omit them from the output data

ignored_highway_types = {
    # place ignored types here:

    # highway types from OSM, which are not actual streets
    "steps",
    "platform",
    "corridor",
    "bus_stop",
    "escape",
    "busway",
    "bus_guideway",
    "road",
    "via_ferrata",
    "elevator",
    "emergency_bay",
    "rest_area",
    "services",
    "razed",
    "abandoned",
    "disused",
    "proposed",
    "planned",
}


def sort(edges):
    ret = []  # convert edges from dict to a sorted list
    tracks = dict((rtype, []) for rtype in railtypes)
    streets = dict((htype, []) for htype in highwaytypes)
    for eid, edge in edges.items():
        edge["id"] = eid
        if edge["track"]:
            rtype = edge["track"]["type"]
            if rtype in tracks:
                tracks[rtype].append(edge)
            else:
                print(f"Unknown rail type: {rtype} {eid}")
        else:
            htype = edge["street"]["type"]
            if htype in streets:
                streets[htype].append(edge)
            else:
                if htype not in ignored_highway_types:
                    print(f"Unknown highway type: {htype} {eid}")
    print("\n  ".join([f"Track Edges (rail types): {sum(len(tracks[rtype]) for rtype in railtypes)}",
                       *[f"{rtype}: {len(tracks[rtype])}" for rtype in railtypes]]))
    print("\n  ".join([f"Street Edges (highway types): {sum(len(streets[htype]) for htype in highwaytypes)}",
                       *[f"{htype}: {len(streets[htype])}" for htype in highwaytypes]]))
    for rtype in railtypes:
        ret.extend(tracks[rtype])
    for htype in highwaytypes:
        ret.extend(streets[htype])
    return ret
