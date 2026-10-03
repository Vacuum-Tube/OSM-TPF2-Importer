"""Minimal osmread-compatible XML parser (no protobuf / PBF)."""
from __future__ import annotations

import bz2
import gzip
import xml.etree.ElementTree as ET


class Node:
    def __init__(self, id, lat, lon, tags=None):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.tags = tags or {}


class Way:
    def __init__(self, id, nodes=None, tags=None):
        self.id = id
        self.nodes = nodes or []
        self.tags = tags or {}


class Relation:
    def __init__(self, id, members=None, tags=None):
        self.id = id
        self.members = members or []
        self.tags = tags or {}


class RelationMember:
    def __init__(self, type, member_id, role=""):
        self.type = type
        self.member_id = member_id
        self.role = role


_TYPE = {"node": Node, "way": Way, "relation": Relation}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def _open(filename):
    name = str(filename).lower()
    if name.endswith(".pbf") or name.endswith(".osm.pbf"):
        raise RuntimeError("PBF is not supported. Use .osm or .osm.bz2 (Geofabrik), or crop in Studio first.")
    if name.endswith(".bz2"):
        return bz2.open(filename, "rb")
    if name.endswith(".gz"):
        return gzip.open(filename, "rb")
    return open(filename, "rb")


def parse_file(filename):
    stream = _open(filename)
    try:
        context = ET.iterparse(stream, events=("end",))
        for _, elem in context:
            tag = _local(elem.tag)
            if tag == "node":
                tags = {_local_k(c): c.get("v") for c in elem if _local(c.tag) == "tag"}
                yield Node(int(elem.get("id")), float(elem.get("lat")), float(elem.get("lon")), tags)
                elem.clear()
            elif tag == "way":
                tags = {_local_k(c): c.get("v") for c in elem if _local(c.tag) == "tag"}
                nodes = [int(c.get("ref")) for c in elem if _local(c.tag) == "nd"]
                yield Way(int(elem.get("id")), nodes, tags)
                elem.clear()
            elif tag == "relation":
                tags = {_local_k(c): c.get("v") for c in elem if _local(c.tag) == "tag"}
                members = []
                for c in elem:
                    if _local(c.tag) != "member":
                        continue
                    members.append(RelationMember(
                        _TYPE.get(c.get("type"), Way),
                        int(c.get("ref")),
                        c.get("role") or "",
                    ))
                yield Relation(int(elem.get("id")), members, tags)
                elem.clear()
    finally:
        stream.close()


def _local_k(elem) -> str:
    return elem.get("k")
