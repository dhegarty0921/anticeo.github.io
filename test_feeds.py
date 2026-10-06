#!/usr/bin/env python3
"""Test every feed in sources.yml: HTTP status + looks-like-RSS check."""
import yaml, urllib.request, socket, ssl

socket.setdefaulttimeout(15)
ctx = ssl.create_default_context()

src = yaml.safe_load(open("sources.yml", encoding="utf-8"))
feeds = src.get("feeds", [])
UA = {"User-Agent": "Mozilla/5.0 (compatible; ANTICEO/1.0; +https://anticeo.com)"}

live, dead = [], []
for url in feeds:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, context=ctx) as r:
            body = r.read(200_000)
            code = r.status
        head = body[:2000].lower()
        ok = code == 200 and (b"<rss" in head or b"<feed" in head or b"<rdf" in head or b"<?xml" in head)
        (live if ok else dead).append((url, code, len(body)))
    except Exception as e:
        dead.append((url, None, str(e)[:60]))

print(f"LIVE: {len(live)}  DEAD: {len(dead)}\n")
print("--- DEAD ---")
for u, c, info in dead:
    print(f"[{c}] {info}  {u}")
print("\n--- LIVE ---")
for u, c, n in live:
    print(f"[{c}] {n:>7}B  {u}")
