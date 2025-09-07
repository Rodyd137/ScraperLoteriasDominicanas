import os, requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from . import registry
from ..schema import Draw
from ..utils import find_after_label, split_numbers  # aún se usa para otras páginas

BASE = "https://loteriasdominicanas.com"
RD_TZ = ZoneInfo("America/Santo_Domingo")

def today_rd():
    return datetime.now(RD_TZ).date().isoformat()

# ---------- LA PRIMERA (parser por tarjetas) ----------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    """
    Parser basado en tarjetas del DOM real:
    - contenedor: .game-block
    - título: .game-title span  (ej: "La Primera Día", "Primera Noche", "El Quinielón Día", "Loto 5")
    - números: .game-scores .score (varios span)
    - fecha en DOM es "dd-mm"; usamos today_rd() para ISO con año.
    """
    url = f"{BASE}/la-primera"
    r = requests.get(url, timeout=30, headers={"User-Agent": "RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out: list[Draw] = []

    def map_title(title: str):
        t = title.strip()
        if t == "La Primera Día":
            return ("Quiniela", "Día")
        if t == "Primera Noche":        # ojo: sin "La"
            return ("Quiniela", "Noche")
        if t == "El Quinielón Día":
            return ("El Quinielón", "Día")
        if t == "El Quinielón Noche":
            return ("El Quinielón", "Noche")
        if t == "Loto 5":
            return ("Loto 5", None)
        return (None, None)

    # Recorremos cada tarjeta:
    for card in soup.select(".game-block"):
        title_el = card.select_one(".game-title span")
        if not title_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        game, edition = map_title(title)
        if not game:
            continue

        # Extrae números
        nums = []
        for s in card.select(".game-scores .score"):
            txt = s.get_text(strip=True)
            if txt.isdigit():
                nums.append(txt.zfill(2))
        if not nums:
            # nada que registrar en esta tarjeta
            continue

        out.append(Draw(
            provider="La Primera",
            game=game,
            edition=edition,
            date=d,
            numbers=nums
        ))

    # DEBUG útil en consola
    print("[DEBUG][La Primera] títulos encontrados:", [(" ".join(c.select_one(".game-title span").get_text(" ", strip=True).split())) for c in soup.select(".game-block") if c.select_one(".game-title span")])
    print("[DEBUG][La Primera] draws:", [(dr.game, dr.edition, dr.numbers) for dr in out])
    return out

# ---------- LEIDSA (mantenemos por ahora; luego lo ajusto igual con su HTML) ----------
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
    print("[DEBUG][Leidsa] draws:", [(dr.game, dr.numbers) for dr in out])
    return out

# ---------- NACIONAL (mantenemos por ahora; luego lo ajusto igual con su HTML) ----------
@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    r = requests.get(f"{BASE}/loteria-nacional", timeout=30, headers={"User-Agent":"RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out = []
    map_labels = [
        ("Juega + Pega +", "Juega + Pega +", None),
        ("Gana Más", "Gana Más", None),
        ("Lotería Nacional", "Lotería Nacional", None),
    ]
    for game, label, edition in map_labels:
        s = find_after_label(soup, label)
        if s:
            out.append(Draw(provider="Lotería Nacional", game=game, edition=edition, date=d, numbers=split_numbers(s)))
    print("[DEBUG][Nacional] draws:", [(dr.game, dr.numbers) for dr in out])
    return out
