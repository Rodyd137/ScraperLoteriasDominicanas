# scraper/main.py
import os, json, hashlib, datetime, traceback

# ✅ IMPORTS RELATIVOS (funcionan con `python -m scraper.main`)
from .schema import Payload, asdict_payload, now_iso
from .sites import all_sites

OUT_DIR = os.getenv("OUT_DIR", "public")

def sha(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

def main():
    print("== RUNNING SITES ==")
    draws = []
    for key, (url, fn) in all_sites():
        try:
            print(f"-> {key}: {url}")
            part = fn() or []
            print(f"   {len(part)} resultados")
            draws.extend(part)
        except Exception as e:
            print(f"[WARN] {key} failed: {e}")
            traceback.print_exc()

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

    # data.json (último snapshot)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # feed diario + alias estable
    feed_dir = os.path.join(OUT_DIR, "feed")
    os.makedirs(feed_dir, exist_ok=True)
    today = datetime.date.today().isoformat()

    # YYYY-MM-DD.json (histórico)
    with open(os.path.join(feed_dir, f"{today}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # latest.json (siempre el último)
    with open(os.path.join(feed_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("Updated.")

if __name__ == "__main__":
    main()
