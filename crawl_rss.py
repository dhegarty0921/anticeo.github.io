#!/usr/bin/env python3
import feedparser, yaml, pathlib, json, time, hashlib, datetime

def nowz(): return datetime.datetime.utcnow().isoformat() + "Z"

src = yaml.safe_load(pathlib.Path("sources.yml").read_text(encoding="utf-8"))
items = []
for url in src.get("feeds", []):
    d = feedparser.parse(url)
    for e in d.entries[:50]:
        title = e.get("title") or "(untitled)"
        link  = e.get("link")  or "#"
        ts    = e.get("published") or e.get("updated") or nowz()
        items.append({
            "title": title.strip(),
            "url": link.strip(),
            "source": d.feed.get("title","").strip(),
            "ts": ts
        })

# de-dup by URL
seen, out = set(), []
for it in items:
    u = it["url"]
    if u in seen: continue
    seen.add(u); out.append(it)

# write NDJSON
with open("scraper_out.ndjson", "w", encoding="utf-8") as f:
    for it in out[:200]:
        f.write(json.dumps(it, ensure_ascii=False) + "\n")

print(f"Wrote {len(out[:200])} items to scraper_out.ndjson")
