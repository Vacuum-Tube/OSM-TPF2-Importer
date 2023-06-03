# https://wiki.openstreetmap.org/wiki/Highways

highwaytypes = [  # sorting order
    "aeroway",
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
    "pedestrian",
    "footway",
    "cycleway",
    "path",
    "track",
    "bridleway",
    "waterstream",
]
# move highway types to ignoredtypes to skip them from the output data
ignoredtypes = [
    "steps",
    "platform",
]


def sort(edges):
    ret = []  # convert edges from dict to a sorted list
    streets = dict((htype, []) for htype in highwaytypes)
    for eid, edge in edges.items():
        edge["id"] = eid
        if edge["track"]:
            ret.append(edge)
        else:
            htype = edge["street"]["type"]
            if htype in streets:
                streets[htype].append(edge)
            else:
                if htype not in ignoredtypes:
                    print(f"Unknown highway type: {htype} {eid}")
    print("Track Edges: ", len(ret))
    print(
        "\n  ".join([f"Street Edges (highway types):", *[f"{htype}: {len(streets[htype])}" for htype in highwaytypes]]))
    for htype in highwaytypes:
        ret.extend(streets[htype])
    return ret
