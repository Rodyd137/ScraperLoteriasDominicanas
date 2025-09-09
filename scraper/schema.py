from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import re
import unicodedata

def slugify(s: str) -> str:
    """
    Convierte 'Lotería Nacional' -> 'loteria-nacional', 'El Quinielón' -> 'el-quinielon'
    """
    s = s.strip().lower()
    # quita acentos
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    # reemplaza no-alfanum por '-'
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s

@dataclass
class Draw:
    # campos "bonitos" para mostrar
    provider: str
    game: str
    edition: Optional[str]
    date: str
    numbers: List[str]

    # IDs normalizados para filtrar/usar en la app
    provider_id: str
    game_id: str

@dataclass
class Payload:
    source: str
    last_updated: str
    draws: List[Draw]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def asdict_payload(p: Payload) -> Dict[str, Any]:
    d = asdict(p)
    # orden estable por IDs (útil para diffs)
    d["draws"] = sorted(
        d["draws"],
        key=lambda x: (x["provider_id"], x["game_id"], x["edition"] or "", x["date"])
    )
    return d
