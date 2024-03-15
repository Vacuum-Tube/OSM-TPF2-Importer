import math
import networkx as nx
import numpy as np
from scipy.interpolate import CubicSpline

from vec2 import Vec2


def optimize(data):
    # 1. Avoid very long edges (can cut through terrain)
    print("=" * 16 + " Split long Edges " + "=" * 16)
    split_long_edges(data["nodes"], data["edges"], 70, etype="street")
    split_long_edges(data["nodes"], data["edges"], 100, etype="track")

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

    # 3. Avoid very short tracks (can lead to zig-zag) and merge them
    print("=" * 16 + " Remove short Track Edges " + "=" * 16)
    remove_short_edges(paths_track, g, gt, gs, data["nodes"], data["edges"], 15)

    # 4. Calculate tangents for curved edge paths
    print("=" * 16 + " Calculate Tangents " + "=" * 16)
    add_curve_tangents(paths_track, g, method="natural", warnangle=15)
    add_curve_tangents(paths_street, g, method="natural")
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
            print(f"Edge({n0},{n1}) is long ({length:.3f}), split it")
            remove_edges.append(eid)
            num_seg = math.ceil(length / max_edge_length)
            lastnode = n0
            for i in range(1, num_seg + 1):
                if i < num_seg:
                    p = p0 + (p1 - p0) * i / num_seg
                    newnode = {"pos": p.toArray()}
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
    for node_ids in paths:
        # print(f"Path: {node_ids}")
        edge_removed = True
        skipped = False
        skip_edges = set()
        while (edge_removed or skipped) and len(node_ids) > 2:
            edge_removed = False
            skipped = False
            lens = []
            for n0, n1 in zip(node_ids[:-1], node_ids[1:]):
                if (n0, n1) not in skip_edges and not is_bridge_or_tunnel(g, n0, n1):
                    p0 = Vec2(nodes[n0]["pos"])
                    p1 = Vec2(nodes[n1]["pos"])
                    length = (p1 - p0).length()
                    lens.append(length)
                else:
                    lens.append(math.inf)
            idx = min(range(len(lens)), key=lambda x: lens[x])  # argmin, find shortest edge
            if lens[idx] < min_edge_length:
                if idx == 0:
                    succ = True
                elif idx == len(lens) - 1:
                    succ = False
                # try to find the better side of the edge to adjust
                elif is_railway_crossing(g, gt, node_ids[idx]):
                    succ = True
                elif is_railway_crossing(g, gt, node_ids[idx + 1]):
                    succ = False
                elif nodes[node_ids[idx]]["signal"]:
                    succ = True
                elif nodes[node_ids[idx + 1]]["signal"]:
                    succ = False
                elif is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx + 1]) != \
                        is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx - 1]):  # node is at bridge transition
                    succ = True
                elif is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx + 1]) != \
                        is_bridge_or_tunnel(g, node_ids[idx + 2], node_ids[idx + 1]):
                    succ = False
                elif lens[idx + 1] < lens[idx - 1]:  # remove node at side of shorter edge
                    succ = True
                else:
                    succ = False
                print(f"Edge({node_ids[idx]},{node_ids[idx + 1]}) is short ({lens[idx]:.3f}), remove it")
                # {'after' if succ else 'before'} {idx}")
                if succ:  # replace with successor
                    node_rem = node_ids[idx + 1]
                    node_keep = node_ids[idx]
                    node_correct = node_ids[idx + 2]
                else:  # replace with predecessor
                    node_rem = node_ids[idx]
                    node_keep = node_ids[idx + 1]
                    node_correct = node_ids[idx - 1]
                # check if remove node is possible
                if is_railway_crossing(g, gt, node_rem):
                    print(node_rem, "is railway crossing")
                    skipped = True
                if nodes[node_rem]["signal"]:
                    print(node_rem, "is signal")
                    skipped = True
                if is_bridge_or_tunnel(g, node_rem, node_correct) != is_bridge_or_tunnel(g, node_rem, node_keep):
                    print("Bridge transition")
                    skipped = True
                if gs.has_node(node_rem):
                    print(node_rem, "is also a street node")
                    skipped = True
                if skipped:
                    skip_edges.add((node_ids[idx], node_ids[idx + 1]))
                    print("Cannot remove", node_rem)
                    continue
                # remove this edge and correct connected edge with other node
                edges.pop(g.edges[node_rem, node_keep]["name"])  # remove edge from orig data
                g.remove_edge(node_rem, node_keep)
                edge = g.edges[node_rem, node_correct]["data"]
                if edge["node0"] == node_rem:  # determine direction of edge
                    assert edge["node1"] == node_correct
                    edge["node0"] = node_keep
                else:
                    assert edge["node0"] == node_correct
                    assert edge["node1"] == node_rem
                    edge["node1"] = node_keep
                g.add_edge(node_correct, node_keep, **g.edges[node_rem, node_correct])
                g.remove_edge(node_rem, node_correct)
                node_ids.remove(node_rem)  # remove from path
                nodes[node_rem]["removed"] = True
                edge_removed = True


def add_curve_tangents(paths, g, method="finite_difference", maxangle=30, warnangle=90):
    for path in paths:
        for n0, n1 in zip(path[:-1], path[1:]):
            e = g.edges[n0, n1]["data"]
            if e["node0"] == n1:
                e["node0"], e["node1"] = e["node1"], e["node0"]  # align edge in same direction as path
                e["nodes_reversed"] = True
        y = [g.nodes[n]["pos"] for n in path]
        x = [0]
        for yi, yi1 in zip(y[:-1], y[1:]):
            x.append(x[-1] + (Vec2(yi1) - Vec2(yi)).length())  # heuristic: linear spline length
        if method in {"natural"}:
            c = CubicSpline(x, y, bc_type="natural", extrapolate=False)
            v = c.derivative(1)
            a = c.derivative(2)
            k = lambda t: abs(v(t)[0] * a(t)[1] - v(t)[1] * a(t)[0]) / sum(v(t) ** 2) ** 1.5  # curvature
            cubic_tangs = {}
            for i in range(1, len(path) - 1):
                if Vec2(v(x[i])).length() > 0:
                    cubic_tangs[path[i]] = Vec2(v(x[i]))
            if Vec2(v(x[0])).length() > 0:
                g.edges[path[0], path[1]]["data"]["tangent0"] = (Vec2(v(x[0])) * (x[1] - x[0])).toArray()
            if Vec2(v(x[-1])).length() > 0:
                g.edges[path[-1], path[-2]]["data"]["tangent1"] = (Vec2(v(x[-1])) * (x[-1] - x[-2])).toArray()
            for angle in [
                Vec2.angle(Vec2(v(x[0])), Vec2(y[1]) - Vec2(y[0])),
                Vec2.angle(Vec2(v(x[-1])), Vec2(y[-1]) - Vec2(y[-2]))]:
                if angle > warnangle / 180 * math.pi:
                    print(f"WARNING start/end node {path[0]} Diff tang angle: {angle * 180 / math.pi:.3f}")
            for i in range(1, len(path) - 1):
                maxk = max(*(k(t) for t in np.linspace(x[i] - 0.49 * (x[i] - x[i - 1]), x[i], 10)),
                           *(k(t) for t in np.linspace(x[i], x[i] + 0.49 * (x[i + 1] - x[i]), 10)))
                edge = g.edges[path[0], path[1]]["data"]
                if edge["track"] and maxk > 1 / (150 if edge["track"]["type"] == "rail" else 25):
                    print(f"CURVE {edge['track']['type']} at {path[i]} Rmin={1 / maxk:.3f}")
        for n0, n1, n2 in zip(path[:-2], path[1:-1], path[2:]):
            p0 = Vec2(g.nodes[n0]["pos"])
            p1 = Vec2(g.nodes[n1]["pos"])
            p2 = Vec2(g.nodes[n2]["pos"])
            t01 = p1 - p0
            t12 = p2 - p1
            e01 = g.edges[n0, n1]["data"]
            e12 = g.edges[n1, n2]["data"]
            if Vec2.angle(t01, t12) < maxangle / 180 * math.pi:
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
                    if angle > warnangle / 180 * math.pi:
                        print(f"WARNING: node {n1} "
                              f"{e01['street'] and 'street(' + e01['street']['type'] or 'track(' + e01['track']['type']}) "
                              f"Diff tang angle: {angle * 180 / math.pi:.3f}")
                if method in {"finite_difference", "Catmull–Rom"}:
                    l01 = cubspline_apprx_length(t01.length(), Vec2.angle(t01, tang))
                    l12 = cubspline_apprx_length(t12.length(), Vec2.angle(t12, tang))
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
        g.add_node(id, **node)
        gd.add_node(id, **node)
    for id, edge in edges.items():
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


def is_railway_crossing(g, gt, node):
    return g.degree[node] >= 4 and gt.degree[node] >= 2


def is_bridge_or_tunnel(g, n0, n1):
    return bool(g.edges[n0, n1]["data"]["bridge"]) or bool(g.edges[n0, n1]["data"]["tunnel"])


def cubspline_apprx_length(dist, angle):
    assert 0 <= angle < math.pi / 2, angle
    if angle < .001:
        return dist
    return dist * angle / math.cos(math.pi / 2 - angle / 2) / 2


# inspired by OSMNX


def is_endpoint(G, node):
    return G.degree(node) != 2


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
