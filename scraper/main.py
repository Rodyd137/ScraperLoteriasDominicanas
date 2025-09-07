# scraper/main.py
import os, json, hashlib, datetime, requests
from .schema import Payload, asdict_payload, now_iso
from .sites import all_sites  # <- import de paquete

OUT_DIR = os.getenv("OUT_DIR", "public")

def sha(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

def main():
    draws = []

    print("=== RUNNING SITES ===")
    for key, (url, fn) in all_sites():
        try:
            print(f"[SITE] {key} -> {url}")
            part = fn() or []
            print(f"    resultados: {len(part)}")
            if part:
                s = part[0]
                print(f"    ejemplo: {s.provider} | {s.game} {s.edition} | {s.numbers}")
            draws.extend(part)
        except Exception as e:
            print(f"    [WARN] {key} failed: {e}")

    print(f"TOTAL DRAWS: {len(draws)}")

    payload = Payload(
        source="https://loteriasdominicanas.com",
        last_updated=now_iso(),
        draws=draws,
    )
    data = asdict_payload(payload)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_file = os.path.join(OUT_DIR, "data.json")
    old = {}
    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            old = json.load(f)

    if sha(old) == sha(data):
        print("No changes.")
        return

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    feed_dir = os.path.join(OUT_DIR, "feed")
    os.makedirs(feed_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    with open(os.path.join(feed_dir, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Updated.")

if __name__ == "__main__":
    main()
