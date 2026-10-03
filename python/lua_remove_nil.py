def lua_remove_nil(d):
    if type(d) is dict:
        e = dict()
        for k, v in d.items():
            if v is not None:
                e[k] = lua_remove_nil(v)
        return e
    elif type(d) is list:
        e = []
        for v in d:
            if v is not None:
                e.append(lua_remove_nil(v))
        return e
    else:
        return d


def drop_removed_nodes(data):
    """Drop graph nodes marked removed so they are not serialized into Lua."""
    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        return data
    removed = {k for k, v in nodes.items() if isinstance(v, dict) and v.get("removed")}
    if not removed:
        return data
    data["nodes"] = {k: v for k, v in nodes.items() if k not in removed}
    paths = data.get("paths")
    if isinstance(paths, dict):
        for name, plist in list(paths.items()):
            if not isinstance(plist, list):
                continue
            cleaned = []
            for path in plist:
                if isinstance(path, list):
                    cleaned.append([n for n in path if n not in removed])
                else:
                    cleaned.append(path)
            paths[name] = cleaned
    return data
