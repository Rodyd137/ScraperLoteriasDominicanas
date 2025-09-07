import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

from . import registry
from ..schema import Draw

BASE = "https://loteriasdominicanas.com"
RD_TZ = ZoneInfo("America/Santo_Domingo")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://loteriasdominicanas.com/",
}

def today_rd() -> str:
    return datetime.now(RD_TZ).date().isoformat()

def _norm(s: str) -> str:
    # normaliza espacios y NBSP
    return " ".join(s.replace("\u00a0", " ").split())

def _extract_cards(soup: BeautifulSoup):
    return soup.select(".game-block")

def _extract_title(card) -> str | None:
    el = card.select_one(".game-title span")
    return _norm(el.get_text(" ", strip=True)) if el else None

def _extract_numbers(card) -> list[str]:
    nums = []
    for s in card.select(".game-scores .score"):
        t = s.get_text(strip=True)
        if t.isdigit():
            nums.append(t.zfill(2))
    return nums

def _fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _build_from_cards(soup: BeautifulSoup, provider: str, title_map: dict[str, tuple[str, str | None]]) -> list[Draw]:
    d = today_rd()
    out: list[Draw] = []
    for card in _extract_cards(soup):
        title = _extract_title(card)
        if not title:
            continue
        if title not in title_map:
            continue
        game, edition = title_map[title]
        nums = _extract_numbers(card)
        if not nums:
            continue
        out.append(Draw(provider=provider, game=game, edition=edition, date=d, numbers=nums))
    return out

# ----------------- LA PRIMERA -----------------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    """
    Parseo por tarjetas:
      - título: .game-title span (ej. 'La Primera Día', 'Primera Noche', 'El Quinielón Día', 'Loto 5')
      - números: .game-scores .score
    """
    url = f"{BASE}/la-primera"
    soup = _fetch_soup(url)

    title_map = {
        "La Primera Día": ("Quiniela", "Día"),
        "Primera Noche": ("Quiniela", "Noche"),        # en el DOM viene sin "La"
        "El Quinielón Día": ("El Quinielón", "Día"),
        "El Quinielón Noche": ("El Quinielón", "Noche"),
        "Loto 5": ("Loto 5", None),
    }

    draws = _build_from_cards(soup, "La Primera", title_map)
    print("[DEBUG][La Primera] encontrados:", [(d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- LEIDSA -----------------
@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    """
    Estructura de tarjetas equivalente. Cuando quieras, pásame el HTML
    para afinar títulos si cambian; por ahora mapeamos los visibles comunes.
    """
    url = f"{BASE}/leidsa"
    soup = _fetch_soup(url)

    title_map = {
        "Pega 3 Más": ("Pega 3 Más", None),
        "Quiniela Leidsa": ("Quiniela", None),
        "Loto Pool": ("Loto Pool", None),
        "Super Kino TV": ("Super Kino TV", None),
        "Loto - Super Loto Más": ("Loto - Super Loto Más", None),
        "Super Palé": ("Super Palé", None),
    }

    draws = _build_from_cards(soup, "Leidsa", title_map)
    print("[DEBUG][Leidsa] encontrados:", [(d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- LOTERÍA NACIONAL -----------------
@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    """
    Mismo patrón de tarjetas:
    - 'Juega + Pega +', 'Gana Más', 'Lotería Nacional'
    """
    url = f"{BASE}/loteria-nacional"
    soup = _fetch_soup(url)

    title_map = {
        "Juega + Pega +": ("Juega + Pega +", None),
        "Gana Más": ("Gana Más", None),
        "Lotería Nacional": ("Lotería Nacional", None),
    }

    draws = _build_from_cards(soup, "Lotería Nacional", title_map)
    print("[DEBUG][Nacional] encontrados:", [(d.game, d.edition, d.numbers) for d in draws])
    return draws
