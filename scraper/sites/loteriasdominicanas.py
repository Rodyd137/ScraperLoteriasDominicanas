import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from . import registry
from ..schema import Draw
from ..utils import find_after_label, split_numbers

BASE = "https://loteriasdominicanas.com"
RD_TZ = ZoneInfo("America/Santo_Domingo")

def today_rd():
    return datetime.now(RD_TZ).date().isoformat()

@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    r = requests.get(f"{BASE}/la-primera", timeout=30, headers={"User-Agent":"RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out = []
    map_labels = [
        ("Quiniela", "La Primera Día", "Día"),
        ("Quiniela", "La Primera Noche", "Noche"),
        ("El Quinielón", "El Quinielón Día", "Día"),
        ("El Quinielón", "El Quinielón Noche", "Noche"),
        ("Loto 5", "Loto 5", None),
    ]
    for game, label, edition in map_labels:
        s = find_after_label(soup, label)
        if s:
            out.append(Draw(provider="La Primera", game=game, edition=edition, date=d, numbers=split_numbers(s)))
    return out

@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    r = requests.get(f"{BASE}/leidsa", timeout=30, headers={"User-Agent":"RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out = []
    map_labels = [
        ("Pega 3 Más", "Pega 3 Más", None),
        ("Quiniela", "Quiniela Leidsa", None),
        ("Loto Pool", "Loto Pool", None),
        ("Super Kino TV", "Super Kino TV", None),
        ("Loto - Super Loto Más", "Loto - Super Loto Más", None),
        ("Super Palé", "Super Palé", None),
    ]
    for game, label, edition in map_labels:
        s = find_after_label(soup, label)
        if s:
            out.append(Draw(provider="Leidsa", game=game, edition=edition, date=d, numbers=split_numbers(s)))
    return out

@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    r = requests.get(f"{BASE}/loteria-nacional", timeout=30, headers={"User-Agent":"RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out = []
    map_labels = [
        ("Gana Más", "Gana Más", None),
        ("Quiniela Nacional", "Lotería Nacional", None),
        ("La Fecha", "La Fecha", None),
    ]
    for game, label, edition in map_labels:
        s = find_after_label(soup, label)
        if s:
            out.append(Draw(provider="Lotería Nacional", game=game, edition=edition, date=d, numbers=split_numbers(s)))
    return out
