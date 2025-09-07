_registry = {}

def site(key, url):
    def deco(fn):
        _registry[key] = (url, fn)
        return fn
    return deco

def all_sites():
    return _registry.items()
