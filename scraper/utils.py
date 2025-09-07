import re
from bs4 import BeautifulSoup

# Expresión regular para detectar listas de números (ej. "73 06 37")
RE_NUMS_LIST = re.compile(r'(?:\d{2}\s+){1,20}\d{2}')

def find_after_label(soup: BeautifulSoup, label_text: str):
    """
    Busca un texto 'label_text' y captura números cercanos (mismo bloque / vecinos).
    """
    labels = [el for el in soup.find_all(text=True) if label_text.lower() in el.lower()]
    for t in labels:
        # Contenedor directo
        cand = " ".join(t.parent.get_text(" ", strip=True).split())
        m = RE_NUMS_LIST.search(cand)
        if m: return m.group(0)
        # Hermanos cercanos
        node = t.parent
        for sib in list(node.next_siblings)[:3]:
            txt = getattr(sib, "get_text", lambda **k: str(sib))(" ", strip=True)
            m = RE_NUMS_LIST.search(txt)
            if m: return m.group(0)
        # Padre
        par = node.parent
        if par:
            txt = par.get_text(" ", strip=True)
            m = RE_NUMS_LIST.search(txt)
            if m: return m.group(0)
    return None

def split_numbers(s: str):
    """
    Divide un string en números individuales de dos dígitos.
    Ejemplo: "73 6 37" -> ["73","06","37"]
    """
    return [n.zfill(2) for n in s.split() if n.isdigit()]
