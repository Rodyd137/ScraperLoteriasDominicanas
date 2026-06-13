"""
JSON API client for loteriasdominicanas.com.

The source site was rewritten as a Nuxt SPA on 2026-06-12 and the old
HTML selectors (`.game-block`, `.game-title span`, `.game-scores .score`)
no longer exist. The SPA hydrates from a public JSON API:

    GET https://api.loteriasdominicanas.com/dominicana/site-companies/{id}
        ?date=<ISO-UTC>
    Origin: https://loteriasdominicanas.com   # CORS-enforced

Response (truncated to what we read):

    {
      "_id": "...",
      "title": "Leidsa",
      "logo": {"key": "..."},
      "siteGames": [{
        "title": "Quiniela Leidsa",
        "logo": {"key": "..."},
        "game": {
          "score_layout": [[{...}, {"is_bonus": true, "options": [...]}]],
          "sessions": [{
            "date": "2026-06-12T04:00:00.000Z",  # midnight America/Santo_Domingo
            "score": [["53","07","63"]]
          }]
        }
      }, ...]
    }

We turn each session into a Draw with the exact same fields the iOS app
already consumes (provider/game/edition/date/numbers/provider_id/game_id/
logo_url) so no client-side change is needed.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests

from ..schema import Draw, slugify
from . import registry

API_BASE  = "https://api.loteriasdominicanas.com/dominicana"
S3_BASE   = "https://temp-lottery.s3.us-east-1.amazonaws.com"
ORIGIN    = "https://loteriasdominicanas.com"
TIMEOUT_S = 12

# 12 companies, mapped to the CANONICAL provider name the iOS app already
# knows (provider_id = slugify(canonical)). Changing the canonical name
# would silently wipe user favorites/subscriptions stored by slug.
COMPANIES: List[Tuple[str, str]] = [
    # (company_id, canonical_provider_name)
    ("6966a6d1ea7015c3b8a3d44a", "Leidsa"),
    ("6966a6d1ea7015c3b8a3d479", "Lotería Nacional"),
    ("6966a6d2ea7015c3b8a3d4a5", "Lotería Real"),
    ("6966a6d2ea7015c3b8a3d4d4", "Loteka"),
    ("6966a6d2ea7015c3b8a3d4fa", "Americanas"),
    ("6966a6d2ea7015c3b8a3d52f", "New York"),
    ("6966a6d2ea7015c3b8a3d564", "Florida"),
    ("6966a6d2ea7015c3b8a3d5bd", "La Primera"),
    ("6966a6d3ea7015c3b8a3d5e0", "La Suerte Dominicana"),
    ("6966a6d3ea7015c3b8a3d5f1", "LoteDom"),
    ("6966a6d3ea7015c3b8a3d60e", "Anguila"),
    ("6966a6d3ea7015c3b8a3d643", "King Lottery"),
]

# Longest-first so "Día" doesn't accidentally swallow "Medio Día".
# Florida's listings use the unaccented "Dia" — accept both spellings
# so "Pick 3 Dia" splits the same as "Pick 3 Día" elsewhere.
EDITION_SUFFIXES = ["Medio Día", "Mañana", "Noche", "Tarde", "Día", "Dia"]

# When the API uses "Dia" without an accent we still emit the canonical
# accented form so the iOS app sees a single edition value across
# providers (it was always "Día" historically).
EDITION_NORMALIZE = {"Dia": "Día"}

# Per-provider title rewrites for siteGame.title strings that don't follow
# the "<game> <edition>" pattern. Maps (canonical_provider, api_title) →
# (game, edition). Kept tiny on purpose — only correct true mismatches
# against the historical schema.
TITLE_OVERRIDES: Dict[Tuple[str, str], Tuple[str, Optional[str]]] = {
    ("La Primera",           "La Primera Día"):      ("Quiniela",  "Medio Día"),
    ("La Primera",           "Primera Noche"):       ("Quiniela",  "Noche"),
    ("King Lottery",         "King Lottery 12:30"):  ("Quiniela",  "Día"),
    ("King Lottery",         "King Lottery 7:30"):   ("Quiniela",  "Noche"),
    ("La Suerte Dominicana", "La Suerte 12:30"):     ("La Suerte", "Día"),
    ("La Suerte Dominicana", "La Suerte 18:00"):     ("La Suerte", "Tarde"),
    ("New York",             "Take 5 Midday"):       ("Take 5",    "Medio Día"),
    ("Florida",              "Fantasy Medio Día"):   ("Fantasy 5", "Medio Día"),
    ("Florida",              "Fantasy 5"):           ("Fantasy 5", "Noche"),
}

# Game-name rewrites after edition stripping. The API picks slightly
# different names than the canonical set; we map back so favorites stick.
GAME_RENAME: Dict[str, str] = {
    "La Cuarteta":             "Cuarteta",
    "Pega 4 Real":             "Pega 4",
    "Quiniela Real":           "Quiniela",
    "Quiniela Leidsa":         "Quiniela",
    "Quiniela LoteDom":        "Quiniela",
    "Quiniela Loteka":         "Quiniela",
    "Loto - Super Loto Más":   "Loto Más",
    "MC Repartidera":          "Mega Chances Repartidera",
    "Super Palé":              "Súper Palé",   # canonical uses accented S
    "Powerball":               "PowerBall",
    "Powerball Double Play":   "PowerBall Double Play",
}

# Per-provider title-prefix filters. Americanas's API includes Florida/NY
# games that are ALSO published under their own dedicated companies — we
# drop the duplicates so the same draw doesn't appear twice in the app.
PROVIDER_DROP_PREFIXES: Dict[str, Tuple[str, ...]] = {
    "Americanas": ("Florida ", "New York "),
}

_NUMERIC = re.compile(r"^\d+$")


def _split_edition(title: str) -> Tuple[str, Optional[str]]:
    """Strip a known edition suffix from a siteGame title."""
    for suf in EDITION_SUFFIXES:
        marker = " " + suf
        if title.endswith(marker):
            base = title[:-len(marker)].strip()
            return base, EDITION_NORMALIZE.get(suf, suf)
    return title.strip(), None


def _normalize_number(raw: str) -> Optional[str]:
    """Zero-pad width-1 numbers (Pick 3 publishes `"7"` where the legacy
    schema had `"07"`). Leave width-2+ alone so Philipsburg's `"6509"` and
    similar 4-digit games round-trip cleanly. Returns None for tokens
    that aren't numbers — caller resolves those via the bonus options."""
    raw = (raw or "").strip()
    if not _NUMERIC.match(raw):
        return None
    return raw.zfill(2) if len(raw) == 1 else raw


def _resolve_bonus(token: str, layout: list) -> Optional[str]:
    """Bonus balls arrive as opaque option IDs in score. The matching
    `score_layout[panel][slot].options[].id` carries a `text` field that
    is the human-readable number (e.g. `"4"` for the Cash Ball)."""
    for panel in layout or []:
        for slot in panel or []:
            for opt in slot.get("options") or []:
                if opt.get("id") == token:
                    return _normalize_number(opt.get("text", ""))
    return None


def _flatten_score(score: list, layout: list) -> List[str]:
    out: List[str] = []
    for grp in score or []:
        if not isinstance(grp, list):
            continue
        for token in grp:
            token = str(token) if token is not None else ""
            n = _normalize_number(token)
            if n is None:
                n = _resolve_bonus(token, layout)
            if n is not None:
                out.append(n)
    return out


def _logo_url(*candidates: Optional[dict]) -> Optional[str]:
    """First logo-shaped dict with a non-empty `.key` wins. Prefers the
    per-siteGame logo over the per-game one over the per-company one,
    matching what the old HTML scraper picked from `<img data-src>`."""
    for c in candidates:
        if isinstance(c, dict):
            key = c.get("key")
            if isinstance(key, str) and key:
                return f"{S3_BASE}/{key}"
    return None


def _yyyymmdd(iso_utc: str) -> str:
    """Session.date is always midnight America/Santo_Domingo expressed
    as UTC (`...T04:00:00.000Z`), so a plain ISO date slice gets the
    correct calendar day without any tz arithmetic."""
    return (iso_utc or "")[:10]


def _fetch_company(company_id: str) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    url = f"{API_BASE}/site-companies/{company_id}?date={now}"
    r = requests.get(
        url,
        headers={"Origin": ORIGIN, "Accept": "application/json"},
        timeout=TIMEOUT_S,
    )
    r.raise_for_status()
    return r.json()


def _draws_for(company_id: str, provider: str) -> List[Draw]:
    try:
        data = _fetch_company(company_id)
    except (requests.RequestException, ValueError) as e:
        print(f"[WARN] {provider} failed: {e}")
        return []

    drop_prefixes = PROVIDER_DROP_PREFIXES.get(provider, ())
    out: List[Draw] = []

    for site_game in data.get("siteGames") or []:
        title_full = (site_game.get("title") or "").strip()
        if not title_full:
            continue
        if drop_prefixes and title_full.startswith(drop_prefixes):
            continue

        inner = site_game.get("game") or {}
        sessions = inner.get("sessions") or []
        if not sessions:
            continue
        sess = sessions[0]
        numbers = _flatten_score(sess.get("score") or [], inner.get("score_layout") or [])
        if not numbers:
            continue

        # 1) Explicit override wins. 2) Suffix split. 3) Bare title.
        override = TITLE_OVERRIDES.get((provider, title_full))
        if override is not None:
            game_base, edition = override
        else:
            game_base, edition = _split_edition(title_full)

        game = GAME_RENAME.get(game_base, game_base)

        out.append(Draw(
            provider=provider,
            game=game,
            edition=edition,
            date=_yyyymmdd(sess.get("date") or ""),
            numbers=numbers,
            provider_id=slugify(provider),
            game_id=slugify(game),
            logo_url=_logo_url(
                site_game.get("logo"),
                inner.get("logo"),
                inner.get("mobile_logo"),
                data.get("logo"),
            ),
        ))

    print(f"[DEBUG][{provider}] encontrados:",
          [(d.game, d.edition, d.numbers, d.date) for d in out])
    return out


# ---- Registry --------------------------------------------------------
# One registered function per company so main.py's per-provider logging
# and error isolation keep working unchanged.

def _make_fetcher(company_id: str, provider: str):
    def fn():
        return _draws_for(company_id, provider)
    fn.__name__ = f"fetch_{slugify(provider).replace('-', '_')}"
    return fn


for _cid, _provider in COMPANIES:
    _key = slugify(_provider).replace("-", "_")
    _url = f"{API_BASE}/site-companies/{_cid}"
    registry.site(_key, _url)(_make_fetcher(_cid, _provider))
