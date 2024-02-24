import math
import networkx as nx
from vec2 import Vec2


def optimize(data):
    # 1. Avoid very long edges (can cut through terrain)
    split_long_edges(data["nodes"], data["edges"], 70, etype="street")
    split_long_edges(data["nodes"], data["edges"], 100, etype="track")

    # 2. Create graph and obtain paths
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
    remove_short_edges(paths_track, g, gt, data["nodes"], data["edges"], 15)

    # 4. Calculate tangents for curved edge paths
    add_curve_tangents(paths_track, g)
    add_curve_tangents(paths_street, g)
    add_path_info_to_nodes(paths_track, data["nodes"], "track")
    add_path_info_to_nodes(paths_street, data["nodes"], "street")

    # 5. Add signal information to edges
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


def remove_short_edges(paths, g, gt, nodes, edges, min_edge_length):
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
                # remove this edge; remove node at side of shorter edge, correct connected edge
                if idx == 0:
                    succ = True
                elif idx == len(lens) - 1:
                    succ = False
                elif is_railway_crossing(g, gt, node_ids[idx]):
                    succ = True
                elif is_railway_crossing(g, gt, node_ids[idx + 1]):
                    succ = False
                elif nodes[node_ids[idx]]["signal"]:
                    succ = True
                elif nodes[node_ids[idx + 1]]["signal"]:
                    succ = False
                elif not is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx + 1]) and \
                        is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx - 1]):
                    succ = True
                elif not is_bridge_or_tunnel(g, node_ids[idx], node_ids[idx + 1]) and \
                        is_bridge_or_tunnel(g, node_ids[idx + 2], node_ids[idx + 1]):
                    succ = False
                elif lens[idx + 1] < lens[idx - 1]:
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
                if (is_railway_crossing(g, gt, node_rem)  # between 2 railwaycrossings or endpoints, cant remove
                        or nodes[node_rem]["signal"]):  # dont remove signal
                    # or is_bridge_or_tunnel(g, node_rem, node_correct)
                    skip_edges.add((node_ids[idx], node_ids[idx + 1]))
                    skipped = True
                    print("Cannot remove")
                    continue
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
                # write to g (thought gt will not be updated)
                g.add_edge(node_correct, node_keep, **g.edges[node_rem, node_correct])
                g.remove_edge(node_rem, node_correct)
                node_ids.remove(node_rem)
                nodes[node_rem]["removed"] = True
                edge_removed = True


def add_curve_tangents(paths, g, maxangle=30):
    for path in paths:
        for n0, n1, n2 in zip(path[:-2], path[1:-1], path[2:]):
            p0 = Vec2(g.nodes[n0]["pos"])
            p1 = Vec2(g.nodes[n1]["pos"])
            p2 = Vec2(g.nodes[n2]["pos"])
            t01 = (p1 - p0)  # .normalize()
            t12 = (p2 - p1)  # .normalize()
            if Vec2.angle_cos(t01, t12) > math.cos(maxangle / 180 * math.pi):
                tang = (t01 + t12).normalize()
                # nodes[n1]["tangent"] = tang.toArray()
                e01 = g.edges[n0, n1]["data"]
                if e01["node0"] == n0:
                    tangent01, mirr = "tangent1", 1
                else:
                    tangent01, mirr = "tangent0", -1
                    e01["reversetopath"] = True
                e01[tangent01] = (tang * t01.length() * mirr).toArray()
                e12 = g.edges[n1, n2]["data"]
                if e12["node0"] == n1:
                    tangent01, mirr = "tangent0", 1
                else:
                    tangent01, mirr = "tangent1", -1
                    e12["reversetopath"] = True
                e12[tangent01] = (tang * t12.length() * mirr).toArray()


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
        g.add_node(id, pos=node["pos"])
    for id, edge in edges.items():
        if g.has_edge(edge["node0"], edge["node1"]):  # duplicate edges can exist because of mapping errors or...
            print(f'Edge({edge["node0"]},{edge["node1"]}) {id} already exist! '
                  f'(type: {g.edges[edge["node0"], edge["node1"]]["type"]})')
            if edge["track"]:  # ...tracks on streets. priorize street.
                continue
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
    return g.degree[node] == 4 and gt.degree[node] == 2


def is_bridge_or_tunnel(g, n0, n1):
    return bool(g.edges[n0, n1]["data"]["bridge"]) or bool(g.edges[n0, n1]["data"]["tunnel"])


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
