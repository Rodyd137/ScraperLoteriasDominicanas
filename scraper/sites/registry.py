from typing import Callable, Dict, Tuple

_registry: Dict[str, Tuple[str, Callable]] = {}

def site(key: str, url: str):
    def deco(fn: Callable):
        _registry[key] = (url, fn)
        return fn
    return deco

def all_sites():
    return [(k, _registry[k]) for k in sorted(_registry)]
