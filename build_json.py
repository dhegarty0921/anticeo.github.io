#!/usr/bin/env python3
import json, pathlib, datetime
from urllib.parse import urlparse

# ---------- Inputs ----------
NDJSON = pathlib.Path("scraper_out.ndjson")
OUT    = pathlib.Path("anticeo-news.json")
CFG    = pathlib.Path("categories.yml")   # optional

# ---------- Optional YAML config ----------
skip_domains = set()
per_domain_cap = 3

try:
    import yaml                      # pip install pyyaml
    if CFG.exists():
        cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
        skip_domains = set(cfg.get("skip_domains") or [])
        per_domain_cap = int(cfg.get("per_domain_cap", per_domain_cap))
except Exception:
    pass

# ---------- Helpers ----------
def _nowz() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"

def _host(u: str) -> str:
    h = (urlparse(u or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h

def dedupe_by_url(items):
    seen, out = set(), []
    for it in items:
        u = it.get("url","")
        if u and u not in seen:
            out.append(it); seen.add(u)
    return out

def cap_per_domain(items, max_per: int):
    counts, out = {}, []
    for it in items:
        host = _host(it.get("url",""))
        if not host:  # keep unknowns
            out.append(it); continue
        if counts.get(host, 0) < max_per:
            out.append(it)
            counts[host] = counts.get(host, 0) + 1
    return out

def cap_per_domain_global(sections, max_per: int):
    counts = {}
    for sec in sections:
        kept = []
        for it in sec.get("items", []):
            host = _host(it.get("url",""))
            if not host or counts.get(host, 0) < max_per:
                kept.append(it)
                if host:
                    counts[host] = counts.get(host, 0) + 1
        sec["items"] = kept
    return sections

# ---------- Section rules ----------
RULES = [
    {"title":"CHUDS VS SHITLIBS",
     "domains":["thehill.com","realclearpolitics.com","washingtontimes.com","politico.com","npr.org","nytimes.com","bbc.com","headlineusa.com"],
     "any":["trump","biden","democrat","republican","gop","election","primary","congress","senate","house","white house","campaign"]},
    {"title":"CULTURE WAR",
     "domains":["religionnews.com","pinknews.co.uk","vox.com","nationalreview.com","theatlantic.com","theguardian.com","tabletmag.com","christianitytoday.com"],
     "any":["lgbt","trans","religion","church","faith","dei","campus","pronoun","abortion","book ban","school board","drag","culture war","race","crt"]},
    {"title":"MILITARY INDUSTRIAL COMPLEX",
     "domains":["defenseone.com","thedrive.com","warontherocks.com","navalnews.com","armytimes.com","aljazeera.com","reuters.com","dw.com","antiwar.com","quincyinst.org","scheerpost.com","venezuelanalysis.com"],
     "any":["israel","gaza","palestin","ukraine","nato","pentagon","defense","weapons","missile","airstrike","drone","war","military","army","navy","marines","iran","yemen","hezbollah","taiwan","venezuela"]},
    {"title":"PARA POLITICAL INTRIGUE",
     "domains":["lawfaremedia.org","eff.org","techdirt.com","justsecurity.org","aclu.org","theintercept.com","scheerpost.com"],
     "any":["cia","fbi","nsa","surveillance","whistleblower","leak","foia","spy","informant","homeland security","doj","dhs","patriot act","9/11","oklahoma city","okc bombing"]}
]
ORDER = [r["title"] for r in RULES]

def classify(title: str, url: str) -> str:
    t = (title or "").lower()
    h = _host(url or "")
    for r in RULES:                 # domain first
        if h in (r.get("domains") or []):
            return r["title"]
    for r in RULES:                 # keyword next
        for kw in (r.get("any") or []):
            if kw in t:
                return r["title"]
    return RULES[0]["title"]        # default to first section

# ---------- Load items ----------
items = []
if NDJSON.exists():
    for line in NDJSON.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line: continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        u = rec.get("url") or ""
        h = _host(u)
        if h and h in skip_domains:
            continue
        items.append({
            "title": rec.get("title") or "",
            "url": u,
            "source": rec.get("source") or h or "",
            "ts": rec.get("ts") or _nowz(),
        })

# ---------- Dedupe, classify, cap ----------
items = dedupe_by_url(items)

sections_map = {t: [] for t in ORDER}
for it in items:
    bucket = classify(it.get("title",""), it.get("url",""))
    sections_map.setdefault(bucket, []).append(it)

sections = []
for title in ORDER:
    lst = sections_map.get(title, [])
    lst = cap_per_domain(lst, per_domain_cap)  # cap inside each section
    sections.append({"title": title, "items": lst})

sections = cap_per_domain_global(sections, per_domain_cap)  # global cap

# ---------- Headline & write ----------
headline_item = None
for s in sections:
    if s["items"]:
        headline_item = {"title": s["items"][0]["title"], "url": s["items"][0]["url"]}
        break
if not headline_item:
    headline_item = {"title": "ANTICEO", "url": "https://anticeo.com"}

news = {
    "generated_at": _nowz(),
    "headline": headline_item,
    "sections": sections,
}

OUT.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {OUT.name} with {sum(len(s['items']) for s in sections)} items "
      f"(cap={per_domain_cap}/domain; skipped={len(skip_domains)} domains)")
