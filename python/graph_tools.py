from math import pi
import networkx as nx

from vec2 import Vec2


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


def is_node_removable(g, gt, gs, node, exclude_bridges=False, printt=False):
    assert g.has_node(node)
    if gt.has_node(node) and gs.has_node(node):
        if printt:
            print(node, "is street and track node")
        return False
    if g.nodes[node]["data"].get("added_long"):
        return True
    if g.nodes[node]["data"].get("signal") and any((g.nodes[node]["data"]["signal"][typ] for typ in [
        "main",  # types actually used in Lua
        "combined",
        "distant",
        "minor",
        "speedlimit",
        "speedlimitdistant",
        "crossing",
        "route",
        "routedistant",
        "departure",
        "whistle",
    ])):
        if printt:
            print(node, "is signal")
        return False
    if g.degree(node) != 2:
        if printt:
            print(node, "not degree 2")
        return False
    neighbors = set(g.neighbors(node))
    assert len(neighbors) == 2
    n_pre, n_suc = neighbors
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
    if len(g.nodes[node]["data"]["way_start_to"]) + len(g.nodes[node]["data"]["way_end_from"]) + \
            2 * len(g.nodes[node]["data"]["way_within"]) != 2:  # two parallel ways on nodes
        if printt:
            print(node, "no degree 2 from ways")
        return False
    return True


def remove_node(g, nodes, edges, path, node_rem, node_keep, node_correct):
    assert not nodes[node_rem].get("removed"), f"node already removed {node_rem}"
    assert node_correct != node_keep, f"error while remove {node_rem}"
    assert path.count(node_rem) == 1, f"node multiple times on path {node_rem}"
    if g.has_edge(node_correct, node_keep):
        print(f"WARNING: Edge({node_correct},{node_keep}) already exist while removing {node_rem}")
        return False
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
    g.add_edge(node_correct, node_keep, **g.edges[node_rem, node_correct])
    g.remove_edge(node_rem, node_correct)
    g.remove_node(node_rem)
    path.remove(node_rem)
    nodes[node_rem]["removed"] = True
    return True


def is_railway_crossing(g, gt, node):
    return g.degree[node] >= 4 and gt.degree[node] >= 2


def is_bridge_or_tunnel(g, n0, n1):
    return bool(g.edges[n0, n1]["data"]["bridge"]) or bool(g.edges[n0, n1]["data"]["tunnel"])


# inspired by OSMNX


def is_endpoint(g, node, maxangle=None):
    if g.nodes[node].get("endpoint"):
        return True
    if g.degree(node) != 2:
        return True
    if isinstance(g, nx.DiGraph):
        neighbors = [*g.successors(node), *g.predecessors(node)]
    else:
        neighbors = list(g.neighbors(node))
    assert len(neighbors) == 2, node
    p1 = g.nodes[node]["pos"]
    p0 = g.nodes[neighbors[0]]["pos"]
    p2 = g.nodes[neighbors[1]]["pos"]
    if maxangle and Vec2.angle(p1 - p0, p2 - p1) > maxangle / 180 * pi:
        return True
    return False


def get_paths_to_simplify(g, maxangle=None):
    endpoints = set(n for n in g.nodes if is_endpoint(g, n, maxangle=maxangle))  # misses isolated loops
    usededges = nx.Graph()
    try_nodes = []
    for endpoint in endpoints:
        for successor in g.nodes[endpoint]["data"]["way_start_to"]:
            try_nodes.append((endpoint, successor))
    for endpoint in endpoints:
        for successor in g.nodes[endpoint]["data"]["way_end_from"]:
            try_nodes.append((endpoint, successor))
    for endpoint in endpoints:
        for nodes in g.nodes[endpoint]["data"]["way_within"]:
            try_nodes.append((endpoint, nodes[1]))
            try_nodes.append((endpoint, nodes[0]))
    for endpoint, successor in try_nodes:
        if (g.has_edge(endpoint, successor) or g.has_edge(successor, endpoint)) \
                and not usededges.has_edge(endpoint, successor):
            path = build_path(g, endpoint, successor, endpoints, usededges, maxangle=maxangle)
            assert path[0] in endpoints and path[-1] in endpoints, path
            for i, j in zip(path[:-1], path[1:]):
                usededges.add_edge(i, j)
            if len(path) > 2:
                yield path
    if (usededges.number_of_nodes(), usededges.number_of_edges()) != (g.number_of_nodes(), g.number_of_edges()):
        print(f"WARNING usededges graph not equal to g ", usededges)


def build_path(g, endpoint, endpoint_successor, endpoints, usededges, maxangle=None):
    path = [endpoint, endpoint_successor]
    successor = endpoint_successor
    while True:
        if successor in endpoints:
            if g.degree(successor) > 2 and successor != endpoint:
                continu = False
                p1 = g.nodes[successor]["pos"]
                for n_pre, n_suc in g.nodes[successor]["data"]["way_within"]:
                    if path[-2] == n_pre and g.has_edge(successor, n_suc):  # way over endpoint
                        successor = n_suc  # continue with path behind endpoint
                        continu = True
                        break
                    elif path[-2] == n_suc and g.has_edge(n_pre, successor):
                        successor = n_pre
                        continu = True
                        break
                if continu and not usededges.has_edge(path[-1], successor) and \
                        (Vec2.angle(p1 - g.nodes[n_pre]["pos"],
                                    g.nodes[n_suc]["pos"] - p1) < maxangle / 180 * pi if maxangle else True):
                    path.append(successor)
                    continue
            break
        if isinstance(g, nx.DiGraph):
            neighbors = {*g.successors(successor), *g.predecessors(successor)}
        else:
            neighbors = set(g.neighbors(successor))
        assert len(neighbors) == 2, successor
        successors = [n for n in neighbors if n not in path]
        if len(successors) == 1:
            successor = successors[0]
            path.append(successor)
        elif len(successors) == 0:
            if endpoint in neighbors:  # Loop
                return path + [endpoint]
            else:
                endnode = [n for n in neighbors if n != path[-2]]
                if len(endnode) == 1:  # Ballon
                    return path + [endnode[0]]
                else:
                    raise Exception(f"Unexpected path end {path}")
        else:
            raise Exception(f"New neighbors not connected to path at {successor}")
    return path
