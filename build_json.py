#!/usr/bin/env python3
import json, pathlib, datetime, re, yaml

ROOT = pathlib.Path(__file__).resolve().parent
NDJSON = ROOT / "scraper_out.ndjson"
CATS   = yaml.safe_load((ROOT / "categories.yml").read_text(encoding="utf-8"))["categories"]

def nowz(): return datetime.datetime.utcnow().isoformat()+"Z"


from urllib.parse import urlparse

def cap_per_domain(items, max_per=3):
    buckets = {}
    out = []
    for it in items:
        host = urlparse(it.get("url","")).hostname or ""
        host = host.lower()
        if host.startswith("www."): host = host[4:]
        buckets.setdefault(host, 0)
        if buckets[host] < max_per:
            out.append(it)
            buckets[host] += 1
    return out


# Compile rules (case-insensitive)
rules = []
for c in CATS:
    pats = [re.compile(pat, re.I) for pat in c.get("any", [])]
    rules.append({"key": c["key"], "max": c.get("max_items", 40), "pats": pats})

# Load items (NDJSON)
raw = []
if NDJSON.exists():
    for ln in NDJSON.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        raw.append({
            "title": rec.get("title","").strip() or "(untitled)",
            "url":   (rec.get("url") or "#").strip(),
            "source": (rec.get("source") or "").strip(),
            "ts":     rec.get("ts") or nowz()
        })
else:
    raw = [{
        "title":"Hello world","url":"https://example.com/1","source":"Demo","ts":nowz()
    }]

# Sort newest first (ts can be RFC822 or ISO; keep as string compare fallback)
def ts_key(x): return x.get("ts","")
raw.sort(key=ts_key, reverse=True)

# Dedup by URL
seen=set(); items=[]
for it in raw:
    u = it["url"]
    if u in seen: continue
    seen.add(u); items.append(it)

# Assign category
def classify(it):
    hay = " ".join([it.get("title",""), it.get("source",""), it.get("url","")])
    for r in rules:
        if any(p.search(hay) for p in r["pats"]):
            return r["key"]
    return None

buckets = {r["key"]: [] for r in rules}
for it in items:
    cat = classify(it)
    if cat:
        buckets[cat].append(it)

# Cap per-category
sections = []
for r in rules:
    arr = buckets[r["key"]][:r["max"]]
    sections.append({"title": r["key"], "items": arr})

# Headline: take the newest across all or fallback
headline = None
for s in sections:
    if s["items"]:
        headline = s["items"][0]
        break
if not headline:
    headline = {"title":"ANTICEO","url":"https://anticeo.com"}

out = {
  "headline": headline,
  "sections": sections,
  "generated_at": nowz()
}

(ROOT / "anticeo-news.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("Wrote anticeo-news.json with", sum(len(s["items"]) for s in sections), "categorized items")
