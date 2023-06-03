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
