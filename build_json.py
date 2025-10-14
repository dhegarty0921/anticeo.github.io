#!/usr/bin/env python3
import json, pathlib, datetime, sys

NDJSON = pathlib.Path("scraper_out.ndjson")
items = []

def nowz():
    return datetime.datetime.utcnow().isoformat()+"Z"

if NDJSON.exists():
    for ln in NDJSON.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            rec = json.loads(ln)
        except Exception as e:
            # skip bad lines but keep going
            print(f"SKIP bad ndjson line: {e}", file=sys.stderr)
            continue
        items.append({
            "title": rec.get("title","(untitled)"),
            "url":   rec.get("url","#"),
            "source":rec.get("source",""),
            "ts":    rec.get("ts") or nowz()
        })
else:
    # Safe fallback so the site still renders
    items = [{
        "title":"Hello world",
        "url":"https://example.com/1",
        "source":"Demo",
        "ts": nowz()
    }]

# Optional: de-dup by URL while preserving order
seen = set()
deduped = []
for it in items:
    u = it.get("url")
    if u in seen:
        continue
    seen.add(u)
    deduped.append(it)

news = {
  "headline": deduped[0] if deduped else {"title":"ANTICEO","url":"https://anticeo.com"},
  "items": deduped[:120]
}

pathlib.Path("anticeo-news.json").write_text(
    json.dumps(news, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("Wrote anticeo-news.json")
