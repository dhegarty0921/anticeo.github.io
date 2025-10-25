#!/usr/bin/env python3
import json, pathlib, datetime
from urllib.parse import urlparse

import yaml
cfg = {}
p = pathlib.Path("categories.yml")
if p.exists():
    cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
SKIP = set((cfg.get("skip_domains") or []))

def keep_item(it):
    h = _host_from_url(it.get("url", ""))
    return h not in SKIP

# when building items or per-section lists:
items = [it for it in items if keep_item(it)]
# or:
for sec in news["sections"]:
    sec["items"] = [it for it in sec["items"] if keep_item(it)]#!/usr/bin/env python3
import json, pathlib, datetime
from urllib.parse import urlparse

# --- helpers: host parsing & caps ---
def _host(u: str) -> str:
    h = (urlparse(u or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h

def cap_per_domain(items, max_per=3):
    """Limit items list to at most max_per per domain."""
    counts, out = {}, []
    for it in items:
        host = _host(it.get("url", ""))
        if not host:
            out.append(it); continue
        if counts.get(host, 0) < max_per:
            out.append(it)
            counts[host] = counts.get(host, 0) + 1
    return out

def cap_per_domain_global(sections, max_per=3):
    """Walk all sections and enforce a global cap per domain."""
    counts = {}
    for sec in sections:
        kept = []
        for it in sec.get("items", []):
            host = _host(it.get("url", ""))
            if not host:
                kept.append(it); continue
            if counts.get(host, 0) < max_per:
                kept.append(it)
                counts[host] = counts.get(host, 0) + 1
        sec["items"] = kept
    return sections

# --- your existing code that builds 'news' with 'sections' goes above this line ---
# Expect something like:
# news = {
#   "generated_at": datetime.datetime.utcnow().isoformat()+"Z",
#   "headline": {...},
#   "sections": [
#       {"title":"CHUDS VS SHITLIBS","items":[...]},
#       {"title":"CULTURE WAR","items":[...]},
#       {"title":"MILITARY INDUSTRIAL COMPLEX","items":[...]},
#       {"title":"PARA POLITICAL INTRIGUE","items":[...]},
#   ]
# }

# 1) cap within each section (3 per domain per section)
for sec in news.get("sections", []):
    sec["items"] = cap_per_domain(sec.get("items", []), max_per=3)

# 2) enforce a global cap (3 per domain across *all* sections combined)
news["sections"] = cap_per_domain_global(news.get("sections", []), max_per=3)

# write file
pathlib.Path("anticeo-news.json").write_text(
    json.dumps(news, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("Wrote anticeo-news.json with",
      sum(len(s["items"]) for s in news.get("sections", [])),
      "categorized items")
# --- ADD THIS HELPER BLOCK NEAR THE TOP (after imports) ---
def _host_from_url(u: str) -> str:
    h = (urlparse(u or "").hostname or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return h

def cap_per_domain(items, max_per=3):
    """
    Keep at most max_per items per registrable host.
    Assumes each item has item["url"] and (optionally) item["title"], item["source"], item["ts"].
    """
    counts = {}
    out = []
    for it in items:
        host = _host_from_url(it.get("url", ""))
        if not host:
            out.append(it)  # keep items with no host
            continue
        if counts.get(host, 0) < max_per:
            out.append(it)
            counts[host] = counts.get(host, 0) + 1
    return out
# --- END HELPER BLOCK ---

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
