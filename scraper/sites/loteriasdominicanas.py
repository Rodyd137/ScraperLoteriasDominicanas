import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo
from . import registry
from ..schema import Draw

BASE = "https://loteriasdominicanas.com"
RD_TZ = ZoneInfo("America/Santo_Domingo")

def today_rd():
    return datetime.now(RD_TZ).date().isoformat()

# ---------- LA PRIMERA (parser por tarjetas en el DOM real) ----------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    url = f"{BASE}/la-primera"
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/127.0.0.0 Safari/537.36"),
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://loteriasdominicanas.com/",
    }
    r = requests.get(url, timeout=30, headers=headers)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out: list[Draw] = []

    def map_title(title: str):
        t = " ".join(title.split())
        if t == "La Primera Día":
            return ("Quiniela", "Día")
        if t == "Primera Noche":        # así viene en el DOM (sin “La”)
            return ("Quiniela", "Noche")
        if t == "El Quinielón Día":
            return ("El Quinielón", "Día")
        if t == "El Quinielón Noche":
            return ("El Quinielón", "Noche")
        if t == "Loto 5":
            return ("Loto 5", None)
        return (None, None)

    for card in soup.select(".game-block"):
        title_el = card.select_one(".game-title span")
        if not title_el:
            continue
        title = " ".join(title_el.get_text(" ", strip=True).split())
        game, edition = map_title(title)
        if not game:
            continue

        nums = []
        for s in card.select(".game-scores .score"):
            txt = s.get_text(strip=True)
            if txt.isdigit():
                nums.append(txt.zfill(2))
        if not nums:
            continue

        out.append(Draw(
            provider="La Primera",
            game=game,
            edition=edition,
            date=d,
            numbers=nums
        ))

    # DEBUG breve
    print("[DEBUG][La Primera] draws:", [(dr.game, dr.edition, dr.numbers) for dr in out])
    return out

# ---------- (dejamos Leidsa/Nacional como estaban; luego los migramos igual) ----------
@registry.site("leidsa", f"{BASE}/leidsa")
def scrape_leidsa():
    # placeholder: hasta migrar a parser por tarjetas
    return []

@registry.site("nacional", f"{BASE}/loteria-nacional")
def scrape_nacional():
    # placeholder: hasta migrar a parser por tarjetas
    return []
