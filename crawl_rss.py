#!/usr/bin/env python3
import feedparser, yaml, pathlib, json, datetime

def nowz(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

src = yaml.safe_load(pathlib.Path("sources.yml").read_text(encoding="utf-8"))

# Collect items per feed first, then round-robin interleave across feeds.
# (The old code concatenated feeds in order and truncated at 200, which
# starved every feed after the first ~4 and left two sections permanently empty.)
per_feed = []
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
for url in src.get("feeds", []):
    d = feedparser.parse(url, request_headers=HEADERS)
    feed_items = []
    for e in d.entries[:50]:
        title = e.get("title") or "(untitled)"
        link  = e.get("link")  or "#"
        ts    = e.get("published") or e.get("updated") or nowz()
        feed_items.append({
            "title": title.strip(),
            "url": link.strip(),
            "source": d.feed.get("title","").strip(),
            "ts": ts
        })
    per_feed.append(feed_items)

items = []
i = 0
while True:
    added = False
    for feed_items in per_feed:
        if i < len(feed_items):
            items.append(feed_items[i])
            added = True
    if not added:
        break
    i += 1

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

print(f"Wrote {len(out[:200])} items to scraper_out.ndjson (from {sum(1 for f_ in per_feed if f_)} live feeds)")
