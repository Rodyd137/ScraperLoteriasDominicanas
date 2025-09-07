from dataclasses import dataclass, asdict
from typing import List, Optional
from datetime import datetime, timezone

@dataclass
class Draw:
    provider: str
    game: str
    edition: Optional[str]
    date: str
    numbers: List[str]

@dataclass
class Payload:
    source: str
    last_updated: str
    draws: List[Draw]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def asdict_payload(p: Payload) -> dict:
    d = asdict(p)
    d["draws"] = sorted(d["draws"], key=lambda x: (x["provider"], x["game"], x["edition"] or "", x["date"]))
    return d
