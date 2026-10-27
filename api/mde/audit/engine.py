"""The audit engine: loads every source the site is built from, runs the rules in rules.json, and writes a workbook."""

from __future__ import annotations

import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from mde.catalogue.seedfiles import read_seed

HERE = Path(__file__).parent
API = HERE.parent
ROOT = API.parent.parent
CAT = API / "catalogue"
SEVERITIES = {"error": 0, "warning": 1, "info": 2}


@dataclass
class Finding:
    rule: str
    severity: str
    scope: str
    key: str
    message: str
    hint: str = ""


@dataclass
class Context:
    params: dict
    works: list[dict]
    taxonomy: dict
    shelves: dict
    gaps: dict
    provenance: dict
    observances: list[dict]
    calendar: dict
    audiobooks: dict
    blog: list[dict]
    relationships: list
    images: dict[str, list[dict]]
    texts: dict[str, str]
    site: Path | None = None
    pages: dict[str, dict] = field(default_factory=dict)
    sitemap: list[str] = field(default_factory=list)

    @property
    def term_keys(self) -> set[str]:
        return {f"{t['dimension']}:{t['slug']}" for t in self.taxonomy["terms"]}

    @property
    def by_slug(self) -> dict[str, dict]:
        return {w["slug"]: w for w in self.works}


def _json(path: Path):
    return json.loads(path.read_text())


def _images() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for f in (API / "data" / "enrichment").glob("*.json"):
        if f.name == "review.json":
            continue
        for slug, rec in _json(f).get("works", {}).items():
            out[slug].extend(rec.get("images") or [])
    return out


def _public_texts() -> dict[str, str]:
    files = ["demo/page.html", "demo/build.cjs", "demo/seo.cjs", "demo/blog.json", "README.md", "docs/FEATURES.md",
             *[str(p.relative_to(ROOT)) for p in sorted((ROOT / "docs" / "press").glob("*.md"))]]
    return {f: (ROOT / f).read_text() for f in files if (ROOT / f).exists()}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.h1 = 0
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self.h1 += 1
        elif tag == "meta" and a.get("name"):
            self.meta[a["name"].lower()] = a.get("content") or ""
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href") or ""
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def scan_site(site: Path) -> tuple[dict[str, dict], list[str]]:
    pages: dict[str, dict] = {}
    for f in sorted(site.rglob("*.html")):
        rel = "/" + str(f.relative_to(site)).replace("\\", "/")
        url = rel[: -len("index.html")] if rel.endswith("/index.html") else rel
        p = _Page()
        p.feed(f.read_text(errors="replace"))
        robots = p.meta.get("robots", "")
        pages[url] = {"file": rel, "title": p.title.strip(), "description": p.meta.get("description", ""), "canonical": p.canonical,
                      "h1": p.h1, "noindex": "noindex" in robots, "links": p.links}
    locs: list[str] = []
    for sm in sorted(site.glob("sitemap*.xml")):
        locs += re.findall(r"<loc>([^<]+)</loc>", sm.read_text())
    return pages, locs


def load_context(site: Path | None = None) -> Context:
    rules = _json(HERE / "rules.json")
    data = read_seed()
    blog = _json(ROOT / "demo" / "blog.json")["posts"] if (ROOT / "demo" / "blog.json").exists() else []
    ctx = Context(params=rules["params"], works=data["works"], taxonomy=_json(API / "taxonomy" / "taxonomy.json"),
                  shelves=_json(CAT / "shelves.json"), gaps=_json(CAT / "gaps.json"), provenance=_json(CAT / "reference-provenance.json")["works"],
                  observances=_json(CAT / "observances.json")["days"], calendar=_json(CAT / "calendar.json"),
                  audiobooks=_json(CAT / "audiobooks.json")["books"], blog=blog, relationships=data.get("relationships", []),
                  images=_images(), texts=_public_texts(), site=site)
    if site:
        ctx.pages, ctx.sitemap = scan_site(site)
    return ctx


# ---------------------------------------------------------------------------------------------------- checks
CHECKS: dict[str, Callable[[Context], Iterable[tuple[str, str]]]] = {}


def check(rule_id: str):
    def deco(fn):
        CHECKS[rule_id] = fn
        return fn
    return deco


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


@check("W001")
def _w001(c):
    for slug, n in Counter(w["slug"] for w in c.works).items():
        if n > 1:
            yield slug, f"{n} records share this slug"


@check("W002")
def _w002(c):
    for w in c.works:
        for f in ("slug", "title", "medium"):
            if not w.get(f):
                yield w.get("slug") or "?", f"missing {f}"
        if w.get("medium") != "channel" and w.get("year") is None:
            yield w["slug"], "missing year"


@check("W003")
def _w003(c):
    top = dt.date.today().year + c.params["year_future"]
    for w in c.works:
        y = w.get("year")
        if isinstance(y, int) and not (c.params["year_min"] <= y <= top):
            yield w["slug"], f"year {y} outside {c.params['year_min']} to {top}"


@check("W004")
def _w004(c):
    for w in c.works:
        for f in ("runtime_minutes", "playtime_hours", "page_count"):
            v = w.get(f) if f in w else (w.get("attributes") or {}).get(f)
            if v is None:
                continue
            if not isinstance(v, (int, float)) or v <= 0 or (f == "runtime_minutes" and v > c.params["runtime_max_minutes"]):
                yield w["slug"], f"{f} = {v!r}"


@check("W005")
def _w005(c):
    known = c.term_keys
    for w in c.works:
        for k in w.get("terms") or {}:
            if k not in known:
                yield w["slug"], f"unknown tag {k}"


@check("W006")
def _w006(c):
    for w in c.works:
        for k, v in (w.get("terms") or {}).items():
            s = v if isinstance(v, (int, float)) else (v[0] if isinstance(v, list) and v else None)
            if not isinstance(s, (int, float)) or not 0 <= s <= 1:
                yield w["slug"], f"{k} strength {v!r}"


@check("W007")
def _w007(c):
    pat = re.compile(c.params["placeholder_pattern"])
    for w in c.works:
        s = w.get("summary")
        if not s:
            continue
        n = len(s.split())
        if n < c.params["summary_min_words"]:
            yield w["slug"], f"summary has {n} words"
        elif len(s) > c.params["summary_max_chars"]:
            yield w["slug"], f"summary is {len(s)} characters"
        if pat.search(s):
            yield w["slug"], "summary contains placeholder text"


@check("W008")
def _w008(c):
    seen: dict[tuple, str] = {}
    for w in c.works:
        k = (_norm(w["title"]), w.get("year"), w["medium"])
        if k in seen and seen[k] != w["slug"]:
            yield w["slug"], f"same title, year and medium as {seen[k]}"
        seen.setdefault(k, w["slug"])


@check("W009")
def _w009(c):
    for w in c.works:
        if w["medium"] in ("channel", "online_video"):
            continue
        t = w.get("popularity_tier")
        if t not in (1, 2, 3, 4, 5):
            yield w["slug"], f"popularity_tier = {t!r}"


@check("W010")
def _w010(c):
    for w in c.works:
        for cc in w.get("countries") or []:
            if not re.fullmatch(r"[A-Z]{2}", cc):
                yield w["slug"], f"country {cc!r}"
        lang = w.get("language")
        if lang and not re.fullmatch(r"[a-z]{2,3}", lang):
            yield w["slug"], f"language {lang!r}"


@check("W011")
def _w011(c):
    for w in c.works:
        if w.get("summary") and w.get("terms") and w["medium"] not in ("channel", "online_video") and not w.get("advisories") and not w.get("ratings"):
            yield w["slug"], "classified but no advisories or age ratings"


@check("W012")
def _w012(c):
    for w in c.works:
        if w.get("summary") and w["medium"] not in ("channel", "online_video") \
                and not any(k.split(":")[0] in ("mood", "theme") for k in (w.get("terms") or {})):
            yield w["slug"], "summary but no mood or theme tags"


@check("W013")
def _w013(c):
    for w in c.works:
        if not w.get("summary") and w.get("popularity_tier") == 1 and w["medium"] not in ("channel", "online_video"):
            yield w["slug"], "tier 1, no summary"


@check("W014")
def _w014(c):
    for slug, imgs in c.images.items():
        for i in imgs:
            if not i.get("url") or not i.get("licence") or not i.get("attribution"):
                yield slug, f"image {i.get('url', '?')} lacks url, licence or attribution"


@check("W015")
def _w015(c):
    for w in c.works:
        if w.get("popularity_tier") == 1 and w["medium"] in ("film", "series", "book", "album") and not c.images.get(w["slug"]) and not w.get("images"):
            yield w["slug"], "tier 1, no real cover"


@check("W016")
def _w016(c):
    known = set(c.by_slug)
    for r in c.relationships:
        for end in (r[0], r[2]):
            if end not in known:
                yield f"{r[0]}->{r[2]}", f"unknown work {end}"


@check("T001")
def _t001(c):
    keys = [f"{t['dimension']}:{t['slug']}" for t in c.taxonomy["terms"]]
    for k, n in Counter(keys).items():
        if n > 1:
            yield k, "duplicate key"
    genres = {t["slug"] for t in c.taxonomy["terms"] if t["dimension"] == "genre"}
    for t in c.taxonomy["terms"]:
        if t.get("parent") and t["parent"] not in genres:
            yield f"{t['dimension']}:{t['slug']}", f"unknown parent {t['parent']}"


@check("T002")
def _t002(c):
    used = Counter(k for w in c.works for k in (w.get("terms") or {}))
    for k in sorted(c.term_keys):
        if not used[k] and not k.startswith("advisory:"):
            yield k, "no work carries this tag"


@check("T003")
def _t003(c):
    owner: dict[str, str] = {}
    for t in c.taxonomy["terms"]:
        for s in t.get("synonyms") or []:
            k = f"{t['dimension']}:{t['slug']}"
            if s.lower() in owner and owner[s.lower()] != k:
                yield s, f"claimed by {owner[s.lower()]} and {k}"
            owner.setdefault(s.lower(), k)


def _rule_tags(rule: dict) -> list[str]:
    return [*(rule.get("any_tags") or []), *(rule.get("all_tags") or [])]


@check("S001")
def _s001(c):
    known = c.term_keys
    for s, n in Counter(x["slug"] for x in c.shelves["shelves"]).items():
        if n > 1:
            yield s, "duplicate shelf slug"
    for s in c.shelves["shelves"]:
        for k in _rule_tags(s["rule"]):
            if k not in known:
                yield s["slug"], f"unknown tag {k}"


@check("S002")
def _s002(c):
    from mde.catalogue.memory import MemoryCatalogue
    cat = MemoryCatalogue.from_seed()
    minimum = c.shelves.get("min_works", 3)
    shown = {s["slug"]: s["total"] for s in cat.shelves()}
    for s in c.shelves["shelves"]:
        if shown.get(s["slug"], 0) < minimum:
            yield s["slug"], f"{shown.get(s['slug'], 0)} works (minimum {minimum})"


@check("C001")
def _c001(c):
    tally: Counter = Counter()
    for gaps in c.gaps["works"].values():
        tally.update(gaps)
    for k, n in c.gaps["totals"].items():
        if tally[k] != n:
            yield k, f"gaps.json says {n}, the works list {tally[k]}"
    slugs = set(c.by_slug)
    for s in c.gaps["works"]:
        if s not in slugs:
            yield s, "gaps.json names an unknown work"


@check("C002")
def _c002(c):
    slugs = set(c.by_slug)
    for s in c.provenance:
        if s not in slugs:
            yield s, "provenance for an unknown work"


@check("C003")
def _c003(c):
    known = c.term_keys
    for o in c.observances:
        if "date" in o:
            try:
                dt.date(2024, int(o["date"][:2]), int(o["date"][3:5]))
            except ValueError:
                yield o.get("slug", "?"), f"bad date {o.get('date')!r}"
        elif "nth" not in o:
            yield o.get("slug", "?"), "neither a date nor an nth rule"
        for k in _rule_tags(o.get("rule") or {}):
            if k not in known:
                yield o["slug"], f"unknown tag {k}"
    for p in c.calendar["programmes"]:
        for k in _rule_tags(p.get("rule") or {}):
            if k not in known:
                yield p["slug"], f"unknown tag {k}"


@check("C004")
def _c004(c):
    slugs = set(c.by_slug)
    for w in c.works:
        if w["medium"] == "online_video":
            ch = (w.get("attributes") or {}).get("channel")
            if not ch or ch not in slugs:
                yield w["slug"], f"channel {ch!r} not in the catalogue"


@check("C005")
def _c005(c):
    slugs = set(c.by_slug)
    for s in c.audiobooks:
        if s not in slugs:
            yield s, "audiobook for an unknown work"


@check("C006")
def _c006(c):
    for s, n in Counter(p["slug"] for p in c.blog).items():
        if n > 1:
            yield s, "duplicate post slug"
    for p in c.blog:
        try:
            dt.date.fromisoformat(p["date"])
        except (ValueError, KeyError):
            yield p.get("slug", "?"), f"bad date {p.get('date')!r}"
        if not (p.get("body") or p.get("content")):
            yield p["slug"], "empty body"


@check("B001")
def _b001(c):
    for spec in c.params["banned_public_strings"]:
        pat = re.compile(spec["pattern"])
        for f, text in c.texts.items():
            for m in pat.finditer(text):
                yield f"{f}", f"{spec['why']}: {m.group(0)!r}"
                break


@check("B002")
def _b002(c):
    works = len(c.works)
    countries = len({cc for w in c.works for cc in w.get("countries") or []})
    langs = len({w["language"] for w in c.works if w.get("language")})
    for f in c.params["stale_count_files"]:
        text = c.texts.get(f)
        if not text:
            continue
        for m in re.finditer(r"(about |roughly |nearly )?([\d,]{3,6}) works from (\d+) countries", text, re.I):
            n, k = int(m.group(2).replace(",", "")), int(m.group(3))
            ok_w = abs(n - works) / works <= 0.05 if m.group(1) else n == works
            if not ok_w or k != countries:
                yield f, f"says {m.group(0)!r}; the catalogue has {works} works from {countries} countries"
        for m in re.finditer(r"(\d+) original languages", text):
            if int(m.group(1)) != langs:
                yield f, f"says {m.group(0)!r}; the catalogue has {langs}"


def _url_file(site: Path, url: str) -> Path | None:
    path = url.split("#")[0].split("?")[0]
    if not path.startswith("/") or path.startswith("//"):
        return None
    for cand in (site / path.lstrip("/"), site / path.lstrip("/") / "index.html"):
        if cand.is_file():
            return cand
    return site / path.lstrip("/")


@check("P001")
def _p001(c):
    for url, p in c.pages.items():
        if p["file"] == "/404.html":
            continue
        bad = [n for n, ok in (("title", p["title"]), ("description", p["description"]), ("canonical", p["canonical"]), ("one H1", p["h1"] == 1)) if not ok]
        if bad:
            yield url, "missing " + ", ".join(bad)


@check("P002")
def _p002(c):
    if not c.site:
        return
    seen: set[tuple[str, str]] = set()
    for url, p in c.pages.items():
        for href in p["links"]:
            if href.startswith(("#", "mailto:", "tel:", "http", "javascript:")) or (url, href) in seen:
                continue
            seen.add((url, href))
            target = _url_file(c.site, href)
            if target is not None and not target.is_file():
                yield url, f"link to {href} has no page"


@check("P003")
def _p003(c):
    base = "https://mimir.terratalesmedia.world"
    for loc in c.sitemap:
        path = loc[len(base):] if loc.startswith(base) else loc
        page = c.pages.get(path)
        if page is None:
            yield loc, "listed in the sitemap but not built"
        elif page["noindex"]:
            yield loc, "listed in the sitemap but marked noindex"


@check("P004")
def _p004(c):
    if not c.sitemap:
        return
    base = "https://mimir.terratalesmedia.world"
    listed = {loc[len(base):] if loc.startswith(base) else loc for loc in c.sitemap}
    for url, p in c.pages.items():
        if not p["noindex"] and p["file"] != "/404.html" and url not in listed:
            yield url, "indexable but not in the sitemap"


@check("P005")
def _p005(c):
    for url, p in c.pages.items():
        if len(p["title"]) > c.params["title_max_chars"]:
            yield url, f"title is {len(p['title'])} characters"
        if len(p["description"]) > c.params["description_max_chars"]:
            yield url, f"description is {len(p['description'])} characters"


# ---------------------------------------------------------------------------------------------------- running
def load_rules() -> dict:
    return _json(HERE / "rules.json")


def load_baseline(path: Path | None = None) -> set[tuple[str, str]]:
    p = path or HERE / "baseline.json"
    if not p.exists():
        return set()
    return {(a["rule"], a["key"]) for a in _json(p).get("accepted", [])}


def run_audit(ctx: Context | None = None, only: set[str] | None = None, baseline: set[tuple[str, str]] | None = None) -> tuple[Context, list[Finding]]:
    ctx = ctx or load_context()
    baseline = load_baseline() if baseline is None else baseline
    out: list[Finding] = []
    for rule in load_rules()["rules"]:
        rid = rule["id"]
        if only and rid not in only:
            continue
        for key, msg in CHECKS[rid](ctx):
            if (rid, key) not in baseline:
                out.append(Finding(rid, rule["severity"], rule["scope"], key, msg, rule["hint"]))
    out.sort(key=lambda f: (SEVERITIES[f.severity], f.rule, f.key, f.message))
    return ctx, out


# ---------------------------------------------------------------------------------------------------- workbook
def _sheets(ctx: Context, findings: list[Finding]) -> dict[str, tuple[list[str], list[list]]]:
    terms = {f"{t['dimension']}:{t['slug']}": t for t in ctx.taxonomy["terms"]}
    used: Counter = Counter()
    strong: Counter = Counter()
    for w in ctx.works:
        for k, v in (w.get("terms") or {}).items():
            used[k] += 1
            if (v if isinstance(v, (int, float)) else v[0]) >= 0.6:
                strong[k] += 1
    people: dict[str, dict] = {}
    works_rows = []
    for w in ctx.works:
        credits = w.get("credits") or []
        for role, name in ((c[0], c[1]) for c in credits):
            p = people.setdefault(name, {"roles": Counter(), "works": 0})
            p["roles"][role] += 1
            p["works"] += 1
        tops = sorted((w.get("terms") or {}).items(), key=lambda kv: -(kv[1] if isinstance(kv[1], (int, float)) else kv[1][0]))
        by_dim: dict[str, list[str]] = defaultdict(list)
        for k, _ in tops:
            by_dim[k.split(":")[0]].append(k.split(":")[1])
        attrs = w.get("attributes") or {}
        imgs = ctx.images.get(w["slug"], [])
        works_rows.append([
            w["slug"], w["title"], w["medium"], w.get("year"), w.get("language"), ", ".join(w.get("countries") or []), w.get("popularity_tier"),
            w.get("runtime_minutes"), w.get("playtime_hours"), attrs.get("page_count"), attrs.get("episodes"),
            ", ".join(c[1] for c in credits if c[0] in ("director", "creator", "author", "developer", "artist", "studio")),
            ", ".join(c[1] for c in credits if c[0] == "actor"),
            "yes" if w.get("summary") else "no", len((w.get("summary") or "").split()),
            ", ".join(by_dim["genre"][:6]), ", ".join(by_dim["mood"][:6]), ", ".join(by_dim["theme"][:6]),
            ", ".join(f"{k}:{v[0] if isinstance(v, list) else v}" for k, v in (w.get("advisories") or {}).items() if (v[0] if isinstance(v, list) else v)),
            attrs.get("series") or "", ", ".join(attrs.get("franchises") or []), len(imgs), imgs[0]["url"] if imgs else "", imgs[0].get("licence", "") if imgs else "",
            ctx.provenance.get(w["slug"], {}).get("qid", ""), ", ".join(ctx.gaps["works"].get(w["slug"], [])),
            sum(1 for f in findings if f.key == w["slug"]),
        ])
    sheets: dict[str, tuple[list[str], list[list]]] = {}
    sheets["Works"] = (["slug", "title", "medium", "year", "language", "countries", "tier", "runtime min", "playtime h", "pages", "episodes",
                        "creators", "cast", "has summary", "summary words", "genres", "moods", "themes", "advisories", "series", "franchises",
                        "images", "cover url", "cover licence", "wikidata", "gaps", "findings"], works_rows)
    sheets["Tags"] = (["key", "dimension", "label", "parent", "works", "strong (0.6+)", "synonyms", "definition"],
                      [[k, t["dimension"], t["label"], t.get("parent", ""), used[k], strong[k], ", ".join(t.get("synonyms") or []), t["definition"]]
                       for k, t in sorted(terms.items())])
    sheets["People"] = (["name", "works", "roles"], [[n, p["works"], ", ".join(f"{r} ({c})" for r, c in p["roles"].most_common())]
                                                    for n, p in sorted(people.items(), key=lambda kv: (-kv[1]["works"], kv[0]))])
    groups: dict[str, list[str]] = defaultdict(list)
    for w in ctx.works:
        a = w.get("attributes") or {}
        for g in [a.get("series"), *(a.get("franchises") or [])]:
            if g:
                groups[g].append(w["slug"])
    sheets["Franchises"] = (["group", "works", "media", "slugs"], [[g, len(s), ", ".join(sorted({ctx.by_slug[x]["medium"] for x in s})), ", ".join(s[:40])]
                                                                  for g, s in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))])
    sheets["Shelves"] = (["slug", "name", "tagline", "rule"], [[s["slug"], s["name"], s.get("tagline", ""), json.dumps(s["rule"])] for s in ctx.shelves["shelves"]])
    sheets["Days"] = (["slug", "name", "date", "kind", "why", "rule"], [[o["slug"], o["name"], o.get("date") or f"nth {o.get('nth')}", o.get("kind", ""), o.get("why", ""), json.dumps(o.get("rule"))]
                                                                          for o in ctx.observances])
    yt = [w for w in ctx.works if w["medium"] in ("channel", "online_video")]
    sheets["YouTube"] = (["slug", "title", "medium", "year", "channel", "genres"], [[w["slug"], w["title"], w["medium"], w.get("year"), (w.get("attributes") or {}).get("channel", ""),
                                                                                    ", ".join(k.split(":")[1] for k in (w.get("terms") or {}) if k.startswith("genre:"))] for w in yt])
    sheets["Audiobooks"] = (["slug", "title", "narrators", "minutes", "url"], [[s, ctx.by_slug.get(s, {}).get("title", "?"), ", ".join(a["audible"].get("narrators", [])),
                                                                               a["audible"].get("minutes"), a["audible"].get("url", "")] for s, a in ctx.audiobooks.items()])
    sheets["Blog"] = (["slug", "date", "title", "tags"], [[p["slug"], p["date"], p["title"], ", ".join(p.get("tags", []))] for p in ctx.blog])
    if ctx.pages:
        listed = set(ctx.sitemap)
        sheets["Pages"] = (["url", "title", "description", "canonical", "h1", "indexable", "in sitemap", "internal links"],
                           [[u, p["title"], p["description"], p["canonical"], p["h1"], "no" if p["noindex"] else "yes",
                             "yes" if any(loc.endswith(u) for loc in listed) else "no", len(p["links"])] for u, p in sorted(ctx.pages.items())])
    rules = load_rules()["rules"]
    sheets["Rules"] = (["id", "severity", "scope", "title", "hint"], [[r["id"], r["severity"], r["scope"], r["title"], r["hint"]] for r in rules])
    sheets["Findings"] = (["severity", "rule", "scope", "key", "message", "hint"], [[f.severity, f.rule, f.scope, f.key, f.message, f.hint] for f in findings])
    counts = Counter(f.severity for f in findings)
    per_rule = Counter(f.rule for f in findings)
    med = Counter(w["medium"] for w in ctx.works)
    summary = [["generated", dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M UTC")], ["works", len(ctx.works)], *[[f"  {m}", n] for m, n in sorted(med.items())],
               ["with summary", sum(1 for w in ctx.works if w.get("summary"))], ["tags", len(terms)],
               ["countries", len({cc for w in ctx.works for cc in w.get("countries") or []})],
               ["original languages", len({w["language"] for w in ctx.works if w.get("language")})],
               ["errors", counts["error"]], ["warnings", counts["warning"]], ["info", counts["info"]],
               *[[f"  {r}", n] for r, n in sorted(per_rule.items())]]
    sheets["Summary"] = (["item", "value"], summary)
    order = ["Summary", "Findings", "Rules", "Works", "Tags", "People", "Franchises", "Shelves", "Days", "YouTube", "Audiobooks", "Blog", "Pages"]
    return {k: sheets[k] for k in order if k in sheets}


def write_workbook(ctx: Context, findings: list[Finding], out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    sheets = _sheets(ctx, findings)
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:   # no openpyxl: one CSV per sheet and an index
        folder = out / "mimir-audit"
        folder.mkdir(exist_ok=True)
        for name, (head, rows) in sheets.items():
            with open(folder / f"{name}.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(head)
                w.writerows(rows)
        return folder
    wb = Workbook()
    wb.remove(wb.active)
    for name, (head, rows) in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(head)
        for r in rows:
            ws.append([("" if v is None else (v if isinstance(v, (int, float, str)) else str(v))) for v in r])
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2B2A25")
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, h in enumerate(head, 1):
            longest = max([len(str(h))] + [len(str(r[i - 1])) for r in rows[:300] if r[i - 1] is not None])
            ws.column_dimensions[get_column_letter(i)].width = min(60, max(10, longest + 2))
    path = out / "mimir-audit.xlsx"
    wb.save(path)
    return path


def markdown_report(findings: list[Finding], hints: bool = False, limit: int = 25) -> str:
    by_rule: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_rule[f.rule].append(f)
    lines = [f"# Mimir audit: {sum(f.severity == 'error' for f in findings)} errors, {sum(f.severity == 'warning' for f in findings)} warnings, "
             f"{sum(f.severity == 'info' for f in findings)} notes", ""]
    for rid, fs in sorted(by_rule.items(), key=lambda kv: (SEVERITIES[kv[1][0].severity], kv[0])):
        titles = {r["id"]: r["title"] for r in load_rules()["rules"]}
        lines.append(f"## {rid} {titles[rid]} ({fs[0].severity}, {len(fs)})")
        if hints:
            lines.append(f"_{fs[0].hint}_")
        lines += [f"- `{f.key}`: {f.message}" for f in fs[:limit]]
        if len(fs) > limit:
            lines.append(f"- … and {len(fs) - limit} more")
        lines.append("")
    return "\n".join(lines)
