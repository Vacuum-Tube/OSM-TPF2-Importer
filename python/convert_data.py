from coord2metric import Coord2metric
from osmread import Node, Way, Relation

ignored_highway_types = {  # highway types from OSM, which are not actual streets
    "proposed",
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
}


def tointornil(str, fallback=None):
    if str and str.isdigit():
        return int(str)
    else:
        return fallback


def convert(nodes, ways, relations, map_bounds, bounds_length):
    data = {
        "towns": {},
        "nodes": {},
        "edges": {},
        "areas": {
            "forests": [],
            "shrubs": [],
        },
        "objects": [],
    }

    places = {
        "state": [],
        "province": [],
        "region": [],
        "county": [],
        "district": [],
        "municipality": [],
        "city": [],
        "town": [],
        "village": [],
        "hamlet": [],
        "borough": [],
        "suburb": [],
        "quarter": [],
        "neighbourhood": [],
        "square": [],
        "isolated_dwelling": [],
        "locality": [],
        "plot": [],
        "farm": [],
        "field": [],
        "island": [],
    }

    c = Coord2metric(map_bounds, bounds_length)
    transf = c.latlon2metricoffset

    def add_object(type, pos):
        data["objects"].append({
            "type": type,
            "pos": pos,
        })

    for id, node in nodes.items():
        tags = node.tags
        pos = list(transf(node.lat, node.lon))
        data["nodes"][id] = {
            "pos": pos,
            # "railway": tags.get("railway"),
            "switch": tags.get("railway") == "switch" or None,
        }

        if tags.get("natural") == "tree":
            add_object("tree", pos)
        if tags.get("amenity") == "fountain":
            add_object("fountain", pos)
        if tags.get("barrier") == "bollard":
            add_object("bollard", pos)
        if tags.get("advertising") == "column":
            add_object("litfass", pos)

        if "place" in tags:
            if "name" in tags:
                places[tags["place"]].append({
                    "name": tags["name"],
                    "pos": pos,
                })
            else:
                print(node.tags["place"], id, "no name!")

    print("Places found:")
    for place, nodes in places.items():
        print(place + ":", len(nodes))
        # if place != "locality":
        for node in nodes:
            print("\t" + node["name"])

    data["towns"] = [
        # *places["city"],
        *places["town"],
        *places["village"],
        *places["suburb"],
        *places["quarter"],
        *places["neighbourhood"],
        # *places["square"],
    ]

    forests_added = set()  # some forests are mapped twice as edge and relation

    for id, way in ways.items():
        tags = way.tags
        wnodes = way.nodes

        isstreet = "highway" in tags and tags["highway"] not in ignored_highway_types
        istram = tags.get("railway") in {"tram"} or tags.get("disused:railway") == "tram" or tags.get(
            "disused") == "tram"
        issubway = tags.get("railway") in {"light_rail", "subway"}
        istrack = tags.get("railway") in {"rail", "construction", "disused", "miniature", "narrow_gauge", "preserved"} \
                  or istram or issubway
        isstream = tags.get("waterway") == "stream" and tags.get("tunnel") is None
        isaeroway = "aeroway" in tags and tags.get("aeroway") in {"runway", "taxiway"}
        isarea = tags.get("area") == "yes"  # closed way -> area (not always correctly set)
        isfloating = tags.get("floating") == "yes"
        if (isstreet and istrack):
            print("Warning: Way is street AND track", id)
            istrack = False

        if (istrack or isstreet or isstream or isaeroway) and not isarea and not isfloating:
            speed = tointornil(tags.get("maxspeed"))
            if not speed:
                mxspds = list(filter(None, [
                    tointornil(tags.get("maxspeed:backward")), tointornil(tags.get("maxspeed:forward"))]))
                speed = min(mxspds) if mxspds else None
            if istrack and speed is None:
                print(f"Track {id} no speed")
            if istrack and tointornil(tags.get("gauge")) is None:
                print(f"Track {id} no gauge")

            for i in range(len(wnodes) - 1):
                if wnodes[i] not in data["nodes"] or wnodes[i + 1] not in data["nodes"]:
                    # print(f"Out of bounds: Skip Edge({wnodes[i]},{wnodes[i + 1]})")
                    # continue  # skip edge
                    raise Exception(f"Way{id} - Edge({wnodes[i]},{wnodes[i + 1]}) Node not in data")
                data["edges"][f"{id}_{i}"] = {
                    "node0": wnodes[i],
                    "node1": wnodes[i + 1],
                    "street": isstreet and {
                        "speed": speed,
                        "type": tags["highway"],
                        # buslane
                        # tram
                        "surface": tags.get("surface"),
                        "tracktype": tags.get("tracktype"),
                        "lanes": tointornil(tags.get("lanes")),
                        "oneway": tags.get("oneway") == "yes" or tags.get("junction") == "roundabout",
                        "sidewalk": False if (tags.get("sidewalk") in {"no", "none", "separate"} or tags.get(
                            "bicycle") == "use_sidepath") else tags.get(
                            "sidewalk"),
                        "foot": tags.get("foot"),
                        "bicycle": False if tags.get("bicycle") in {"no"} else tags.get("bicycle"),
                        "segregated": False if tags.get("segregated") == "no" else tags.get("segregated"),
                        "width": tointornil(tags.get("width")),
                        "country": ("rural" in tags["zone:traffic"]) if "zone:traffic" in tags else
                        ("urban" not in tags["source:maxspeed"]) if "source:maxspeed" in tags else
                        False if tags.get("lit") == "yes" else None,
                        "lit": False if tags.get("lit") == "no" else tags.get("lit"),
                    } or isstream and {
                                  "type": "waterstream",
                                  "width": tointornil(tags.get("width")),
                              } or isaeroway and {
                                  "type": "aeroway",
                                  "subtype": tags.get("aeroway")
                              } or None,
                    "track": istrack and {
                        "type": tags.get("railway"),
                        "speed": speed,
                        "electrified": False if tags.get("electrified") == "no" else tags.get("electrified"),
                        "gauge": tointornil(tags.get("gauge")),
                        "tram": istram,
                        "subway": issubway,
                        "lzb": (tags.get("railway:lzb") == "yes") or None,
                    } or None,
                    "bridge": False if tags.get("bridge") == "no" else tags.get("bridge"),
                    "tunnel": False if tags.get("tunnel") == "no" else tags.get("tunnel"),
                }

        if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
            data["areas"]["forests"].append({
                "polygon": list(wnodes),  # tuples not work export
                "leaf_type": tags.get("leaf_type"),
            })
            forests_added.add(id)

        if tags.get("natural") == "scrub":
            data["areas"]["shrubs"].append({
                "polygon": list(wnodes),
            })

    def add_multipolygon(relation, area_type):
        tags = relation.tags
        assert relation.id not in forests_added
        forests_added.add(relation.id)
        if tags.get("type") == "multipolygon":
            mp = {
                "outer": [],
                "inner": [],
            }
            for member in relation.members:
                if member.type == Relation:
                    if member.member_id in relations:  # else out of map bounds
                        rel = relations[member.member_id]
                        tags = rel.tags
                        if not (tags.get("landuse") == "forest" or tags.get("natural") == "wood"):
                            # only add here if not otherwise being added by iterating all relations
                            add_multipolygon(rel, area_type)
                elif member.type == Way:
                    if member.member_id in ways:  # else out of map bounds
                        way = ways[member.member_id]
                        if way.id not in forests_added:
                            mp[member.role].append(list(way.nodes))
                        else:
                            print(f"Way {member.member_id} from Rel {relation.id} already in data.areas")
                else:
                    assert False
            if len(mp["outer"]) > 0:
                data["areas"][area_type].append({
                    "multipolygon": mp,
                    "leaf_type": tags.get("leaf_type"),
                })
        else:
            assert False, tags.get("type")

    for id, relation in relations.items():
        tags = relation.tags
        if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
            add_multipolygon(relation, "forests")
        if tags.get("natural") == "scrub":
            add_multipolygon(relation, "shrubs")

    return data
