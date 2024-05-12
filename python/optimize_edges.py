import math
from math import pi
import numpy as np

from vec2 import Vec2
from cubic_spline import MyCubicSpline as CubicSpline, approx_length_arc
from graph_tools import create_graphs, create_sub_graph, create_bridge_graph, get_paths_to_simplify, is_node_removable, \
    remove_node


def optimize(data):
    # 1. Avoid very long edges (can cut through terrain, and affects curve splines negatively)
    print("=" * 16 + " Split long Edges " + "=" * 16)
    split_long_edges(data["nodes"], data["edges"], 100, etype="street")
    split_long_edges(data["nodes"], data["edges"], 200, etype="track")

    # 2. Create graph and obtain paths
    print("=" * 16 + " Create Graphs " + "=" * 16)
    g, gd = create_graphs(data["nodes"], data["edges"])
    gs = create_sub_graph(g, "STREET")
    print("Street: ", gs)
    gt = create_sub_graph(gd, "TRACK")  # we need a directed graph for the signal direction
    print("Track: ", gt)
    gb = create_bridge_graph(g)
    print("Bridge: ", gb)
    paths_track = list(get_paths_to_simplify(gt, maxangle=45))
    paths_street = list(get_paths_to_simplify(gs, maxangle=30))
    paths_bridge = list(get_paths_to_simplify(gb))
    data["paths"] = {
        "track": paths_track,
        "street": paths_street,
        "bridge": paths_bridge,
    }
    print(f"Track Paths: {len(paths_track)} , Av len: {np.array([len(p) for p in paths_track]).mean():.1f}")
    print(f"Street Paths: {len(paths_street)} , Av len: {np.array([len(p) for p in paths_street]).mean():.1f}")
    print(f"Bridge Paths: {len(paths_bridge)} , Av len: {np.array([len(p) for p in paths_bridge]).mean():.1f}")

    # 3. Remove Nodes to improve curve geometry and reduce number of segments
    print("=" * 16 + " Remove Nodes with high curvature " + "=" * 16)
    remove_nodes_curvature(paths_track, g, gt, gs, data["nodes"], data["edges"], maxlength=200, maxangle=30)
    remove_nodes_curvature(paths_street, g, gt, gs, data["nodes"], data["edges"], maxlength=100, maxangle=25)
    print("=" * 16 + " Remove unnecessary short Edges " + "=" * 16)
    remove_short_unnecessary_edges(paths_track, g, gt, gs, data["nodes"], data["edges"], maxlength=100, maxangle=35)
    remove_short_unnecessary_edges(paths_street, g, gt, gs, data["nodes"], data["edges"], maxlength=70, maxangle=30)
    print("=" * 16 + " Remove short Edges " + "=" * 16)
    remove_short_edges(paths_track, g, gt, gs, data["nodes"], data["edges"], 10)
    remove_short_edges(paths_street, g, gt, gs, data["nodes"], data["edges"], 5)

    # 4. Calculate tangents for curved edge paths
    print("=" * 16 + " Calculate Tangents " + "=" * 16)
    add_curve_tangents(paths_track, g, method="natural", maxangle=999, warnangle=35)
    add_curve_tangents(paths_street, g, method="natural", maxangle=999, warnangle=50)
    add_path_info_to_nodes(paths_track, data["nodes"], "track")
    add_path_info_to_nodes(paths_street, data["nodes"], "street")
    print("=" * 16 + " Align Tangents of Switches " + "=" * 16)
    align_switches_tangents(g, gt, data["nodes"], maxangle=40)

    # 5. Add signal information to edges
    print("=" * 16 + " Adjust Signals " + "=" * 16)
    adjust_signals(data["nodes"], g)

    # remove unnecessary data
    for nid, node in data["nodes"].items():
        node["way_start_to"] = None
        node["way_end_from"] = None
        node["way_within"] = None


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
                    p = p0 + (p1 - p0) * i / num_seg  # linear interpolation
                    newnodekey = f"{eid}_n{i}"
                    newnode = {"pos": p.toArray(), "added_long": True}
                    assert newnodekey not in nodes
                    nodes[newnodekey] = newnode
                else:
                    newnodekey = n1
                newedge = edge.copy()
                newedge["node0"] = lastnode
                newedge["node1"] = newnodekey
                newedgekey = f"{eid}_{i}"
                assert newedgekey not in edges
                assert newedgekey not in add_edges
                add_edges[newedgekey] = newedge
                if i == 1:
                    for k, (n_pre, n_suc) in enumerate(nodes[n0]["way_within"]):
                        if n1 == n_suc:
                            nodes[n0]["way_within"][k][1] = newnodekey
                    for k, ns in enumerate(nodes[n0]["way_start_to"]):
                        if n1 == ns:
                            nodes[n0]["way_start_to"][k] = newnodekey
                if i == num_seg:
                    for k, (n_pre, n_suc) in enumerate(nodes[n1]["way_within"]):
                        if n0 == n_pre:
                            nodes[n1]["way_within"][k][0] = lastnode
                    for k, ne in enumerate(nodes[n1]["way_end_from"]):
                        if n0 == ne:
                            nodes[n1]["way_end_from"][k] = lastnode
                lastnode = newnodekey
    edges.update(add_edges)
    for key in remove_edges:
        edges.pop(key)


def remove_short_edges(paths, g, gt, gs, nodes, edges, min_edge_length):
    for path in paths:  # node_ids
        skip_edges = set()
        while len(path) > 3:
            y = [g.nodes[n]["pos"] for n in path]
            lens = [math.inf if (path[i], path[i + 1]) in skip_edges else (y[i + 1] - y[i]).length() for i in
                    range(len(path) - 1)]
            idx = min(range(len(lens)), key=lambda x: lens[x])  # argmin, find shortest edge
            if lens[idx] > min_edge_length:
                break
            edge = g.edges[path[idx], path[idx + 1]]["data"]
            if edge["track"] and edge["track"]["type"] not in {"rail", "light_rail", "subway"}:
                break
            if edge["street"] and edge["street"]["type"] not in {"motorway", "trunk", "motorway_link", "trunk_link",
                                                                 "primary", "secondary", "tertiary", "residential",
                                                                 "unclassified", "service"}:
                break
            if idx == 0:
                succ = True
            elif idx == len(lens) - 1:
                succ = False
            # try to find the better side of the edge to adjust
            elif not is_node_removable(g, gt, gs, path[idx], exclude_bridges=True):
                succ = True
            elif not is_node_removable(g, gt, gs, path[idx + 1], exclude_bridges=True):
                succ = False
            elif lens[idx + 1] < lens[idx - 1]:  # remove node at side of shorter edge
                succ = True
            else:
                succ = False
            if succ:  # replace with successor
                node_rem = path[idx + 1]
                node_keep = path[idx]
                node_correct = path[idx + 2]
            else:  # replace with predecessor
                node_rem = path[idx]
                node_keep = path[idx + 1]
                node_correct = path[idx - 1]
            if is_node_removable(g, gt, gs, node_rem, exclude_bridges=True, printt=False):
                print(f"Remove Edge({path[idx]},{path[idx + 1]}) is short ({lens[idx]:.4g})")
                if not remove_node(g, nodes, edges, path, node_rem, node_keep, node_correct):
                    break
            else:
                skip_edges.add((path[idx], path[idx + 1]))
                # print("Cannot remove", node_rem)


def remove_nodes_curvature(paths, g, gt, gs, nodes, edges, maxlength, maxangle=30):
    for path in paths:
        skip_nodes = set(path[i] for i in range(1, len(path) - 1)
                         if not is_node_removable(g, gt, gs, path[i]))
        maxk = 1
        while len(path) > 3 and maxk > 0:
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
                    elif l01 + l12 > maxlength:
                        print(f"Dont remove {node} with Rmin={1 / maxk:.4g}, Edge would be too long {l01 + l12:.3g}")
                    else:
                        print(f"Remove Node({node}) CURVE "
                              f"{edge['track'] and 'track(' + edge['track']['type'] or 'street(' + edge['street']['type']},"
                              f"{(edge['track'] or edge['street']).get('speed') or ''}) too narrow Rmin={1 / maxk:.4g}")
                        # use data from longer edge
                        node_data, node_other = (node_pre, node_suc) if l01 > l12 else (node_suc, node_pre)
                        if not remove_node(g, nodes, edges, path, node, node_other, node_data):
                            skip_nodes.add(node)
                        break
                ks[kidx][1] = -1  # ignore for the rest of this loop
                skip_nodes.add(node)


def remove_short_unnecessary_edges(paths, g, gt, gs, nodes, edges, maxlength, maxangle):
    for path in paths:
        for node in path:
            assert not nodes[node].get("removed"), node
        skip_nodes = set(path[i] for i in range(1, len(path) - 1)
                         if not is_node_removable(g, gt, gs, path[i]))
        segdelnodes = [[] for _ in range(len(path) - 1)]  # for the dist condition, use to find segement to test
        while len(path) > 3:
            c = get_spline(g, path)
            x, y = c.x, c.y
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
                if l01 + l12 < maxlength \
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
                        if remove_node(g, nodes, edges, path, node, node_other, node_data):
                            segdelnodes[idx - 1].append(node)
                            segdelnodes[idx - 1].extend(segdelnodes[idx])
                            segdelnodes.pop(idx)
                        else:
                            skip_nodes.add(node)
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


def get_spline(g, path, method="natural"):
    y = [g.nodes[n]["pos"].toArray() for n in path]
    return CubicSpline(y, bc_method=method)


def add_curve_tangents(paths, g, method, maxangle, warnangle):
    for path in paths:
        for n0, n1 in zip(path[:-1], path[1:]):
            e = g.edges[n0, n1]["data"]
            if e["node0"] == n1:
                e["node0"], e["node1"] = e["node1"], e["node0"]  # align edge in same direction as path
                e["nodes_reversed"] = True
        if method in {"natural"}:
            c = get_spline(g, path, method="natural")
            x, y = c.x, c.y
            cerr = c.error_spline()  # curve deviation from straight line - not considering removed nodes!
            for i in range(0, len(path) - 1):
                minv = min(c.vabs(t) for t in np.linspace(x[i], x[i + 1], 10))
                if minv < 0.1:
                    print(f"WARNING Edge({path[i]},{path[i + 1]}) low spline speed {minv}")
            cubic_tangs = [c.vi[i] if c.viabs[i] > 0 else None for i in range(1, len(path) - 1)]
            if c.viabs[0] > 0:
                g.edges[path[0], path[1]]["data"]["tangent0"] = (c.vi[0] * (x[1] - x[0])).toArray()
            if c.viabs[-1] > 0:
                g.edges[path[-1], path[-2]]["data"]["tangent1"] = (c.vi[-1] * (x[-1] - x[-2])).toArray()
            for angle in [
                Vec2.angle(c.vi[0], y[1] - y[0]),
                Vec2.angle(c.vi[-1], y[-1] - y[-2])]:
                if angle > warnangle / 180 * pi:
                    print(f"WARNING start/end node {path[0]} Diff tang angle: {angle * 180 / pi:.3f}")
        for i, n0, n1, n2 in zip(range(1, len(path) - 1), path[:-2], path[1:-1], path[2:]):
            p0 = g.nodes[n0]["pos"]
            p1 = g.nodes[n1]["pos"]
            p2 = g.nodes[n2]["pos"]
            t01 = p1 - p0
            t12 = p2 - p1
            e01 = g.edges[n0, n1]["data"]
            e12 = g.edges[n1, n2]["data"]
            etype = (e01['street'] and 'street(' + e01['street']['type'] or 'track(' + e01['track']['type']) + ")"
            if Vec2.angle(t01, t12) < maxangle / 180 * pi:
                if method == "finite_difference":  # https://en.wikipedia.org/wiki/Cubic_Hermite_spline
                    tang = (t01.normalize() + t12.normalize()) / 2
                elif method == "Catmull–Rom":
                    tang = (p2 - p0) / 2
                elif method == "natural":
                    tang = cubic_tangs[i - 1]
                    if not tang:
                        continue
                    if not .7 < tang.length() < 1.5:
                        print(f"WARNING: at {n1} spline tang length {tang}")
                    maxerr = cerr.maxerr_at_node(i)
                    if e01['street'] and maxerr > 8 or e01['track'] and maxerr > 15:
                        print(f"WARNING Spline maxerr: {maxerr:.3f} at {n1} {etype}")
                        if e01['street']:
                            continue  # skip to use straight tangent
                else:
                    raise Exception("Unknown tangent method: " + method)
                for angle in [Vec2.angle(tang, t01), Vec2.angle(tang, t12)]:
                    if angle > warnangle / 180 * pi:
                        print(f"WARNING Diff tang angle: {angle * 180 / pi:.3f} at {n1} {etype}")
                if method in {"finite_difference", "Catmull–Rom"}:
                    l01 = approx_length_arc(t01.length(), Vec2.angle(t01, tang))
                    l12 = approx_length_arc(t12.length(), Vec2.angle(t12, tang))
                    e01["tangent1"] = tang.normalize(l01).toArray()
                    e12["tangent0"] = tang.normalize(l12).toArray()
                elif method in {"natural"}:  # cubic spline was initialized with x (linear length)
                    e01["tangent1"] = (tang * t01.length()).toArray()
                    e12["tangent0"] = (tang * t12.length()).toArray()
            else:
                print(f"Edges({n0},{n1},{n2}) above maxangle {Vec2.angle(t01, t12) * 180 / pi}")


def add_path_info_to_nodes(paths, nodes, prefix):
    for path in paths:
        for n0, n1, n2 in zip(path[:-2], path[1:-1], path[2:]):
            if f"path_{prefix}" not in nodes[n1]:
                nodes[n1][f"path_{prefix}"] = []
            nodes[n1][f"path_{prefix}"].append([n0, n2])


def align_switches_tangents(g, gt, nodes, maxangle):
    switches = set(n for n in gt.nodes if gt.degree(n) == 3)
    for zwitch in switches:
        if "path_track" in nodes[zwitch]:
            path = nodes[zwitch]["path_track"][0]
            if "tangent1" not in g.edges[zwitch, path[0]]["data"] or "tangent0" not in g.edges[zwitch, path[1]]["data"]:
                continue
            assert Vec2.angle(Vec2(g.edges[zwitch, path[0]]["data"]["tangent1"]),
                              Vec2(g.edges[zwitch, path[1]]["data"]["tangent0"])) < 0.01, zwitch
            tang = Vec2(g.edges[zwitch, path[0]]["data"]["tangent1"]).normalize()
            # cant use gt, is outdated after node removal
            neighbors = {n for n in g.neighbors(zwitch) if g.edges[zwitch, n]["data"]["track"]}
            assert len(neighbors) == 3, zwitch
            third_node = (neighbors - set(path)).pop()
            assert g.has_edge(zwitch, third_node), f"no third edge {zwitch}"
            sw_edge = g.edges[zwitch, third_node]
            if sw_edge["data"]["node0"] == zwitch:
                tangent01 = "tangent0"
            else:
                assert sw_edge["data"]["node1"] == zwitch
                tangent01 = "tangent1"
            if tangent01 not in sw_edge["data"]:  # no path on the switch side, e.g. next node is another switch
                sw_tang = g.nodes[sw_edge["data"]["node1"]]["pos"] - g.nodes[sw_edge["data"]["node0"]]["pos"]
            else:
                sw_tang = Vec2(sw_edge["data"][tangent01])
            angle = Vec2.angle(tang, sw_tang)
            if angle * 180 / pi < maxangle:
                print(
                    f"Align tangents of Path({zwitch},{path[1] if tangent01 == 'tangent0' else path[0]}) and Switch({zwitch},{third_node})")
                sw_edge["data"][tangent01] = tang.normalize(sw_tang.length()).toArray()
            elif angle * 180 / pi > 180 - maxangle:
                print(
                    f"Align tangents of Path({zwitch},{path[1] if tangent01 == 'tangent1' else path[0]}) and Switch({zwitch},{third_node})")
                sw_edge["data"][tangent01] = (-tang).normalize(sw_tang.length()).toArray()
            else:
                print(f"Angle of switch {zwitch} too large: {angle * 180 / pi}")
        else:
            pass  # TODO align tangents of different ways heuristacally


def adjust_signals(nodes, g):
    for nid, node in nodes.items():
        if node.get("signal") and not node.get("removed"):
            if "path_track" in node:
                if len(node["path_track"]) == 1:  # assume 1 path only
                    edge = g.edges[nid, node["path_track"][0][0]]  # predecessor
                    # place signal on edge before because of Signal Distance and so that signals are right in front of poles
                    if edge["data"].get("nodes_reversed"):
                        node["signal"]["direction_backward"] = not node["signal"]["direction_backward"]
                    if node["signal"]["direction_backward"]:  # need to place on edge after, before pole
                        edge = g.edges[nid, node["path_track"][0][1]]  # successor
                    edge["data"]["objects"] = {"signal": node["signal"]}
                    node["signal"] = False
                else:
                    print("WARNING: signal on more than 1 path", nid, node)
            else:
                print(f"Node {nid} signal but no path info")
