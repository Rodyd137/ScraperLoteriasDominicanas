# scraper/sites/loteriasdominicanas.py
import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from zoneinfo import ZoneInfo

from . import registry
from ..schema import Draw

# ----------------- Config -----------------
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

# cloudscraper es opcional (bypass Cloudflare)
try:
    import cloudscraper  # type: ignore
except Exception:
    cloudscraper = None  # noqa: F401


# ----------------- Utils -----------------
def today_rd() -> str:
    return datetime.now(RD_TZ).date().isoformat()

def _norm_ws(s: str) -> str:
    return " ".join((s or "").replace("\u00a0", " ").split())

def _fetch_html(url: str) -> str:
    """
    Intenta usar cloudscraper; si no está o falla, usa requests.
    """
    if cloudscraper is not None:
        try:
            s = cloudscraper.create_scraper(
                browser={"browser": "chrome", "platform": "windows", "mobile": False}
            )
            r = s.get(url, timeout=30, headers=BROWSER_HEADERS)
            r.raise_for_status()
            return r.text
        except Exception:
            pass  # cae a requests
    r = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
    r.raise_for_status()
    return r.text

def _fetch_soup(url: str, dump_slug: str | None = None) -> BeautifulSoup:
    html = _fetch_html(url)
    if os.getenv("DEBUG") == "1" and dump_slug:
        os.makedirs("public/debug", exist_ok=True)
        with open(f"public/debug/{dump_slug}.html", "w", encoding="utf-8") as f:
            f.write(html)
    return BeautifulSoup(html, "lxml")

def _extract_cards(soup: BeautifulSoup):
    # selector principal; añade backups si cambian clases
    cards = soup.select(".game-block")
    if not cards:
        cards = soup.select(".game-item, .lottery-card, .card")  # fallbacks suaves
    return cards

def _extract_title(card) -> str | None:
    el = card.select_one(".game-title span") or card.select_one(".game-title")
    return _norm_ws(el.get_text(" ", strip=True)) if el else None

def _extract_numbers(card) -> list[str]:
    nums = []
    for s in card.select(".game-scores .score, .scores .score, .score"):
        t = s.get_text(strip=True)
        if t.isdigit():
            nums.append(t.zfill(2))
    return nums

# --- Fecha por tarjeta (badge tipo 08-09 / 8/9 / 8.9) ---
_ddmm = re.compile(r"\b([0-3]?\d)[\-/\.]([01]?\d)\b")

def _extract_card_date(card) -> str | None:
    # 1) Candidatos típicos de badge/fecha
    candidates = card.select(
        ".game-header .badge, .game-header .date, .game-date, .date, .badge"
    )
    texts = [_norm_ws(el.get_text(" ", strip=True)) for el in candidates if el]

    # 2) Fallback: un trozo del texto del card
    if not texts:
        texts = [_norm_ws(card.get_text(" ", strip=True))[:80]]

    today = datetime.now(RD_TZ).date()
    for txt in texts:
        m = _ddmm.search(txt)
        if not m:
            continue
        dd, mm = int(m.group(1)), int(m.group(2))
        if 1 <= dd <= 31 and 1 <= mm <= 12:
            yy = today.year
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
    out: list[Draw] = []
    cards = _extract_cards(soup)
    # log simple
    print(f"[DEBUG] {provider}: cards={len(cards)}")

    for card in cards:
        title = _extract_title(card)
        if not title:
            continue

        # tolera “Mediodía” / “Medio Día”, “Dia” / “Día”
        if title not in title_map:
            t2 = title.replace("Mediodía", "Medio Día").replace("Dia", "Día")
            if t2 not in title_map:
                continue
            title = t2

        game, edition = title_map[title]
        nums = _extract_numbers(card)
        if not nums:
            continue

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


# ----------------- Scrapers -----------------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    soup = _fetch_soup(f"{BASE}/la-primera", dump_slug="la-primera")
    title_map = {
        "La Primera Día": ("Quiniela", "Día"),
        "Primera Noche": ("Quiniela", "Noche"),
        "El Quinielón Día": ("El Quinielón", "Día"),
        "El Quinielón Noche": ("El Quinielón", "Noche"),
        "Loto 5": ("Loto 5", None),
    }
    draws = _build_from_cards(soup, "La Primera", title_map)
    print("[DEBUG][La Primera]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    soup = _fetch_soup(f"{BASE}/leidsa", dump_slug="leidsa")
    title_map = {
        "Pega 3 Más": ("Pega 3 Más", None),
        "Quiniela Leidsa": ("Quiniela", None),
        "Loto Pool": ("Loto Pool", None),
        "Super Kino TV": ("Super Kino TV", None),
        "Loto - Super Loto Más": ("Loto - Super Loto Más", None),
        "Super Palé": ("Super Palé", None),
    }
    draws = _build_from_cards(soup, "Leidsa", title_map)
    print("[DEBUG][Leidsa]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    soup = _fetch_soup(f"{BASE}/loteria-nacional", dump_slug="nacional")
    title_map = {
        "Juega + Pega +": ("Juega + Pega +", None),
        "Gana Más": ("Gana Más", None),
        "Lotería Nacional": ("Lotería Nacional", None),
    }
    draws = _build_from_cards(soup, "Lotería Nacional", title_map)
    print("[DEBUG][Nacional]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("real", f"{BASE}/loto-real")
def scrape_real():
    soup = _fetch_soup(f"{BASE}/loto-real", dump_slug="real")
    title_map = {
        "Quiniela Real": ("Quiniela", None),
        "Loto Real": ("Loto Real", None),
    }
    draws = _build_from_cards(soup, "Lotería Real", title_map)
    print("[DEBUG][Real]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("loteka", f"{BASE}/loteka")
def scrape_loteka():
    soup = _fetch_soup(f"{BASE}/loteka", dump_slug="loteka")
    title_map = {
        "Quiniela Loteka": ("Quiniela", None),
        "Mega Chances": ("Mega Chances", None),
    }
    draws = _build_from_cards(soup, "Loteka", title_map)
    print("[DEBUG][Loteka]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("lotedom", f"{BASE}/lotedom")
def scrape_lotedom():
    soup = _fetch_soup(f"{BASE}/lotedom", dump_slug="lotedom")
    title_map = {
        "Quiniela LoteDom": ("Quiniela", None),
        "El Quemaito Mayor": ("El Quemaito Mayor", None),
    }
    draws = _build_from_cards(soup, "LoteDom", title_map)
    print("[DEBUG][LoteDom]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("la_suerte", f"{BASE}/la-suerte-dominicana")
def scrape_la_suerte():
    soup = _fetch_soup(f"{BASE}/la-suerte-dominicana", dump_slug="la-suerte")
    title_map = {
        "La Suerte 12:30": ("La Suerte", "12:30"),
        "La Suerte 18:00": ("La Suerte", "18:00"),
    }
    draws = _build_from_cards(soup, "La Suerte Dominicana", title_map)
    print("[DEBUG][La Suerte]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("florida", f"{BASE}/loteria-de-florida")
def scrape_florida():
    soup = _fetch_soup(f"{BASE}/loteria-de-florida", dump_slug="florida")
    title_map = {
        "Florida Día": ("Florida", "Día"),
        "Florida Tarde": ("Florida", "Tarde"),
        "Florida Noche": ("Florida", "Noche"),
    }
    draws = _build_from_cards(soup, "Florida", title_map)
    print("[DEBUG][Florida]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("nueva_york", f"{BASE}/nueva-york")
def scrape_nueva_york():
    soup = _fetch_soup(f"{BASE}/nueva-york", dump_slug="nueva-york")
    title_map = {
        "New York Día": ("New York", "Día"),
        "New York Tarde": ("New York", "Tarde"),
        "New York Noche": ("New York", "Noche"),
    }
    draws = _build_from_cards(soup, "New York", title_map)
    print("[DEBUG][New York]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("americanas", f"{BASE}/americanas")
def scrape_americanas():
    soup = _fetch_soup(f"{BASE}/americanas", dump_slug="americanas")
    title_map = {
        "PowerBall": ("PowerBall", None),
        "Mega Millions": ("Mega Millions", None),
        "Cash 4 Life": ("Cash 4 Life", None),
    }
    draws = _build_from_cards(soup, "Americanas", title_map)
    print("[DEBUG][Americanas]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("anguila", f"{BASE}/anguila")
def scrape_anguila():
    soup = _fetch_soup(f"{BASE}/anguila", dump_slug="anguila")
    title_map = {
        "Anguila Mañana": ("Anguila", "Mañana"),
        "Anguila Medio Día": ("Anguila", "Medio Día"),
        "Anguila Tarde": ("Anguila", "Tarde"),
        "Anguila Noche": ("Anguila", "Noche"),
    }
    draws = _build_from_cards(soup, "Anguila", title_map)
    print("[DEBUG][Anguila]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws

@registry.site("king_lottery", f"{BASE}/king-lottery")
def scrape_king_lottery():
    soup = _fetch_soup(f"{BASE}/king-lottery", dump_slug="king-lottery")
    title_map = {
        "King Lottery 12:30": ("King Lottery", "12:30"),
        "King Lottery 7:30": ("King Lottery", "7:30"),
    }
    draws = _build_from_cards(soup, "King Lottery", title_map)
    print("[DEBUG][King Lottery]:", [(d.date, d.game, d.edition, d.numbers) for d in draws])
    return draws
