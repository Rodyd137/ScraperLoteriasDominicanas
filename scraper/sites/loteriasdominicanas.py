import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from zoneinfo import ZoneInfo
import re

from . import registry
from ..schema import Draw, slugify

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

PROV = {
    "La Primera": "la-primera",
    "Leidsa": "leidsa",
    "Lotería Nacional": "loteria-nacional",
    "Lotería Real": "loteria-real",
    "Loteka": "loteka",
    "LoteDom": "lotedom",
    "La Suerte Dominicana": "la-suerte-dominicana",
    "Florida": "florida",
    "New York": "nueva-york",
    "Americanas": "americanas",
    "Anguila": "anguila",
    "King Lottery": "king-lottery",
}

def today_rd() -> str:
    return datetime.now(RD_TZ).date().isoformat()

def _norm(s: str) -> str:
    return " ".join(s.replace("\u00a0", " ").split())

def _fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def _extract_cards(soup: BeautifulSoup):
    return soup.select(".game-block")

def _extract_title(card) -> str | None:
    el = card.select_one(".game-title span")
    return _norm(el.get_text(" ", strip=True)) if el else None

def _extract_numbers(card) -> list[str]:
    nums = []
    for s in card.select(".game-scores .score"):
        t = s.get_text(strip=True)
        # ignora "2X", etc.
        if t.isdigit():
            nums.append(t.zfill(2))
    return nums

# ---------- NUEVO: lectura de fecha base (con año) desde la página ----------
_RE_PAGE_TODAY = re.compile(r"today\s*:\s*'(\d{2}-\d{2}-\d{4})'")

def _page_base_date(soup: BeautifulSoup) -> date | None:
    """
    Busca en los <script> el fragmento: today: 'dd-mm-yyyy'
    y devuelve datetime.date(yyyy, mm, dd)
    """
    for s in soup.find_all("script"):
        txt = (s.string or s.get_text()) or ""
        m = _RE_PAGE_TODAY.search(txt)
        if m:
            dd, mm, yy = m.group(1).split("-")
            return date(int(yy), int(mm), int(dd))
    return None

# ---------- NUEVO: extracción de dd-mm del card y armado de yyyy-mm-dd ----------
_RE_DDMM = re.compile(r"\b([0-3]?\d)[\-/\.]([01]?\d)\b")

def _extract_card_date(card, year_base: int) -> str | None:
    """
    Lee '06-09' desde elementos típicos del card y lo convierte a 'YYYY-MM-DD'
    usando year_base. Hace un ajuste simple para cruces de año (enero/12).
    """
    cands = card.select(".session-date, .game-date, .badge, .date")
    texts = [(" ".join((el.get_text(" ", strip=True) or "").split())) for el in cands if el]
    if not texts:
        texts = [(" ".join((card.get_text(" ", strip=True) or "").split()))]

    for t in texts:
        m = _RE_DDMM.search(t)
        if not m:
            continue
        dd, mm = int(m.group(1)), int(m.group(2))
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            yy = year_base
            # si estamos en enero y el card dice 12 (diciembre), asume año anterior
            today = datetime.now(RD_TZ).date()
            if today.month == 1 and mm == 12 and year_base == today.year:
                yy -= 1
            return f"{yy:04d}-{mm:02d}-{dd:02d}"
    return None

# ---------- Constructor de Draws desde los cards ----------
def _build_from_cards(
    soup: BeautifulSoup,
    provider: str,
    title_map: dict[str, tuple[str, str | None]],
    game_slug_overrides: dict[str, str] | None = None,
) -> list[Draw]:
    """
    title_map: { 'La Primera Día': ('Quiniela', 'Día'), ... }
    game_slug_overrides: {'El Quinielón': 'quinielon'}  # opcional

    Cards whose title isn't in title_map are skipped with a debug log so
    we can see — in the GitHub Actions output — which fresh sorteos the
    upstream site started publishing that we haven't mapped yet.
    """
    # Año base de la página; si no se encuentra, usa fecha de RD
    base = _page_base_date(soup) or datetime.now(RD_TZ).date()
    base_year = base.year

    out: list[Draw] = []
    provider_id = PROV.get(provider, slugify(provider))
    unmatched_titles: list[str] = []

    for card in _extract_cards(soup):
        title = _extract_title(card)
        if not title:
            continue

        # Tolerar pequeñas variantes en títulos
        original_title = title
        if title not in title_map:
            t2 = title.replace("Mediodía", "Medio Día").replace("Dia", "Día")
            if t2 not in title_map:
                unmatched_titles.append(original_title)
                continue
            title = t2

        game, edition = title_map[title]
        nums = _extract_numbers(card)
        if not nums:
            continue

        game_id = (game_slug_overrides or {}).get(game) or slugify(game)

        # Fecha real del sorteo desde el card; fallback al base
        d = _extract_card_date(card, base_year) or base.isoformat()

        out.append(
            Draw(
                provider=provider,
                game=game,
                edition=edition,
                date=d,
                numbers=nums,
                provider_id=provider_id,
                game_id=game_id,
            )
        )

    if unmatched_titles:
        print(f"[UNMATCHED][{provider}] {unmatched_titles}")
    return out

# ----------------- LA PRIMERA -----------------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    soup = _fetch_soup(f"{BASE}/la-primera")
    # Upstream switched "La Primera Día" → "Quiniela Medio Día" and
    # "Primera Noche" → "Quiniela Noche". Keep the old labels as a
    # transition fallback so we don't lose draws if the site rolls back.
    title_map = {
        # Current upstream labels
        "Quiniela Medio Día": ("Quiniela", "Medio Día"),
        "Quiniela Mediodía": ("Quiniela", "Medio Día"),
        "Quiniela Noche": ("Quiniela", "Noche"),
        # Old labels (kept as fallback)
        "La Primera Día": ("Quiniela", "Medio Día"),
        "Primera Noche": ("Quiniela", "Noche"),
        # Quinielón
        "El Quinielón Día": ("El Quinielón", "Día"),
        "El Quinielón Noche": ("El Quinielón", "Noche"),
        # Loto 5
        "Loto 5": ("Loto 5", None),
    }
    overrides = {"El Quinielón": "quinielon"}
    draws = _build_from_cards(soup, "La Primera", title_map, overrides)
    print("[DEBUG][La Primera] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- LEIDSA -----------------
@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    soup = _fetch_soup(f"{BASE}/leidsa")
    title_map = {
        "Pega 3 Más": ("Pega 3 Más", None),
        "Quiniela Leidsa": ("Quiniela", None),
        "Quiniela Palé": ("Quiniela Palé", None),
        "Quiniela Pale": ("Quiniela Palé", None),
        "Loto Pool": ("Loto Pool", None),
        "Super Kino TV": ("Super Kino TV", None),
        # Upstream now shows "Loto Más"; kept old label for transition.
        "Loto Más": ("Loto Más", None),
        "Loto Mas": ("Loto Más", None),
        "Loto - Super Loto Más": ("Loto Más", None),
        "Súper Palé": ("Súper Palé", None),
        "Super Pale": ("Súper Palé", None),
        "Super Palé": ("Súper Palé", None),
    }
    draws = _build_from_cards(soup, "Leidsa", title_map)
    print("[DEBUG][Leidsa] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- LOTERÍA NACIONAL -----------------
@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    soup = _fetch_soup(f"{BASE}/loteria-nacional")
    title_map = {
        "Juega + Pega +": ("Juega + Pega +", None),
        "Juega Más Pega Más": ("Juega + Pega +", None),
        "Gana Más": ("Gana Más", None),
        "Quiniela": ("Quiniela", None),
        "Quiniela Nacional": ("Quiniela", None),
        "Lotería Nacional": ("Lotería Nacional", None),
        "Billetes Domingo": ("Billetes Domingo", None),
    }
    draws = _build_from_cards(soup, "Lotería Nacional", title_map)
    print("[DEBUG][Nacional] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- Lotería Real -----------------
@registry.site("real", f"{BASE}/loto-real")
def scrape_real():
    soup = _fetch_soup(f"{BASE}/loto-real")
    title_map = {
        "Quiniela Real": ("Quiniela", None),
        "Quinielita Real": ("Quinielita", None),
        "Quinielita": ("Quinielita", None),
        "Loto Real": ("Loto Real", None),
        "Loto": ("Loto", None),
        "Loto Pool": ("Loto Pool", "Día"),
        "Loto Pool Día": ("Loto Pool", "Día"),
        "Loto Pool Noche": ("Loto Pool", "Noche"),
        "Chance Real": ("Chance Real", None),
        "Nueva Yol Real": ("Nueva Yol Real", None),
        "Pega 4": ("Pega 4", None),
        "Repartidera Real": ("Repartidera Real", None),
        "Repartidera": ("Repartidera Real", None),
        "Súper Palé": ("Súper Palé", None),
        "Super Pale": ("Súper Palé", None),
        "Super Palé": ("Súper Palé", None),
    }
    draws = _build_from_cards(soup, "Lotería Real", title_map)
    print("[DEBUG][Real] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- Loteka -----------------
@registry.site("loteka", f"{BASE}/loteka")
def scrape_loteka():
    soup = _fetch_soup(f"{BASE}/loteka")
    title_map = {
        "Quiniela Loteka": ("Quiniela", None),
        "Mega Chances": ("Mega Chances", None),
        "Repartidera": ("Mega Chances Repartidera", None),
        "MegaLotto": ("MegaLotto", None),
        "Mega Lotto": ("MegaLotto", None),
        "Toca 3": ("Toca 3", None),
        "Quiniela Mega Decenas": ("Quiniela Mega Decenas", None),
        "Mega Decenas": ("Quiniela Mega Decenas", None),
    }
    draws = _build_from_cards(soup, "Loteka", title_map)
    print("[DEBUG][Loteka] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- LoteDom (El Quemaito Mayor) -----------------
@registry.site("lotedom", f"{BASE}/lotedom")
def scrape_lotedom():
    soup = _fetch_soup(f"{BASE}/lotedom")
    title_map = {
        "Quiniela LoteDom": ("Quiniela", None),
        "El Quemaito Mayor": ("El Quemaito Mayor", None),
        "Agarra 4": ("Agarra 4", None),
        "Súper Palé": ("Súper Palé", None),
        "Super Pale": ("Súper Palé", None),
        "Super Palé": ("Súper Palé", None),
    }
    draws = _build_from_cards(soup, "LoteDom", title_map, {"El Quemaito Mayor": "quemaito-mayor"})
    print("[DEBUG][LoteDom] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- La Suerte Dominicana -----------------
@registry.site("la_suerte", f"{BASE}/la-suerte-dominicana")
def scrape_la_suerte():
    soup = _fetch_soup(f"{BASE}/la-suerte-dominicana")
    # Upstream switched from time labels (12:30 / 18:00) to Día / Tarde.
    # Keep both so a card with the old label still maps cleanly.
    title_map = {
        # Current upstream
        "Quiniela": ("La Suerte", "Día"),
        "Quiniela La Suerte": ("La Suerte", "Día"),
        "Quiniela Tarde": ("La Suerte", "Tarde"),
        "La Suerte Tarde": ("La Suerte", "Tarde"),
        # Old time-based labels kept as fallback
        "La Suerte 12:30": ("La Suerte", "Día"),
        "La Suerte 18:00": ("La Suerte", "Tarde"),
    }
    draws = _build_from_cards(soup, "La Suerte Dominicana", title_map)
    print("[DEBUG][La Suerte] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
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
    print("[DEBUG][Florida] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
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
    print("[DEBUG][New York] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- Americanas -----------------
@registry.site("americanas", f"{BASE}/americanas")
def scrape_americanas():
    soup = _fetch_soup(f"{BASE}/americanas")
    title_map = {
        "PowerBall": ("PowerBall", None),
        "Powerball": ("PowerBall", None),
        "PowerBall Double Play": ("PowerBall Double Play", None),
        "Powerball Double Play": ("PowerBall Double Play", None),
        "Mega Millions": ("Mega Millions", None),
        "Cash 4 Life": ("Cash 4 Life", None),
        # Florida y NY ahora se publican dentro de "Americanas" (la fuente
        # consolidó). Mantener las páginas dedicadas (scrape_florida /
        # scrape_nueva_york) como fallback.
        "Florida Tarde": ("Florida", "Tarde"),
        "Florida Noche": ("Florida", "Noche"),
        "New York Medio Día": ("New York", "Medio Día"),
        "New York Mediodía": ("New York", "Medio Día"),
        "New York Noche": ("New York", "Noche"),
    }
    draws = _build_from_cards(soup, "Americanas", title_map)
    print("[DEBUG][Americanas] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
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
        # Cuarteta editions (4-number pick game tied to Anguila)
        "La Cuarteta Mañana": ("Cuarteta", "Mañana"),
        "Cuarteta Mañana": ("Cuarteta", "Mañana"),
        "Cuarteta Medio Día": ("Cuarteta", "Medio Día"),
        "Cuarteta Mediodía": ("Cuarteta", "Medio Día"),
        "Cuarteta Tarde": ("Cuarteta", "Tarde"),
        "Cuarteta Noche": ("Cuarteta", "Noche"),
    }
    draws = _build_from_cards(soup, "Anguila", title_map)
    print("[DEBUG][Anguila] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws

# ----------------- King Lottery -----------------
@registry.site("king_lottery", f"{BASE}/king-lottery")
def scrape_king_lottery():
    soup = _fetch_soup(f"{BASE}/king-lottery")
    # Upstream renamed the King Lottery editions from time-of-day labels
    # ("12:30", "7:30") to "Día" / "Noche". Keep BOTH so we catch the
    # cards either way the site decides to format them.
    title_map = {
        # New (current) — Quiniela
        "Quiniela King": ("Quiniela", "Día"),
        "King Lottery Día": ("Quiniela", "Día"),
        "Quiniela King Noche": ("Quiniela", "Noche"),
        "King Lottery Noche": ("Quiniela", "Noche"),
        # Old labels kept as fallback during the upstream transition
        "King Lottery 12:30": ("Quiniela", "Día"),
        "King Lottery 7:30": ("Quiniela", "Noche"),
        # Pick games
        "Pick 3 Día": ("Pick 3", "Día"),
        "Pick 3 Noche": ("Pick 3", "Noche"),
        "Pick 4 Día": ("Pick 4", "Día"),
        "Pick 4 Noche": ("Pick 4", "Noche"),
        # Loto Pool
        "Loto Pool Medio Día": ("Loto Pool", "Medio Día"),
        "Loto Pool Mediodía": ("Loto Pool", "Medio Día"),
        "Loto Pool Noche": ("Loto Pool", "Noche"),
        # Philipsburg
        "Philipsburg Medio Día": ("Philipsburg", "Medio Día"),
        "Philipsburg Mediodía": ("Philipsburg", "Medio Día"),
        "Philipsburg Noche": ("Philipsburg", "Noche"),
    }
    draws = _build_from_cards(soup, "King Lottery", title_map)
    print("[DEBUG][King Lottery] encontrados:", [(d.game, d.edition, d.numbers, d.date) for d in draws])
    return draws
