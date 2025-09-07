# Registro simple de sitios
sites: dict[str, tuple[str, callable]] = {}

def site(key: str, url: str):
    def deco(fn):
        sites[key] = (url, fn)
        return fn
    return deco
