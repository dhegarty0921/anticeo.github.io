#!/usr/bin/env python3
import json, pathlib, datetime, re
from urllib.parse import urlparse

# ---------- Inputs ----------
NDJSON = pathlib.Path("scraper_out.ndjson")
OUT    = pathlib.Path("anticeo-news.json")
CFG    = pathlib.Path("categories.yml")   # optional

# ---------- Optional YAML config ----------
skip_domains = set()
per_domain_cap = 3
max_age_days = 4

try:
    import yaml                      # pip install pyyaml
    if CFG.exists():
        cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
        skip_domains = set(cfg.get("skip_domains") or [])
        per_domain_cap = int(cfg.get("per_domain_cap", per_domain_cap))
        max_age_days = int(cfg.get("max_age_days", max_age_days))
except Exception:
    pass

# ---------- Helpers ----------
def _nowz() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)

def parse_ts(ts: str):
    """Parse RSS (RFC-822) or ISO-8601 timestamps; unparseable -> None."""
    if not ts:
        return None
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(ts)
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None

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

# Hosts with a relaxed PER-SECTION cap: news.google.com is a proxy for
# several DISTINCT real sources (site: mirrors), and the caps exist to stop
# one site dominating. Still bounded so one noisy mirror query (name
# collisions, a viral corporate saga) can't flood a section. Exempt from the
# global cap, since the proxied sources genuinely differ.
CAP_LAX_HOSTS = {"news.google.com": 8}

def cap_per_domain(items, max_per: int):
    counts, out = {}, []
    for it in items:
        host = _host(it.get("url",""))
        if not host:  # keep unknowns
            out.append(it); continue
        limit = CAP_LAX_HOSTS.get(host, max_per)
        if counts.get(host, 0) < limit:
            out.append(it)
            counts[host] = counts.get(host, 0) + 1
    return out

def cap_per_domain_global(sections, max_per: int):
    counts = {}
    for sec in sections:
        kept = []
        for it in sec.get("items", []):
            host = _host(it.get("url",""))
            if not host or host in CAP_LAX_HOSTS:
                kept.append(it); continue
            if counts.get(host, 0) < max_per:
                kept.append(it)
                counts[host] = counts.get(host, 0) + 1
        sec["items"] = kept
    return sections

# ---------- Section rules ----------
# Classification priority = list order (first match wins), which is decoupled
# from display order (ORDER below): the settler-colonial rule is checked FIRST
# so its specific keywords beat the generic "israel"/"iran" hits in MILITARY
# INDUSTRIAL COMPLEX, but it still RENDERS at the bottom of the page.
RULES = [
    {"title":"YOU LIVE IN A SHITHOLE COUNTRY",
     "domains":[],
     "any":[
            # trump family / kushner — specific people and entities
            "jared kushner","kushner","ivanka","donald trump jr","don jr",
            "eric trump","trump organization","trump org","trump family",
            # corruption vocabulary
            "corrupt","corruption","bribery","bribe","graft","grift","grifter",
            "emoluments","kickback","pay to play","pay-to-play",
            "conflict of interest","self-dealing","kleptocracy","cronyism",
            "dark money","revolving door","quid pro quo",
            # legal milestones
            "indictment","indicted","convicted","guilty plea","pleaded guilty",
            "wire fraud","tax fraud","bank fraud","securities fraud",
            "insurance fraud","racketeering",
            ]},
    {"title":"ICE IS A DRESS REHEARSAL FOR STATE REPRESSION",
     "domains":[],
     "any":["ice","ice agents","abolish ice",
            "immigration and customs enforcement",
            "deportation","deportations","deported","deporting",
            "immigration raid","immigration raids","ice raid","ice raids",
            "detention","detainee","detained","detaining",
            "immigrant","immigrants","immigration","migrant","migrants",
            "asylum","daca","dreamers","sanctuary city","sanctuary cities",
            "border patrol","customs and border protection","cbp",
            "kristi noem","tom homan","greg bovino",
            "masked agents","masked officer","masked officers"]},
    {"title":"SETTLER COLONIAL STATE FALSE FLAG LIES",
     "domains":[],
     "any":["netanyahu","ben-gvir","ben gvir","bengvir","gvir","itamar",
            "aipac","adl","anti-defamation league",
            "threatens iran","threatened iran","threatens war on iran",
            "strike on iran","strikes on iran","attacked iran","attack iran",
            "bomb iran","bombing iran","war on iran","war with iran",
            "israel threatens","israeli threats"]},
    {"title":"CHUDS VS SHITLIBS",
     "domains":["thehill.com","realclearpolitics.com","washingtontimes.com","politico.com","npr.org","nytimes.com","bbc.com","headlineusa.com"],
     "any":["trump","biden","democrat","republican","gop","election","primary","congress","senate","house","white house","campaign"]},
    {"title":"CULTURE WAR",
     "domains":["religionnews.com","pinknews.co.uk","vox.com","nationalreview.com","theatlantic.com","theguardian.com","tabletmag.com","christianitytoday.com"],
     "any":["lgbt","trans","religion","church","faith","dei","campus","pronoun","abortion","book ban","school board","drag","culture war","race","crt"]},
    {"title":"MILITARY INDUSTRIAL COMPLEX",
     "domains":["defenseone.com","twz.com","warontherocks.com","navalnews.com","armytimes.com","aljazeera.com","reuters.com","dw.com","antiwar.com","quincyinst.org","scheerpost.com","venezuelanalysis.com","mintpressnews.com","rss.dw.com","electronicintifada.net"],
     "any":["israel","gaza","palestin","ukraine","nato","pentagon","defense","weapons","missile","airstrike","drone","war","military","army","navy","marines","iran","yemen","hezbollah","taiwan","venezuela"]},
    {"title":"PARA POLITICAL INTRIGUE",
     # aclu.org intentionally NOT domain-pinned: its heavy ICE/detention coverage
     # must route to the ICE section by keyword; other ACLU items still match
     # PARA keywords (foia, surveillance, doj, ...) below.
     "domains":["lawfaremedia.org","eff.org","techdirt.com","justsecurity.org","theintercept.com","scheerpost.com","unlimitedhangout.com","dropsitenews.com"],
     "any":["cia","fbi","nsa","surveillance","whistleblower","leak","foia","spy","informant","homeland security","doj","dhs","patriot act","9/11","oklahoma city","okc bombing"]}
]
ORDER = ["CHUDS VS SHITLIBS","YOU LIVE IN A SHITHOLE COUNTRY","CULTURE WAR","MILITARY INDUSTRIAL COMPLEX",
         "PARA POLITICAL INTRIGUE","SETTLER COLONIAL STATE FALSE FLAG LIES",
         "ICE IS A DRESS REHEARSAL FOR STATE REPRESSION"]

def classify(title: str, url: str) -> str:
    t = (title or "").lower()
    h = _host(url or "")
    for r in RULES:                 # domain first
        if h in (r.get("domains") or []):
            return r["title"]
    for r in RULES:                 # keyword next
        for kw in (r.get("any") or []):
            # word-boundary match so "adl" doesn't fire inside "headlines"
            if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", t):
                return r["title"]
    return ORDER[0]                 # default to first DISPLAY section (CHUDS)

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
            "section": rec.get("section") or "",
        })

# ---------- Dedupe, classify, cap ----------
items = dedupe_by_url(items)

# Drop items past their shelf life: feeds re-list the same top stories for
# days, which made the page look frozen. Unparseable ts -> keep (treat as new).
cutoff = _now() - datetime.timedelta(days=max_age_days)
items = [it for it in items
         if (t := parse_ts(it.get("ts"))) is None or t >= cutoff]

def _ts_key(it):
    t = parse_ts(it.get("ts"))
    return t.timestamp() if t else _now().timestamp() + 86400  # unparseable last

sections_map = {t: [] for t in ORDER}
for it in items:
    bucket = it.get("section") or classify(it.get("title",""), it.get("url",""))
    sections_map.setdefault(bucket, []).append(it)

sections = []
for title in ORDER:
    lst = sections_map.get(title, [])
    lst.sort(key=_ts_key, reverse=True)        # freshest first, so the cap keeps news
    lst = cap_per_domain(lst, per_domain_cap)  # cap inside each section
    sections.append({"title": title, "items": lst})

sections = cap_per_domain_global(sections, per_domain_cap)  # global cap
for sec in sections:
    sec["items"].sort(key=_ts_key, reverse=True)  # re-sort after global cap

# ---------- Headline & write ----------
headline_item = None
newest = None
for s in sections:
    for it in s["items"]:
        if newest is None or _ts_key(it) > _ts_key(newest):
            newest = it
if newest:
    headline_item = {"title": newest["title"], "url": newest["url"]}
else:
    headline_item = {"title": "ANTICEO", "url": "https://anticeo.com"}

news = {
    "generated_at": _nowz(),
    "headline": headline_item,
    "sections": sections,
}

OUT.write_text(json.dumps(news, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {OUT.name} with {sum(len(s['items']) for s in sections)} items "
      f"(cap={per_domain_cap}/domain; skipped={len(skip_domains)} domains)")
