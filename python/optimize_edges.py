import math
import sys
from math import pi
import networkx as nx
import numpy as np

from vec2 import Vec2
from cubic_spline import MyCubicSpline as CubicSpline, approx_length_arc


def optimize(data):
    # 1. Avoid very long edges (can cut through terrain)
    print("=" * 16 + " Split long Edges " + "=" * 16)
    split_long_edges(data["nodes"], data["edges"], 100, etype="street")
    split_long_edges(data["nodes"], data["edges"], 200, etype="track")

    # 2. Create graph and obtain paths
    print("=" * 16 + " Create Graphs " + "=" * 16)
    g, gd = create_graphs(data["nodes"], data["edges"])
    gs = create_sub_graph(g, "STREET")
    gt = create_sub_graph(gd, "TRACK")  # we need a directed graph for the signal direction
    gb = create_bridge_graph(g)
    paths_track = list(get_paths_to_simplify(gt, gt))  # ignore railway crossings, so they dont break paths
    paths_street = list(get_paths_to_simplify(gs, gs))
    paths_bridges = list(get_paths_to_simplify(gb, gb))
    data["paths"] = {
        "track": paths_track,
        "street": paths_street,
        "bridge": paths_bridges,
    }

    # 3. Remove Nodes to improve curve geometry and reduce number of segments
    print("=" * 16 + " Remove Nodes with high curvature " + "=" * 16)
    remove_nodes_curvature(paths_track, g, gt, gs, data["nodes"], data["edges"], 200, maxangle=30)
    remove_nodes_curvature(paths_street, g, gt, gs, data["nodes"], data["edges"], 80, maxangle=30)
    print("=" * 16 + " Remove unnecessary short Edges " + "=" * 16)
    remove_short_unnecessary_edges(paths_track, g, gt, gs, data["nodes"], data["edges"], 100, maxangle=35)
    remove_short_unnecessary_edges(paths_street, g, gt, gs, data["nodes"], data["edges"], 70, maxangle=30)
    print("=" * 16 + " Remove short Edges " + "=" * 16)
    remove_short_edges(paths_track, g, gt, gs, data["nodes"], data["edges"], 10)
    remove_short_edges(paths_street, g, gt, gs, data["nodes"], data["edges"], 1.5)

    # 4. Calculate tangents for curved edge paths
    print("=" * 16 + " Calculate Tangents " + "=" * 16)
    add_curve_tangents(paths_track, g, method="natural", maxangle=45, warnangle=30)
    add_curve_tangents(paths_street, g, method="natural", maxangle=30, warnangle=90)
    add_path_info_to_nodes(paths_track, data["nodes"], "track")
    add_path_info_to_nodes(paths_street, data["nodes"], "street")

    # 5. Add signal information to edges
    print("=" * 16 + " Adjust Signals " + "=" * 16)
    adjust_signals(data["nodes"], g)


def split_long_edges(nodes, edges, max_edge_length, etype=None):
    add_edges = {}  # add later, RuntimeError: dictionary changed size during iteration
    remove_edges = []
    for eid, edge in edges.items():
        if etype and not edge.get(etype):
            continue
        n0 = edge["node0"]
        n1 = edge["node1"]
        p0 = Vec2(nodes[n0]["pos"])
        p1 = Vec2(nodes[n1]["pos"])
        length = (p1 - p0).length()
        if length > max_edge_length:
            print(f"Split Edge({n0},{n1}) is long ({length:.4g})")
            remove_edges.append(eid)
            num_seg = math.ceil(length / max_edge_length)
            lastnode = n0
            for i in range(1, num_seg + 1):
                if i < num_seg:
                    p = p0 + (p1 - p0) * i / num_seg
                    newnode = {"pos": p.toArray(), "added_long": True}
                    newnodekey = f"{eid}_n{i}"
                    assert newnodekey not in nodes
                    nodes[newnodekey] = newnode
                else:
                    newnodekey = n1
                newedge = edge.copy()
                newedge["node0"] = lastnode
                newedge["node1"] = newnodekey
                lastnode = newnodekey
                newedgekey = f"{eid}_{i}"
                assert newedgekey not in edges
                assert newedgekey not in add_edges
                add_edges[newedgekey] = newedge
    edges.update(add_edges)
    for key in remove_edges:
        edges.pop(key)


def remove_short_edges(paths, g, gt, gs, nodes, edges, min_edge_length):
    for path in paths:  # node_ids
        skip_edges = set()
        while len(path) > 2:
            y = [g.nodes[n]["pos"] for n in path]
            lens = [math.inf if (path[i], path[i + 1]) in skip_edges else (y[i + 1] - y[i]).length() for i in
                    range(len(path) - 1)]
            idx = min(range(len(lens)), key=lambda x: lens[x])  # argmin, find shortest edge
            if lens[idx] > min_edge_length:
                break
            if idx == 0:
                succ = True
            elif idx == len(lens) - 1:
                succ = False
            # try to find the better side of the edge to adjust
            elif not is_node_removable(g, gt, gs, path[idx], path[idx - 1], path[idx + 1], exclude_bridges=True):
                succ = True
            elif not is_node_removable(g, gt, gs, path[idx + 1], path[idx], path[idx + 2], exclude_bridges=True):
                succ = False
            elif lens[idx + 1] < lens[idx - 1]:  # remove node at side of shorter edge
                succ = True
            else:
                succ = False
            print(f"Remove Edge({path[idx]},{path[idx + 1]}) is short ({lens[idx]:.4g})")
            # {'after' if succ else 'before'} {idx}")
            if succ:  # replace with successor
                node_rem = path[idx + 1]
                node_keep = path[idx]
                node_correct = path[idx + 2]
            else:  # replace with predecessor
                node_rem = path[idx]
                node_keep = path[idx + 1]
                node_correct = path[idx - 1]
            if is_node_removable(g, gt, gs, node_rem, node_correct, node_keep, exclude_bridges=True, printt=True):
                remove_node(g, nodes, edges, path, node_rem, node_keep, node_correct)
            else:
                skip_edges.add((path[idx], path[idx + 1]))
                # print("Cannot remove", node_rem)


def remove_nodes_curvature(paths, g, gt, gs, nodes, edges, max_edge_length, maxangle=30):
    for path in paths:
        skip_nodes = set(path[i] for i in range(1, len(path) - 1)
                         if not is_node_removable(g, gt, gs, path[i], path[i - 1], path[i + 1]))
        maxk = 1
        while len(path) > 2 and maxk > 0:
            c = get_spline(g, path)
            x, y = c.x, c.y
            ks = [[i, c.maxk_at_node(i)] for i in range(1, len(path) - 1) if path[i] not in skip_nodes]
            if len(ks) == 0:
                break
            while True:
                kidx = max(range(len(ks)), key=lambda j: ks[j][1])  # get node with largest curvature
                (idx, maxk) = ks[kidx]
                if maxk <= 0:
                    break
                node, node_pre, node_suc = path[idx], path[idx - 1], path[idx + 1]
                edge = g.edges[node_pre, node]["data"]
                minradius = expected_minradius(edge)
                # if nodes[node].get("added_long"):  # nodes added by split edges are expected to create straights
                #     minradius=max(minradius * 2,100)
                if maxk > 1 / minradius:
                    t01 = y[idx] - y[idx - 1]
                    t12 = y[idx + 1] - y[idx]
                    l01 = t01.length()
                    l12 = t12.length()
                    if Vec2.angle(t01, t12) > maxangle / 180 * pi:
                        pass  # print(f"Dont remove, Angle too high {Vec2.angle(t01, t12)*180/pi:.3f}")
                    elif l01 + l12 > max_edge_length:
                        print(f"Dont remove {node} with Rmin={1 / maxk:.4g}, Edge would be too long {l01 + l12:.3g}")
                    else:
                        print(f"Remove Node({node}) CURVE "
                              f"{edge['track'] and 'track(' + edge['track']['type'] or 'street(' + edge['street']['type']},"
                              f"{(edge['track'] or edge['street'])['speed'] or ''}) too narrow Rmin={1 / maxk:.4g}")
                        # use data from longer edge
                        node_data, node_other = (node_pre, node_suc) if l01 > l12 else (node_suc, node_pre)
                        remove_node(g, nodes, edges, path, node, node_other, node_data)
                        break
                ks[kidx][1] = -1  # ignore for the rest of this loop
                skip_nodes.add(node)


def remove_short_unnecessary_edges(paths, g, gt, gs, nodes, edges, max_edge_length, maxangle):
    for path in paths:
        skip_nodes = set(path[i] for i in range(1, len(path) - 1)
                         if not is_node_removable(g, gt, gs, path[i], path[i - 1], path[i + 1]))
        segdelnodes = [[] for _ in range(len(path) - 1)]  # for the dist condition, use to find segement to test
        while len(path) > 2:
            c = get_spline(g, path)
            x, y = c.x, c.y
            # cerr = c.error_spline()
            # maxerr = [[i, cerr.maxerr_at_node(i)] for i in range(1, len(path) - 1) if path[i] not in skip_nodes]
            # print(maxerr)
            trynodes = [i for i in range(1, len(path) - 1) if path[i] not in skip_nodes]
            if len(trynodes) == 0:
                break
            for idx in trynodes:
                node = path[idx]
                t01 = y[idx] - y[idx - 1]
                t12 = y[idx + 1] - y[idx]
                l01 = t01.length()
                l12 = t12.length()
                assert l01 > 0
                assert l12 > 0
                if l01 + l12 < max_edge_length \
                        and c.viabs[idx] > 0 \
                        and Vec2.angle(c.vi[idx], t01) < maxangle / 180 * pi \
                        and Vec2.angle(c.vi[idx], t12) < maxangle / 180 * pi \
                        and Vec2.angle(t01, t12) < maxangle / 180 * pi:
                    # spline curve without this node
                    cwo = get_spline(g, [n for i, n in enumerate(path) if i != idx])
                    dist = cwo.dist_to_point(y[idx], idx - 1, idx)  # distance to the removed node
                    # check distance of already removed nodes
                    distothers = max((cwo.dist_to_point(Vec2(nodes[n]["pos"]), i if i < idx else i - 1, i + 1 if
                    i < idx else i) for i, seg in enumerate(segdelnodes) for n in seg), default=-1)
                    if idx == 1 and Vec2.angle(cwo.vi[0], t01) > 10 / 180 * pi:  # try preserve orig start direction
                        pass
                    elif idx == len(path) - 2 and Vec2.angle(cwo.vi[-1], t12) > 10 / 180 * pi:
                        pass
                    elif 1 < idx < len(path) - 2 and (Vec2.angle(cwo.y[idx - 1] - cwo.y[idx - 2],
                                                                 cwo.y[idx] - cwo.y[idx - 1]) > maxangle / 180 * pi
                                                      or Vec2.angle(cwo.y[idx + 1] - cwo.y[idx],
                                                                    cwo.y[idx] - cwo.y[idx - 1]) > maxangle / 180 * pi):
                        pass
                    elif dist < 1.8 and distothers < 2.2:
                        print(f"Remove Node({node}) errdist={dist:.3g} distoth={distothers:.3g} "
                              f"new edge len {l01 + l12:.4g}= {l01:.4g} + {l12:.4g}")
                        node_data, node_other = (path[idx - 1], path[idx + 1]) if l01 > l12 else (
                            path[idx + 1], path[idx - 1])
                        remove_node(g, nodes, edges, path, node, node_other, node_data)
                        segdelnodes[idx - 1].append(node)
                        segdelnodes[idx - 1].extend(segdelnodes[idx])
                        segdelnodes.pop(idx)
                        break
                skip_nodes.add(node)


def expected_minradius(edge):
    r = 1
    if edge["track"]:
        if edge["track"]["type"] == "rail":
            r = 100
            if edge["track"]["speed"]:
                r = expected_radius_speed(edge["track"]["speed"] / 3.6) / 1.1  # tolerance
        elif edge["track"]["type"] in {"light_rail", "subway"}:
            r = 50
        elif edge["track"]["type"] in {"tram", "narrow_gauge", "disused"}:
            r = 10
    if edge["street"]:
        if edge["street"]["type"] in {"motorway", "trunk"}:
            r = 40
        elif edge["street"]["type"] in {"motorway_link", "trunk_link", "primary", "secondary", "tertiary", }:
            r = 5
    return r


def expected_radius_speed(speed):
    # TPF2 tracks speedCoeffs say: curve speed limit [m/s] = a * (radius + b) ^ c
    # -> radius = (speed/a)^(1/c)-b
    a, b, c = 1.36, -40, 0.5  # from WernerK "Realistic Track Speed" Mod
    return (speed / a) ** (1 / c) - b


def remove_node(g, nodes, edges, path, node_rem, node_keep, node_correct):
    assert not nodes[node_rem].get("removed")
    # remove edge and correct connected edge with other node
    edges.pop(g.edges[node_rem, node_keep]["name"])  # remove edge from orig data
    g.remove_edge(node_rem, node_keep)
    edge = g.edges[node_rem, node_correct]["data"]  # use this edge's data
    if edge["node0"] == node_rem:  # determine direction of edge
        assert edge["node1"] == node_correct
        edge["node0"] = node_keep
    else:
        assert edge["node0"] == node_correct
        assert edge["node1"] == node_rem
        edge["node1"] = node_keep
    if not g.has_edge(node_correct, node_keep):
        g.add_edge(node_correct, node_keep, **g.edges[node_rem, node_correct])
    else:
        print(f"WARNING: Edge({node_correct},{node_keep}) already exist while removing {node_rem}", file=sys.stderr)
        # dont add, lets hope nothing bad happens
    g.remove_edge(node_rem, node_correct)
    g.remove_node(node_rem)
    path.remove(node_rem)
    nodes[node_rem]["removed"] = True


def get_spline(g, path, method="natural"):
    y = [g.nodes[n]["pos"].toArray() for n in path]
    return CubicSpline(y, bc_method=method)


def add_curve_tangents(paths, g, method="finite_difference", maxangle=30, warnangle=90):
    for path in paths:
        for n0, n1 in zip(path[:-1], path[1:]):
            e = g.edges[n0, n1]["data"]
            if e["node0"] == n1:
                e["node0"], e["node1"] = e["node1"], e["node0"]  # align edge in same direction as path
                e["nodes_reversed"] = True
        if method in {"natural"}:
            c = get_spline(g, path, method="natural")
            x, y = c.x, c.y
            for i in range(0, len(path) - 1):
                minv = min(c.vabs(t) for t in np.linspace(x[i], x[i + 1], 10))
                if minv < 0.1:
                    print(f"WARNING Edge({path[i]},{path[i + 1]}) low spline speed {minv}")
            cubic_tangs = {}
            for i in range(1, len(path) - 1):
                if c.viabs[i] > 0:
                    cubic_tangs[path[i]] = c.vi[i]
            if c.viabs[0] > 0:
                g.edges[path[0], path[1]]["data"]["tangent0"] = (c.vi[0] * (x[1] - x[0])).toArray()
            if c.viabs[-1] > 0:
                g.edges[path[-1], path[-2]]["data"]["tangent1"] = (c.vi[-1] * (x[-1] - x[-2])).toArray()
            for angle in [
                Vec2.angle(c.vi[0], y[1] - y[0]),
                Vec2.angle(c.vi[-1], y[-1] - y[-2])]:
                if angle > warnangle / 180 * pi:
                    print(f"WARNING start/end node {path[0]} Diff tang angle: {angle * 180 / pi:.3f}")
        for n0, n1, n2 in zip(path[:-2], path[1:-1], path[2:]):
            p0 = g.nodes[n0]["pos"]
            p1 = g.nodes[n1]["pos"]
            p2 = g.nodes[n2]["pos"]
            t01 = p1 - p0
            t12 = p2 - p1
            e01 = g.edges[n0, n1]["data"]
            e12 = g.edges[n1, n2]["data"]
            if Vec2.angle(t01, t12) < maxangle / 180 * pi:
                if method == "finite_difference":  # https://en.wikipedia.org/wiki/Cubic_Hermite_spline
                    tang = (t01.normalize() + t12.normalize()) / 2
                elif method == "Catmull–Rom":
                    tang = (p2 - p0) / 2
                elif method == "natural":
                    tang = cubic_tangs.get(n1)
                    if not tang:
                        continue
                    if not .7 < tang.length() < 1.5:
                        print(f"WARNING: at {n1} spline tang length {tang}")
                else:
                    raise Exception("Unknown tangent method: " + method)
                for angle in [Vec2.angle(tang, t01), Vec2.angle(tang, t12)]:
                    if angle > warnangle / 180 * pi:
                        print(f"WARNING: node {n1} "
                              f"{e01['street'] and 'street(' + e01['street']['type'] or 'track(' + e01['track']['type']}) "
                              f"Diff tang angle: {angle * 180 / pi:.3f}")
                if method in {"finite_difference", "Catmull–Rom"}:
                    l01 = approx_length_arc(t01.length(), Vec2.angle(t01, tang))
                    l12 = approx_length_arc(t12.length(), Vec2.angle(t12, tang))
                    e01["tangent1"] = tang.normalize(l01).toArray()
                    e12["tangent0"] = tang.normalize(l12).toArray()
                elif method in {"natural"}:  # cubic spline was initialized with x (linear length)
                    e01["tangent1"] = (tang * t01.length()).toArray()
                    e12["tangent0"] = (tang * t12.length()).toArray()


def add_path_info_to_nodes(paths, nodes, prefix):
    for path in paths:
        for n0, n1, n2 in zip(path[:-2], path[1:-1], path[2:]):
            assert f"path_{prefix}_predecessor" not in nodes[n1], n1
            assert f"path_{prefix}_successor" not in nodes[n1], n1
            nodes[n1][f"path_{prefix}_predecessor"] = n0
            nodes[n1][f"path_{prefix}_successor"] = n2


def adjust_signals(nodes, g):
    for nid, node in nodes.items():
        if node.get("signal"):
            if "path_track_predecessor" in node and "path_track_successor" in node:
                edge = g.edges[nid, node["path_track_predecessor"]]
                # place signal on edge before because of Signal Distance and so that signals are right in front of poles
                if edge["data"].get("nodes_reversed"):
                    node["signal"]["direction_backward"] = not node["signal"]["direction_backward"]
                if node["signal"]["direction_backward"]:
                    edge = g.edges[nid, node["path_track_successor"]]  # need to place on edge after before pole
                edge["data"]["objects"] = {"signal": node["signal"]}
                node["signal"] = False
            else:
                print(f"Node {nid} signal but no path info")


def create_graphs(nodes, edges):
    g = nx.Graph()  # undirected graph
    gd = nx.DiGraph()  # directed graph
    for id, node in nodes.items():
        for gi in [g, gd]:
            gi.add_node(id, data=node, pos=Vec2(node["pos"]), endpoint=node.get("endpoint"))
    for id, edge in edges.items():
        assert bool(edge["track"]) ^ bool(edge["street"]), f"Edge has to be track OR street {id}"
        if g.has_edge(edge["node0"], edge["node1"]):  # duplicate edges can exist because of mapping errors or...
            print(f'Edge({edge["node0"]},{edge["node1"]}) {id} already exist! '
                  f'(type: {g.edges[edge["node0"], edge["node1"]]["type"]})')
            if edge["track"]:  # ...tracks on streets. priorize street.
                continue  # (by overiding the edge, but works only for undirected!)
            if gd.has_edge(edge["node1"], edge["node0"]):
                gd.remove_edge(edge["node1"], edge["node0"])  # avoid duplicate edge for directed graph
        for gi in [g, gd]:
            gi.add_edge(edge["node0"], edge["node1"], name=id, data=edge,
                        type=edge["track"] and "TRACK" or edge["street"] and "STREET")
    g.remove_nodes_from(list(nx.isolates(g)))  # remove nodes not connected to any edges
    gd.remove_nodes_from(list(nx.isolates(gd)))
    return g, gd


def create_sub_graph(g, etype):
    g2 = g.copy()
    g2.remove_edges_from(filter(lambda e: g.edges[e]["type"] != etype, g.edges))
    g2.remove_nodes_from(list(nx.isolates(g2)))
    return g2


def create_bridge_graph(g):
    g2 = g.copy()
    g2.remove_edges_from(filter(lambda e: not g.edges[e]["data"]["bridge"], g.edges))
    g2.remove_nodes_from(list(nx.isolates(g2)))
    return g2


def is_node_removable(g, gt, gs, node, n_pre, n_suc, exclude_bridges=False, printt=False):
    if is_railway_crossing(g, gt, node):
        if printt:
            print(node, "is railway crossing")
        return False
    if gt.has_node(node) and gs.has_node(node):
        if printt:
            print(node, "is street and track node")
        return False
    if g.nodes[node]["data"].get("signal"):
        if printt:
            print(node, "is signal")
        return False
    if is_bridge_or_tunnel(g, node, n_pre) != is_bridge_or_tunnel(g, node, n_suc):
        if printt:
            print(node, "is at Bridge transition")
        return False
    if exclude_bridges and (is_bridge_or_tunnel(g, node, n_pre) or is_bridge_or_tunnel(g, node, n_suc)):
        return False
    edge_pre = g.edges[node, n_pre]["data"]
    edge_suc = g.edges[node, n_suc]["data"]
    if edge_pre["track"] and edge_pre["track"]["type"] != edge_suc["track"]["type"]:
        if printt:
            print(node, "between different rail types")
        return False
    if edge_pre["street"] and edge_pre["street"]["type"] != edge_suc["street"]["type"]:
        if printt:
            print(node, "between different highway types")
        return False
    return True


def is_railway_crossing(g, gt, node):
    return g.degree[node] >= 4 and gt.degree[node] >= 2


def is_bridge_or_tunnel(g, n0, n1):
    return bool(g.edges[n0, n1]["data"]["bridge"]) or bool(g.edges[n0, n1]["data"]["tunnel"])


# inspired by OSMNX


def is_endpoint(g, node):
    if g.nodes[node].get("endpoint"):
        return True
    return g.degree(node) != 2


def get_paths_to_simplify(G, G2):  # G2: graph to check degree / to consider railway crossings
    endpoints = set([n for n in G.nodes if is_endpoint(G2, n)])
    all_between_points = set()
    if isinstance(G, nx.DiGraph):
        for endpoint in endpoints:
            for successor in G.successors(endpoint):
                if successor not in endpoints and successor not in all_between_points:
                    path = build_path(G, endpoint, successor, endpoints)
                    all_between_points.update(set(path))
                    yield path
        # prefer successors to build paths according to direction
        for endpoint in endpoints:
            for successor in G.predecessors(endpoint):
                if successor not in endpoints and successor not in all_between_points:
                    path = build_path(G, endpoint, successor, endpoints)
                    all_between_points.update(set(path))
                    yield path
    else:
        for endpoint in endpoints:
            for successor in G.neighbors(endpoint):
                if successor not in endpoints and successor not in all_between_points:
                    path = build_path(G, endpoint, successor, endpoints)
                    all_between_points.update(set(path))
                    yield path


def build_path(G, endpoint, endpoint_successor, endpoints):
    path = [endpoint, endpoint_successor]
    successor = endpoint_successor
    while successor not in endpoints:
        if isinstance(G, nx.DiGraph):
            iternodes = {*G.successors(successor), *G.predecessors(successor)}
        else:
            iternodes = set(G.neighbors(successor))
        assert len(iternodes) == 2, successor
        successors = [n for n in iternodes if n not in path]
        if len(successors) == 1:
            successor = successors[0]
            path.append(successor)
        elif len(successors) == 0:  # Loop
            if endpoint in iternodes:
                return path + [endpoint]
            else:
                raise Exception(f"Unexpected path end {path}")
        else:
            raise Exception(f"Unexpected simplify pattern failed near {successor}")
    return path
