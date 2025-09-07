# scraper/sites/__init__.py
"""
Inicializador del paquete `sites`.

- Importa los módulos que definen sitios y se autoregistran con
  @registry.site(...).
- Expone `all_sites()` para que `main.py` pueda iterar sobre ellos.
"""

from . import registry

# IMPORTANTE: importa aquí cada módulo que define sitios para que se registren
from . import loteriasdominicanas  # noqa: F401

def all_sites():
    """
    Devuelve un iterable de (key, (url, fn)) como espera `main.py`.
    """
    return list(registry._registry.items())
