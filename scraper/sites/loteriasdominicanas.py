# scraper/sites/loteriasdominicanas.py
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from zoneinfo import ZoneInfo

from . import registry
from ..schema import Draw

BASE = "https://loteriasdominicanas.com"
RD_TZ = ZoneInfo("America/Santo_Domingo")

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/127.0"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://loteriasdominicanas.com/",
}

def today_rd() -> str:
    return datetime.now(RD_TZ).date().isoformat()

def _norm_ws(s: str) -> str:
    return " ".join((s or "").replace("\u00a0", " ").split())

def _fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _extract_cards(soup: BeautifulSoup):
    return soup.select(".game-block")

def _extract_title(card) -> str | None:
    el = card.select_one(".game-title span")
    return _norm_ws(el.get_text(" ", strip=True)) if el else None

def _extract_numbers(card) -> list[str]:
    nums = []
    for s in card.select(".game-scores .score"):
        t = s.get_text(strip=True)
        if t.isdigit():
            nums.append(t.zfill(2))
    return nums

# ----------- NUEVO: fecha por tarjeta (badge tipo 08-09) -----------
_ddmm = re.compile(r"\b([0-3]?\d)[\-/\.]([01]?\d)\b")

def _extract_card_date(card) -> str | None:
    """
    Busca dentro de la tarjeta un patrón dd-mm / dd/mm / dd.mm y
    lo convierte a ISO (YYYY-MM-DD) usando el año actual en RD.
    """
    # 1) Intentos con selectores "típicos" de badge
    candidates = card.select(
        ".game-header .badge, .game-header .date, .game-date, .date, .badge"
    )
    texts = []
    for el in candidates:
        txt = _norm_ws(el.get_text(" ", strip=True))
        if txt:
            texts.append(txt)

    # 2) Fallback: todo el texto de la tarjeta (limitado)
    if not texts:
        texts = [_norm_ws(card.get_text(" ", strip=True))[:64]]

    # 3) Busca el primer dd-mm plausible
    today = datetime.now(RD_TZ).date()
    for txt in texts:
        m = _ddmm.search(txt)
        if not m:
            continue
        dd = int(m.group(1))
        mm = int(m.group(2))
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            yy = today.year
            # pequeño ajuste de cambio de año (enero mostrando dic)
            if today.month == 1 and mm == 12:
                yy -= 1
            try:
                return date(yy, mm, dd).isoformat()
            except ValueError:
                pass
    return None

def _build_from_cards(
    soup: BeautifulSoup,
    provider: str,
    title_map: dict[str, tuple[str, str | None]],
) -> list[Draw]:
    """
    title_map: { 'La Primera Día': ('Quiniela', 'Día'), ... }
    """
    out: list[Draw] = []
    for card in _extract_cards(soup):
        title = _extract_title(card)
        if not title:
            continue

        # tolera “Mediodía” vs “Medio Día”, “Dia” vs “Día”
        if title not in title_map:
            t2 = title.replace("Mediodía", "Medio Día").replace("Dia", "Día")
            if t2 not in title_map:
                continue
            title = t2

        game, edition = title_map[title]
        nums = _extract_numbers(card)
        if not nums:
            continue

        # <<< aquí tomamos la fecha real del card >>>
        d = _extract_card_date(card) or today_rd()

        out.append(
            Draw(
                provider=provider,
                game=game,
                edition=edition,
                date=d,
                numbers=nums,
            )
        )
    return out

# ----------------- LA PRIMERA -----------------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    soup = _fetch_soup(f"{BASE}/la-primera")
    title_map = {
        "La Primera Día": ("Quiniela", "Día"),
        "Primera Noche": ("Quiniela", "Noche"),
        "El Quinielón Día": ("El Quinielón", "Día"),
        "El Quinielón Noche": ("El Quinielón", "Noche"),
        "Loto 5": ("Loto 5", None),
    }
    draws = _build_from_cards(soup, "La Primera", title_map)
    print("[DEBUG][La Primera] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- LEIDSA -----------------
@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    soup = _fetch_soup(f"{BASE}/leidsa")
    title_map = {
        "Pega 3 Más": ("Pega 3 Más", None),
        "Quiniela Leidsa": ("Quiniela", None),
        "Loto Pool": ("Loto Pool", None),
        "Super Kino TV": ("Super Kino TV", None),
        "Loto - Super Loto Más": ("Loto - Super Loto Más", None),
        "Super Palé": ("Super Palé", None),
    }
    draws = _build_from_cards(soup, "Leidsa", title_map)
    print("[DEBUG][Leidsa] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- LOTERÍA NACIONAL -----------------
@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    soup = _fetch_soup(f"{BASE}/loteria-nacional")
    title_map = {
        "Juega + Pega +": ("Juega + Pega +", None),
        "Gana Más": ("Gana Más", None),
        "Lotería Nacional": ("Lotería Nacional", None),
    }
    draws = _build_from_cards(soup, "Lotería Nacional", title_map)
    print("[DEBUG][Nacional] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Lotería Real -----------------
@registry.site("real", f"{BASE}/loto-real")
def scrape_real():
    soup = _fetch_soup(f"{BASE}/loto-real")
    title_map = {
        "Quiniela Real": ("Quiniela", None),
        "Loto Real": ("Loto Real", None),
    }
    draws = _build_from_cards(soup, "Lotería Real", title_map)
    print("[DEBUG][Real] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Loteka -----------------
@registry.site("loteka", f"{BASE}/loteka")
def scrape_loteka():
    soup = _fetch_soup(f"{BASE}/loteka")
    title_map = {
        "Quiniela Loteka": ("Quiniela", None),
        "Mega Chances": ("Mega Chances", None),
    }
    draws = _build_from_cards(soup, "Loteka", title_map)
    print("[DEBUG][Loteka] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- LoteDom (El Quemaito Mayor) -----------------
@registry.site("lotedom", f"{BASE}/lotedom")
def scrape_lotedom():
    soup = _fetch_soup(f"{BASE}/lotedom")
    title_map = {
        "Quiniela LoteDom": ("Quiniela", None),
        "El Quemaito Mayor": ("El Quemaito Mayor", None),
    }
    draws = _build_from_cards(soup, "LoteDom", title_map)
    print("[DEBUG][LoteDom] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- La Suerte Dominicana -----------------
@registry.site("la_suerte", f"{BASE}/la-suerte-dominicana")
def scrape_la_suerte():
    soup = _fetch_soup(f"{BASE}/la-suerte-dominicana")
    title_map = {
        "La Suerte 12:30": ("La Suerte", "12:30"),
        "La Suerte 18:00": ("La Suerte", "18:00"),
    }
    draws = _build_from_cards(soup, "La Suerte Dominicana", title_map)
    print("[DEBUG][La Suerte] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Florida -----------------
@registry.site("florida", f"{BASE}/loteria-de-florida")
def scrape_florida():
    soup = _fetch_soup(f"{BASE}/loteria-de-florida")
    title_map = {
        "Florida Día": ("Florida", "Día"),
        "Florida Tarde": ("Florida", "Tarde"),
        "Florida Noche": ("Florida", "Noche"),
    }
    draws = _build_from_cards(soup, "Florida", title_map)
    print("[DEBUG][Florida] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Nueva York -----------------
@registry.site("nueva_york", f"{BASE}/nueva-york")
def scrape_nueva_york():
    soup = _fetch_soup(f"{BASE}/nueva-york")
    title_map = {
        "New York Día": ("New York", "Día"),
        "New York Tarde": ("New York", "Tarde"),
        "New York Noche": ("New York", "Noche"),
    }
    draws = _build_from_cards(soup, "New York", title_map)
    print("[DEBUG][New York] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Americanas -----------------
@registry.site("americanas", f"{BASE}/americanas")
def scrape_americanas():
    soup = _fetch_soup(f"{BASE}/americanas")
    title_map = {
        "PowerBall": ("PowerBall", None),
        "Mega Millions": ("Mega Millions", None),
        "Cash 4 Life": ("Cash 4 Life", None),
    }
    draws = _build_from_cards(soup, "Americanas", title_map)
    print("[DEBUG][Americanas] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- Anguila -----------------
@registry.site("anguila", f"{BASE}/anguila")
def scrape_anguila():
    soup = _fetch_soup(f"{BASE}/anguila")
    title_map = {
        "Anguila Mañana": ("Anguila", "Mañana"),
        "Anguila Medio Día": ("Anguila", "Medio Día"),
        "Anguila Tarde": ("Anguila", "Tarde"),
        "Anguila Noche": ("Anguila", "Noche"),
    }
    draws = _build_from_cards(soup, "Anguila", title_map)
    print("[DEBUG][Anguila] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

# ----------------- King Lottery -----------------
@registry.site("king_lottery", f"{BASE}/king-lottery")
def scrape_king_lottery():
    soup = _fetch_soup(f"{BASE}/king-lottery")
    title_map = {
        "King Lottery 12:30": ("King Lottery", "12:30"),
        "King Lottery 7:30": ("King Lottery", "7:30"),
    }
    draws = _build_from_cards(soup, "King Lottery", title_map)
    print("[DEBUG][King Lottery] encontrados:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws
