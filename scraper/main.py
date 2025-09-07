import os, json, hashlib, datetime
from schema import Payload, asdict_payload, now_iso
from sites import all_sites

OUT_DIR = os.getenv("OUT_DIR", "public")

def sha(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

def main():
    draws = []
    for key, (url, fn) in all_sites():
        try:
            part = fn() or []
            draws.extend(part)
        except Exception as e:
            print(f"[WARN] {key} failed: {e}")

    payload = Payload(
        source="https://loteriasdominicanas.com",
        last_updated=now_iso(),
        draws=draws
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
