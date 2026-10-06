#!/usr/bin/env python3
import feedparser, yaml, pathlib, json, datetime

def nowz(): return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

src = yaml.safe_load(pathlib.Path("sources.yml").read_text(encoding="utf-8"))

# Collect items per feed first, then round-robin interleave across feeds.
# (The old code concatenated feeds in order and truncated at 200, which
# starved every feed after the first ~4 and left two sections permanently empty.)
per_feed = []
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}

# Feeds that block GitHub Actions IP ranges fall back to a Google News
# mirror of the same site. The section hint keeps items classified correctly
# since fallback URLs point at news.google.com instead of the real domain.
FALLBACKS = {
    "https://electronicintifada.net/rss.xml":
        "https://news.google.com/rss/search?q=site:electronicintifada.net&hl=en-US&gl=US&ceid=US:en",
}
SECTION_HINT = {
    "https://electronicintifada.net/rss.xml": "MILITARY INDUSTRIAL COMPLEX",
}

for url in src.get("feeds", []):
    d = feedparser.parse(url, request_headers=HEADERS)
    source = d.feed.get("title","").strip()
    used_fallback = False
    if not d.entries and url in FALLBACKS:
        d = feedparser.parse(FALLBACKS[url], request_headers=HEADERS)
        source = source + " (via Google News)" if source else "via Google News"
        used_fallback = True
    feed_items = []
    for e in d.entries[:50]:
        title = e.get("title") or "(untitled)"
        link  = e.get("link")  or "#"
        ts    = e.get("published") or e.get("updated") or nowz()
        rec = {
            "title": title.strip(),
            "url": link.strip(),
            "source": source,
            "ts": ts
        }
        if used_fallback and url in SECTION_HINT:
            rec["section"] = SECTION_HINT[url]
        feed_items.append(rec)
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
