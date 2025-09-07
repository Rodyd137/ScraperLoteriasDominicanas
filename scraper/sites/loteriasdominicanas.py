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

# ---------- LA PRIMERA ----------
@registry.site("la_primera", f"{BASE}/la-primera")
def scrape_la_primera():
    url = f"{BASE}/la-primera"
    r = requests.get(url, timeout=30, headers={"User-Agent": "RD-Bot/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    d = today_rd()
    out = []

    def map_title(title: str):
        t = title.strip()
        if t == "La Primera Día":
            return ("Quiniela", "Día")
        if t == "Primera Noche":
            return ("Quiniela", "Noche")
        if t == "El Quinielón Día":
            return ("El Quinielón", "Día")
        if t == "El Quinielón Noche":
            return ("El Quinielón", "Noche")
        if t == "Loto 5":
            return ("Loto 5", None)
        return (None, None)

    # Recorremos cada tarjeta
    for card in soup.select(".game-block"):
        title_el = card.select_one(".game-title span")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        game, edition = map_title(title)
        if not game:
            print("[DEBUG] Ignorado título:", title)
            continue

        # Extraer números
        nums = [s.get_text(strip=True).zfill(2) for s in card.select(".game-scores .score") if s.get_text(strip=True).isdigit()]
        if not nums:
            print(f"[DEBUG] {title}: sin números")
            continue

        out.append(Draw(provider="La Primera", game=game, edition=edition, date=d, numbers=nums))
        print(f"[DEBUG] {title}: {nums}")

    print("[DEBUG] Total draws La Primera:", len(out))
    return out
