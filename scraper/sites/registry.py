# scraper/sites/registry.py
_registry = {}

def site(key, url):
    def deco(fn):
        _registry[key] = (url, fn)
        return fn
    return deco

def all_sites():
    # Devuelve iterable de (key, (url, fn))
    return _registry.items()
