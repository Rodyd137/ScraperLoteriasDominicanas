# scraper/schema.py
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import re
import unicodedata

# ------------------------
# Utils
# ------------------------
def slugify(s: str) -> str:
    """
    'Lotería Nacional' -> 'loteria-nacional'
    'El Quinielón'     -> 'el-quinielon'
    """
    s = s.strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s

def now_iso() -> str:
    # ISO en UTC con sufijo Z (útil para last_updated)
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# ------------------------
# Data
# ------------------------
@dataclass
class Draw:
    # Para mostrar
    provider: str                 # p.ej. "La Primera"
    game: str                     # p.ej. "Quiniela"
    edition: Optional[str]        # p.ej. "Día" / "Noche" / "12:30" / None
    date: str                     # "YYYY-MM-DD" (día del sorteo)
    numbers: List[str]            # ["73","06","37", ...] (ya formateados a 2 dígitos)

    # IDs normalizados (se calculan en __post_init__)
    provider_id: str = field(init=False)  # "la-primera"
    game_id: str = field(init=False)      # "quiniela"

    # NUEVO: momento del sorteo (opcional)
    time: Optional[str] = None            # "HH:MM" en hora local del proveedor (RD)
    date_time: Optional[str] = None       # ISO-8601 con zona, p.ej. "2025-09-07T12:00:00-04:00"

    def __post_init__(self):
        self.provider_id = slugify(self.provider)
        self.game_id = slugify(self.game)
        # Asegura strings limpias y cero-llenado donde aplique
        norm: List[str] = []
        for x in self.numbers:
            sx = str(x).strip()
            if sx.isdigit():
                try:
                    norm.append(f"{int(sx):02d}")
                except Exception:
                    norm.append(sx)
            else:
                norm.append(sx)
        self.numbers = norm

@dataclass
class Payload:
    source: str
    last_updated: str
    draws: List[Draw]

def asdict_payload(p: Payload) -> Dict[str, Any]:
    d = asdict(p)
    # Orden estable por IDs/edición/fecha
    d["draws"] = sorted(
        d["draws"],
        key=lambda x: (x["provider_id"], x["game_id"], x.get("edition") or "", x["date"], x.get("time") or "")
    )
    return d
