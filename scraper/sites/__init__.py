# scraper/sites/__init__.py
from . import registry

# Importa módulos que registran sitios (side effect del decorador)
from . import loteriasdominicanas  # noqa: F401

def all_sites():
    # Usa la función pública del registro (no el atributo interno)
    return list(registry.all_sites())
