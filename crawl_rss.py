#!/usr/bin/env python3
import feedparser, yaml, pathlib, json, datetime, sys

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
    # Personal blog may block GitHub Actions IPs like EI does; mirror ready.
    "https://mikopeled.com/feed/":
        "https://news.google.com/rss/search?q=site:mikopeled.com&hl=en-US&gl=US&ceid=US:en",
    # Cloudflare-fronted; GitHub Actions IPs usually get a challenge page.
    "https://www.palestinechronicle.com/feed/":
        "https://news.google.com/rss/search?q=site:palestinechronicle.com&hl=en-US&gl=US&ceid=US:en",
}
# Per-feed section override: every item from a listed feed lands in the given
# section, regardless of title keywords or domain classification in build_json.py.
# (Originally only used for Google News fallbacks, since fallback URLs point at
# news.google.com instead of the real domain; now also pins author/aggregated
# feeds whose domain mapping or keyword mix would misclassify them.)
SECTION_HINT = {
    "https://headlineusa.com/author/ksilva/feed/": "PARA POLITICAL INTRIGUE",
    "https://www.globalresearch.ca/feed/": "MILITARY INDUSTRIAL COMPLEX",
    # New section: author feeds pinned wholesale (their beats span the theme)
    "https://mikopeled.com/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://news.google.com/rss/search?q=site:davidsheen.com&hl=en-US&gl=US&ceid=US:en": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://news.google.com/rss/search?q=site:haaretz.com+%22Gideon+Levy%22&hl=en-US&gl=US&ceid=US:en": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://news.google.com/rss/search?q=site:nybooks.com+%22Wallace+Shawn%22&hl=en-US&gl=US&ceid=US:en": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    # Theme publications pinned wholesale (from David Sheen's portfolio list)
    "https://thegrayzone.com/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://mondoweiss.net/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://www.972mag.com/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://www.middleeastmonitor.com/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    # Repinned from MILITARY INDUSTRIAL COMPLEX / keyword routing: both beats
    # are squarely the settler-colonial theme.
    "https://electronicintifada.net/rss.xml": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    "https://www.mintpressnews.com/feed/": "SETTLER COLONIAL STATE FALSE FLAG LIES",
    # Palestine Chronicle intentionally UNPINNED: Gaza war coverage classifies
    # into MILITARY INDUSTRIAL COMPLEX by keyword.
}

# Clean display labels for feeds whose <title> is a search query (Google News
# mirrors) rather than a publication name.
SOURCE_LABEL = {
    "https://news.google.com/rss/search?q=site:davidsheen.com&hl=en-US&gl=US&ceid=US:en": "David Sheen",
    "https://news.google.com/rss/search?q=site:haaretz.com+%22Gideon+Levy%22&hl=en-US&gl=US&ceid=US:en": "Gideon Levy (Haaretz)",
    "https://news.google.com/rss/search?q=site:nybooks.com+%22Wallace+Shawn%22&hl=en-US&gl=US&ceid=US:en": "Wallace Shawn (NYRB)",
    "https://news.google.com/rss/search?q=%22Ben+Cohen%22+%22Ben+%26+Jerry%27s%22&hl=en-US&gl=US&ceid=US:en": "Ben Cohen (Ben & Jerry's)",
}

for url in src.get("feeds", []):
    # A single feed dropping the connection mid-body (chunked IncompleteRead)
    # used to kill the whole run — log it and keep crawling the rest.
    try:
        d = feedparser.parse(url, request_headers=HEADERS)
    except Exception as ex:
        print(f"WARNING: feed failed, skipping: {url} ({type(ex).__name__}: {ex})", file=sys.stderr)
        per_feed.append([])
        continue
    source = SOURCE_LABEL.get(url) or d.feed.get("title","").strip()
    used_fallback = False
    if not d.entries and url in FALLBACKS:
        try:
            d = feedparser.parse(FALLBACKS[url], request_headers=HEADERS)
        except Exception as ex:
            print(f"WARNING: fallback failed, skipping: {FALLBACKS[url]} ({type(ex).__name__}: {ex})", file=sys.stderr)
            per_feed.append([])
            continue
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
        if url in SECTION_HINT:
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
