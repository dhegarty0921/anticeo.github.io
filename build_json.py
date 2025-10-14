#!/usr/bin/env python3
import json, pathlib, datetime

# TODO: replace this with your real scraper output.
# Produce a minimal, valid anticeo-news.json so the page renders.
news = {
  "headline": {"title": "ANTICEO is live", "url": "https://anticeo.com"},
  "items": [
    {"title":"Hello world","url":"https://example.com/1","source":"Demo",
     "ts": datetime.datetime.utcnow().isoformat()+"Z"}
  ]
}

pathlib.Path("anticeo-news.json").write_text(
    json.dumps(news, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("Wrote anticeo-news.json")
