from coord2metric import Coord2metric
from osmread import Node, Way, Relation

from sort_edges import ignored_highway_types, highwaytypes


def tointornil(str, fallback=None):
    if str and str.isdigit():
        return int(str)
    else:
        return fallback


def trueornil(bool):
    return bool or None


def funcornil(elem, func):
    if elem is not None:
        return func(elem)
    else:
        return None


def convert(nodes, ways, relations, map_bounds, bounds_length):
    data = {
        "towns": {},
        "nodes": {},
        "edges": {},
        "areas": {
            "forests": [],
            "shrubs": [],
            "grounds": [],
        },
        "objects": [],
    }

    places = dict((place, []) for place in ["municipality", "city", "town", "village", "suburb", "quarter",
                                            "neighbourhood", "square"])

    def add_object(type, pos):
        data["objects"].append({
            "type": type,
            "pos": pos,
        })

    transf = Coord2metric(map_bounds, bounds_length).latlon2metricoffset

    for id, node in nodes.items():
        tags = node.tags
        pos = list(transf(node.lat, node.lon))
        data["nodes"][id] = {
            "pos": pos,
            "way_start_to": [],
            "way_end_from": [],
            "way_within": [],
            "outofbounds": tags.get("outofbounds"),
            # "railway": tags.get("railway"),
            "switch": trueornil(tags.get("railway") == "switch"),
            # https://wiki.openstreetmap.org/wiki/Tag:railway%3Dsignal#How_Signal_Tagging_works_by_principle
            "signal": tags.get("railway") == "signal" and {
                "ref": tags.get("ref"),
                "track_position": tags.get("railway:position"),  # Strecken km
                "direction_backward": trueornil(tags.get("railway:signal:direction") == "backward"),
                "position_left": trueornil((tags.get("railway:signal:position") == "left") != (
                    # left/right/bridge/overhead/in_track
                        tags.get("railway:signal:direction") == "backward")),
                # XOR, in OSM left is interpreted from the original direction, in TPF from the signal dircetion
                "combined": tags.get("railway:signal:combined"),
                "combined_function": tags.get("railway:signal:combined:function"),  # exit/entry/intermediate/block
                "main": tags.get("railway:signal:main"),
                "main_function": tags.get("railway:signal:main:function"),  # exit/entry/intermediate/block
                "main_form": tags.get("railway:signal:main:form"),  # sign/light/semaphore
                "distant": tags.get("railway:signal:distant"),
                "distant_form": tags.get("railway:signal:distant:form"),  # sign/light/semaphore
                "distant_repeated": trueornil(tags.get("railway:signal:distant:repeated") == "yes"),
                "distant_shortened": trueornil(tags.get("railway:signal:distant:shortened") == "yes"),
                "speedlimit": tags.get("railway:signal:speed_limit"),
                "speedlimit_form": tags.get("railway:signal:speed_limit:form"),  # sign/light
                "speedlimit_speed": tags.get("railway:signal:speed_limit:speed"),
                "speedlimit_speed_int": tointornil(funcornil(tags.get("railway:signal:speed_limit:speed"),
                                                             lambda x: x.split(";")[0])),
                "speedlimitdistant": tags.get("railway:signal:speed_limit_distant"),
                "speedlimitdistant_form": tags.get("railway:signal:speed_limit_distant:form"),  # sign/light
                "speedlimitdistant_speed": tags.get("railway:signal:speed_limit_distant:speed"),
                "speedlimitdistant_speed_int": tointornil(
                    funcornil(tags.get("railway:signal:speed_limit_distant:speed"),
                              lambda x: x.split(";")[0])),
                "crossing": tags.get("railway:signal:crossing"),
                "crossingdistant": tags.get("railway:signal:crossing_distant"),
                "minor": tags.get("railway:signal:minor"),
                "minor_dwarf": trueornil(tags.get("railway:signal:minor:height") == "dwarf"),
                "stop": tags.get("railway:signal:stop"),
                "route": tags.get("railway:signal:route"),
                "route_states": tags.get("railway:signal:route:states"),
                "routedistant": tags.get("railway:signal:route_distant"),
                "routedistant_states": tags.get("railway:signal:route_distant:states"),
                "wrongtrack": tags.get("railway:signal:wrong_road"),
                "departure": tags.get("railway:signal:departure"),
                "whistle": tags.get("railway:signal:whistle"),
            } or None,
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
                if tags["place"] not in places:
                    places[tags["place"]] = []
                places[tags["place"]].append({
                    "name": tags["name"],
                    "pos": pos,
                })
            # else:
            # print(node.tags["place"], id, "no name!")

    print("Places found:")
    for place, nodes in places.items():
        print(place + ":", len(nodes))
        # if place != "locality":
        for node in nodes:
            print("\t" + node["name"])

    # https://wiki.openstreetmap.org/wiki/Key:place
    data["towns"] = [
        # *places["city"],
        *places["town"],
        *places["village"],
        *places["suburb"],
        *places["quarter"],
        *places["neighbourhood"],
        # *places["square"],
    ]

    poly_areas_added = set()  # some forests are mapped twice, as way and relation
    groundtags_landuse = {"residential", "commercial", "industrial", "retail", "construction", "education",
                          "brownfield", "quarry", "railway", "meadow", "orchard", "allotments",
                          "farmland", "farmyard", "vineyard", "animal_keeping", "flowerbed"}
    groundtags_natural = {"beach", "grassland", "heath", "mud", "shingle"}  # "water"
    groundtags_surface = {"paved", "asphalt", "concrete", "concrete:plates", "paving_stones", "cobblestone", "grass",
                          "grass_paver", "sett", "unhewn_cobblestone", "bricks", "unpaved", "compacted", "woodchips",
                          "fine_gravel", "gravel", "rock", "pebblestone", "ground", "dirt", "earth", "mud", "sand"}

    def add_polygon(way, id, area_type, **addtags):
        if len(way.nodes) > 3:
            dic = {"polygon": list(way.nodes)}  # tuples not work with Lua export
            dic.update(addtags)
            data["areas"][area_type].append(dic)
            poly_areas_added.add(id)

    for id, way in ways.items():
        tags = way.tags
        wnodes = way.nodes

        isstreet = False
        if "highway" in tags:
            if tags["highway"] in highwaytypes:
                isstreet = True
            else:
                if tags["highway"] not in ignored_highway_types:
                    print(f'Unknown highway type: {tags["highway"]} {id}')
        istrack = tags.get("railway") in {"rail", "construction", "disused", "miniature", "narrow_gauge", "preserved",
                                          "light_rail", "subway", "tram"}
        issubway = tags.get("railway") in {"light_rail", "subway"}
        istram = tags.get("railway") in {"tram"} or tags.get("disused:railway") == "tram" or tags.get(
            "disused") == "tram"
        isstream = tags.get("waterway") in {"stream", "river"} and tags.get("tunnel", "no") == "no"
        isaeroway = "aeroway" in tags and tags.get("aeroway") in {"runway", "taxiway"}
        isarea = tags.get("area") == "yes" or "place" in tags  # closed way -> area (not always correctly set)
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
                        "level": tags.get("level"),
                        "country": guess_urban_country(tags),
                        "lit": False if tags.get("lit") == "no" else tags.get("lit"),
                    } or isstream and {
                                  "type": "waterstream",
                                  "waterwaytype": tags.get("waterway"),
                                  "width": tointornil(tags.get("width")),
                                  "boat": False if tags.get("boat") == "no" else tags.get("boat"),
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
                        "lzb": trueornil(tags.get("railway:lzb") == "yes"),
                    } or None,
                    "bridge": False if tags.get("bridge") == "no" else tags.get("bridge"),
                    "tunnel": False if tags.get("tunnel") == "no" else tags.get("tunnel"),
                }

            data["nodes"][wnodes[0]]["way_start_to"].append(wnodes[1])
            data["nodes"][wnodes[-1]]["way_end_from"].append(wnodes[-2])
            for i in range(1, len(wnodes) - 1):
                data["nodes"][wnodes[i]]["way_within"].append([wnodes[i - 1], wnodes[i + 1]])

            if data["nodes"][wnodes[0]]["outofbounds"]:
                data["nodes"][wnodes[0]]["endpoint"] = True
            if data["nodes"][wnodes[-1]]["outofbounds"]:
                data["nodes"][wnodes[-1]]["endpoint"] = True

        # Area (closed way)
        if wnodes[0] == wnodes[-1]:
            if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
                add_polygon(way, id, "forests", leaf_type=tags.get("leaf_type"))
            elif tags.get("natural") == "scrub":
                add_polygon(way, id, "shrubs")
            elif tags.get("landuse") in groundtags_landuse:
                add_polygon(way, id, "grounds", surface=tags.get("landuse"))
            elif tags.get("natural") in groundtags_natural:
                add_polygon(way, id, "grounds", surface=tags.get("natural"))
            elif tags.get("natural") == "water" and tags.get("water") in {"lake", "pond", "reservoir", "moat"}:
                add_polygon(way, id, "grounds", surface="water")
            elif tags.get("surface") in groundtags_surface and \
                    tags.get("area:highway") != "steps" and "railway" not in tags:
                add_polygon(way, id, "grounds", surface=tags.get("surface"))
            elif tags.get("golf") == "bunker":
                add_polygon(way, id, "grounds", surface="golf_bunker")
            elif tags.get("golf") == "fairway":
                add_polygon(way, id, "grounds", surface="golf_fairway")
            elif tags.get("golf") == "green":
                add_polygon(way, id, "grounds", surface="golf_green")

    def add_multipolygon(relation, area_type, **addtags):
        if relation.tags.get("type") != "multipolygon":
            print(f"Relation {relation.id} not Multi Polygon!")
            return
        mp = {
            "outer": [],
            "inner": [],
        }
        for member in relation.members:
            if member.type == Relation:
                if member.member_id in relations:  # else out of map bounds
                    add_multipolygon(relations[member.member_id], area_type, **addtags)
                    # if sub relation contains (different) tags, it is not considered
            elif member.type == Way:
                if member.member_id in ways:  # else out of map bounds
                    way = ways[member.member_id]
                    if way.nodes[0] != way.nodes[-1]:  # open ways seem to be allowed for MP, this is too complex for me
                        continue
                    if len(way.nodes) > 3 and (
                            member.role == "outer" and way.id not in poly_areas_added or member.role == "inner"):
                        mp[member.role].append(list(way.nodes))
                        if member.role == "outer":
                            poly_areas_added.add(way.id)
                    # else:
                    # print(f"Way {member.member_id} from Rel {relation.id} already in data.areas")
        if len(mp["outer"]) > 0:
            dic = {"multipolygon": mp}
            dic.update(addtags)
            data["areas"][area_type].append(dic)

    for id, relation in relations.items():
        tags = relation.tags
        if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
            add_multipolygon(relation, "forests", leaf_type=tags.get("leaf_type"))
        elif tags.get("natural") == "scrub":
            add_multipolygon(relation, "shrubs")
        elif tags.get("landuse") in groundtags_landuse:
            add_multipolygon(relation, "grounds", surface=tags.get("landuse"))
        elif tags.get("natural") in groundtags_natural:
            add_multipolygon(relation, "grounds", surface=tags.get("natural"))
        elif tags.get("natural") == "water" and tags.get("water") in {"lake", "pond", "reservoir", "moat"}:
            add_multipolygon(relation, "grounds", surface="water")
        elif tags.get("surface") in groundtags_surface and \
                tags.get("area:highway") != "steps" and "railway" not in tags:
            add_multipolygon(relation, "grounds", surface=tags.get("surface"), leisure=tags.get("leisure"))

    return data


def guess_urban_country(tags):
    if "rural" in tags.get("zone:traffic", ""):
        return True
    if "urban" in tags.get("zone:traffic", ""):
        return False
    if tags.get("lit") == "yes":
        return False
    if "urban" in tags.get("source:maxspeed", ""):
        return False
    return None
