// Node 20+
import fs from "fs";
import path from "path";

const APP_ID = process.env.ONESIGNAL_APP_ID;
const REST_KEY = process.env.ONESIGNAL_REST_API_KEY;
if (!APP_ID || !REST_KEY) {
  console.error("Missing ONESIGNAL_APP_ID or ONESIGNAL_REST_API_KEY");
  process.exit(1);
}

const urls = [
  "https://rodyd137.github.io/ScraperLoteriasDominicanas/public/feed/latest.json",
  "https://rodyd137.github.io/ScraperLoteriasDominicanas/public/data.json",
];

const stateDir = ".botstate";
const stateFile = path.join(stateDir, "lastDates.json");
await fs.promises.mkdir(stateDir, { recursive: true });

function normalize(s) {
  return (s || "")
    .normalize("NFD").replace(/\p{Diacritic}/gu, "")
    .toLowerCase().trim();
}
function canonEdition(raw) {
  let t = normalize(raw);
  if (!t) return "";
  if (["mediodia","medio dia","medio-dia","dia","d"].includes(t)) return "dia";
  if (["noche","n"].includes(t)) return "noche";
  if (["tarde"].includes(t)) return "18:00";
  if (t === "12:30" || t === "1230") return "12:30";
  if (t === "18:00" || t === "1800") return "18:00";
  return t;
}
function normalizeGameKey(raw) {
  let g = normalize(raw);
  g = g.replaceAll("loto-super loto mas", "loto super loto mas")
       .replaceAll("loto - super loto mas", "loto super loto mas")
       .replaceAll("quiniela leidsa", "quiniela")
       .replaceAll("quiniela loteka", "quiniela")
       .replaceAll("quiniela real", "quiniela")
       .replaceAll("quiniela lotedom", "quiniela");
  return g;
}
function favKeyOf(d) {
  return `${normalize(d.provider)}|${normalizeGameKey(d.game)}|${canonEdition(d.edition)}`;
}
function tagKeyFor(favKey) {
  const base = favKey
    .normalize("NFD").replace(/\p{Diacritic}/gu, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return "fav_" + base.slice(0, 40);
}
function toYMD(dateStr) {
  if (!dateStr) return null;
  // Intenta yyyy-MM-dd directo
  if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) return dateStr;
  // Si viene ISO, parsea y formatea a es-DO / Santo Domingo
  const d = new Date(dateStr);
  if (isNaN(d)) return null;
  const fmt = new Intl.DateTimeFormat("es-DO", { timeZone: "America/Santo_Domingo", year:"numeric", month:"2-digit", day:"2-digit" });
  const parts = fmt.formatToParts(d).reduce((acc,p)=> (acc[p.type]=p.value, acc), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}
function todayYMD() {
  const now = new Date();
  const fmt = new Intl.DateTimeFormat("es-DO", { timeZone: "America/Santo_Domingo", year:"numeric", month:"2-digit", day:"2-digit" });
  const parts = fmt.formatToParts(now).reduce((acc,p)=> (acc[p.type]=p.value, acc), {});
  return `${parts.year}-${parts.month}-${parts.day}`;
}

async function loadFeed() {
  for (const u of urls) {
    try {
      const r = await fetch(u, { timeout: 12000 });
      if (!r.ok) continue;
      const json = await r.json();
      if (Array.isArray(json)) return json;
      if (json && Array.isArray(json.draws)) return json.draws;
    } catch {}
  }
  throw new Error("No se pudo leer el feed");
}

async function sendPush({ tagKey, title, body, data }) {
  const payload = {
    app_id: APP_ID,
    headings: { es: title, en: title },
    contents: { es: body, en: body },
    // Target solo a los que tengan el tag de ese favorito
    filters: [{ field: "tag", key: tagKey, relation: "=", value: "1" }],
    data
  };
  const r = await fetch("https://onesignal.com/api/v1/notifications", {
    method: "POST",
    headers: {
      "Authorization": `Basic ${REST_KEY}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
  if (!r.ok) {
    const t = await r.text();
    console.error("OneSignal error:", r.status, t);
    return false;
  }
  return true;
}

const draws = await loadFeed();
const currentMap = {}; // favKey -> yyy-mm-dd
for (const d of draws) {
  const fk = favKeyOf(d);
  const ymd = toYMD(d.date);
  if (ymd) currentMap[fk] = ymd;
}

let prev = {};
try { prev = JSON.parse(await fs.promises.readFile(stateFile, "utf8")); } catch {}

const today = todayYMD();
const changedToday = [];
for (const [fk, ymd] of Object.entries(currentMap)) {
  const before = prev[fk];
  if (ymd === today && before !== ymd) {
    const item = draws.find(dd => favKeyOf(dd) === fk);
    if (item) changedToday.push({ fk, ymd, item });
  }
}

// Envía una notificación por cada favorito que cambió hoy
for (const { fk, ymd, item } of changedToday) {
  const tagKey = tagKeyFor(fk);
  const title = `${item.game}${item.edition ? " • " + item.edition : ""} — ${item.provider}`;
  const nums = Array.isArray(item.numbers) ? item.numbers.join("  ") : "";
  const ok = await sendPush({
    tagKey,
    title,
    body: nums.length ? `Números: ${nums}` : `Actualizado ${ymd}`,
    data: { favKey: fk, provider: item.provider, game: item.game, edition: item.edition || "", date: ymd, numbers: item.numbers || [] }
  });
  console.log(ok ? `PUSH OK → ${tagKey}` : `PUSH FAIL → ${tagKey}`);
}

// Actualiza estado (evita repetir)
await fs.promises.writeFile(stateFile, JSON.stringify(currentMap, null, 2));
