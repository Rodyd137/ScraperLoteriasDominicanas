from . import registry
from . import loteriasdominicanas  # noqa: F401

def all_sites():
    return list(registry._registry.items())
