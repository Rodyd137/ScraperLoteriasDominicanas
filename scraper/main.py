import os, json, hashlib, datetime, requests
from schema import Payload, asdict_payload, now_iso
from sites import all_sites

OUT_DIR = os.getenv("OUT_DIR", "public")

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/127.0.0.0 Safari/537.36"),
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://loteriasdominicanas.com/",
}

def sha(d: dict) -> str:
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()

def dump_html(key: str, url: str):
    """Guarda el HTML crudo de un sitio para depurar cuando no hay resultados."""
    try:
        r = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
        r.raise_for_status()
        os.makedirs(os.path.join(OUT_DIR, "debug"), exist_ok=True)
        path = os.path.join(OUT_DIR, "debug", f"{key}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(r.text)
        print(f"    [DEBUG] HTML guardado -> {path}")
    except Exception as e:
        print(f"    [DEBUG] No se pudo guardar HTML de {key}: {e}")

def main():
    draws = []

    print("=== RUNNING SITES ===")
    for key, (url, fn) in all_sites():
        try:
            print(f"[SITE] {key} -> {url}")
            part = fn() or []
            print(f"    resultados: {len(part)}")
            if not part:
                print(f"    [WARN] {key} devolvió 0 resultados. Dumping HTML…")
                dump_html(key, url)
            else:
                # muestra un ejemplo
                sample = part[0]
                print(f"    ejemplo: provider={sample.provider}, game={sample.game}, edition={sample.edition}, nums={sample.numbers}")
            draws.extend(part)
        except Exception as e:
            print(f"    [ERROR] {key} failed: {e}")
            dump_html(key, url)

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
