"""Catalogue views: browse with filters and facets, tag pages, people pages and full work pages.

Pure functions over WorkProfile lists, so the API (PostgreSQL-backed) and the browser demo (seed file)
render identical pages. demo/engine.cjs mirrors this module; tests/test_demo_parity.py checks they agree.

At pilot scale every view is computed in memory over the whole catalogue. Before the catalogue reaches tens
of thousands of works, browse filtering and facet counts move into SQL with the same output shape.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from mde.catalogue.model import RELATIONSHIP_TYPES, WorkProfile, normalise_title, severity, slugify
from mde.taxonomy import Taxonomy

TAG_DIMENSIONS = ["genre", "theme", "mood", "pacing", "complexity", "narrative", "world", "style"]
TAG_THRESHOLD = 0.4      # a term is shown as a tag (and counted in facets) at or above this strength
SUITABLE_BELOW = 0.45    # "avoid X" in browse keeps works assessed as None or Mild for X
SORTS = ("popular", "title", "newest", "oldest", "shortest")


@dataclass
class BrowseFilters:
    media: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)        # taxonomy keys, all required
    decade: int | None = None
    language: str | None = None
    country: str | None = None
    max_minutes: int | None = None                       # works of unknown length are excluded
    avoid: list[str] = field(default_factory=list)       # advisory keys; unassessed works are excluded
    exclude: list[str] = field(default_factory=list)     # taxonomy keys that must not apply
    year_min: int | None = None
    year_max: int | None = None
    q: str = ""                                          # title, original title or credited name
    sort: str = "popular"


def length_text(w: WorkProfile) -> str | None:
    approx = "~" if w.length_is_estimate else ""
    if w.runtime_minutes:
        return f"{approx}{w.runtime_minutes} min"
    if w.playtime_hours:
        return f"{approx}{w.playtime_hours:g} h"
    return None


def basis(is_interpretation: bool, review_status: str) -> str:
    if not is_interpretation:
        return "catalogue"
    return "interpretation" if review_status != "reviewed" else "reviewed_interpretation"


def _tags(w: WorkProfile, dimensions: list[str]) -> list[tuple[str, float]]:
    found = [(k, ev.strength) for k, ev in w.terms.items()
             if k.split(":")[0] in dimensions and ev.strength >= TAG_THRESHOLD]
    return sorted(found, key=lambda kv: (-kv[1], kv[0]))


def _guide_flags(w: WorkProfile, tax: Taxonomy) -> list[dict]:
    """Guide groups rated Moderate or Severe, for compact display on cards."""
    flags = []
    for group, label in tax.guide_groups:
        levels = [ev.strength for k, ev in w.terms.items()
                  if k.startswith("advisory:") and tax.get(k).group == group]
        if levels and max(levels) >= SUITABLE_BELOW:
            flags.append({"group": group, "label": label, "severity": severity(max(levels))})
    return flags


def card(w: WorkProfile, tax: Taxonomy) -> dict:
    return {
        "slug": w.slug, "title": w.title, "original_title": w.original_title, "medium": w.medium, "year": w.year,
        "length": length_text(w), "creators": w.creators, "summary": w.summary,
        "genres": [{"key": k, "label": tax.get(k).label} for k, _ in _tags(w, ["genre"])],
        "tags": [{"key": k, "label": tax.get(k).label} for k, _ in _tags(w, TAG_DIMENSIONS[1:])[:4]],
        "ratings": [{"system": r.system, "rating": r.rating} for r in w.ratings],
        "guide_flags": _guide_flags(w, tax),
    }


def _matches(w: WorkProfile, f: BrowseFilters) -> bool:
    if f.media and w.medium not in f.media:
        return False
    if any(w.strength(t) < TAG_THRESHOLD for t in f.tags):
        return False
    if f.decade is not None and (w.year is None or w.year // 10 * 10 != f.decade):
        return False
    if any(w.strength(t) >= TAG_THRESHOLD for t in f.exclude):
        return False
    if f.year_min is not None and (w.year is None or w.year < f.year_min):
        return False
    if f.year_max is not None and (w.year is None or w.year > f.year_max):
        return False
    if f.language and w.language != f.language:
        return False
    if f.country and f.country not in w.countries:
        return False
    if f.max_minutes is not None and (w.length_minutes is None or w.length_minutes > f.max_minutes):
        return False
    for key in f.avoid:
        ev = w.terms.get(key)
        if ev is None or ev.strength >= SUITABLE_BELOW:
            return False
    if f.q:
        needle = f.q.strip().lower()
        haystack = [w.title, w.original_title or "", *(c.name for c in w.credits)]
        if not any(needle in h.lower() for h in haystack):
            return False
    return True


def _sort_key(w: WorkProfile, f: BrowseFilters):
    title = normalise_title(w.title)
    if f.sort == "title":
        return (title,)
    if f.sort == "newest":
        return (-(w.year or 0), title)
    if f.sort == "oldest":
        return (w.year or 9999, title)
    if f.sort == "shortest":
        return (w.length_minutes if w.length_minutes is not None else 10**9, title)
    if f.tags:  # "popular" with tags selected: strongest matches first
        return (-round(sum(w.strength(t) for t in f.tags), 6), w.popularity_tier or 5, title)
    return (w.popularity_tier or 5, title)


def _facet(counter: Counter, label) -> list[dict]:
    items = [{"value": v, "label": label(v), "count": n} for v, n in counter.items()]
    return sorted(items, key=lambda x: (-x["count"], str(x["label"])))


def browse(works: list[WorkProfile], tax: Taxonomy, f: BrowseFilters) -> dict:
    hits = sorted((w for w in works if _matches(w, f)), key=lambda w: _sort_key(w, f))
    media, decades, languages = Counter(), Counter(), Counter()
    by_dim: dict[str, Counter] = {d: Counter() for d in ("genre", "theme", "mood")}
    for w in hits:
        media[w.medium] += 1
        if w.year is not None:
            decades[w.year // 10 * 10] += 1
        if w.language:
            languages[w.language] += 1
        for k, _ in _tags(w, list(by_dim)):
            by_dim[k.split(":")[0]][k] += 1
    ctx = _context(works)
    return {
        "total": len(hits),
        "results": [_rich_card(w, tax, ctx) for w in hits],
        "facets": {
            "medium": _facet(media, lambda v: v),
            "decade": sorted(({"value": d, "label": f"{d}s", "count": n} for d, n in decades.items()),
                             key=lambda x: -x["value"]),
            "language": _facet(languages, lambda v: v),
            **{d: _facet(c, lambda v: tax.get(v).label)[:12] for d, c in by_dim.items()},
        },
    }


def tag_index(works: list[WorkProfile], tax: Taxonomy) -> list[dict]:
    """Every tag in use, grouped by dimension, with how many works carry it."""
    counts: Counter = Counter()
    for w in works:
        for k, _ in _tags(w, TAG_DIMENSIONS):
            counts[k] += 1
    out = []
    for d in TAG_DIMENSIONS:
        terms = [{"key": t.key, "label": t.label, "count": counts[t.key]} for t in tax.in_dimension(d) if counts[t.key]]
        if terms:
            out.append({"dimension": d, "label": tax.dimensions[d].label,
                        "terms": sorted(terms, key=lambda x: (-x["count"], x["label"]))})
    return out


def tag_page(works: list[WorkProfile], tax: Taxonomy, key: str) -> dict | None:
    if key not in tax.terms:
        return None
    term = tax.get(key)
    ctx = _context(works)
    tagged = sorted((w for w in works if w.strength(key) >= TAG_THRESHOLD),
                    key=lambda w: (-w.strength(key), normalise_title(w.title)))
    related: Counter = Counter()
    for w in tagged:
        for k, _ in _tags(w, TAG_DIMENSIONS):
            if k != key:
                related[k] += 1
    return {
        "key": key, "label": term.label, "definition": term.definition, "dimension": term.dimension,
        "dimension_label": tax.dimensions[term.dimension].label, "applies_to": list(term.applies_to),
        "works": [{**_rich_card(w, tax, ctx), "strength": w.strength(key)} for w in tagged],
        "related": [{"key": k, "label": tax.get(k).label, "count": n}
                    for k, n in sorted(related.items(), key=lambda kv: (-kv[1], tax.get(kv[0]).label))[:10]],
    }


def people_index(works: list[WorkProfile]) -> list[dict]:
    people: dict[str, dict] = {}
    for w in works:
        for c in w.credits:
            p = people.setdefault(slugify(c.name), {"slug": slugify(c.name), "name": c.name, "kind": c.kind,
                                                     "roles": [], "count": 0, "_works": set()})
            if c.role not in p["roles"]:
                p["roles"].append(c.role)
            p["_works"].add(w.slug)
    for p in people.values():
        p["count"] = len(p.pop("_works"))
        p["roles"].sort()
    return sorted(people.values(), key=lambda p: (-p["count"], p["name"]))


def person_page(works: list[WorkProfile], tax: Taxonomy, slug: str) -> dict | None:
    credited = []
    name = kind = None
    for w in works:
        roles = [c.role for c in w.credits if slugify(c.name) == slug]
        if roles:
            c = next(c for c in w.credits if slugify(c.name) == slug)
            name, kind = c.name, c.kind
            credited.append((w, roles))
    if not credited:
        return None
    credited.sort(key=lambda wr: (-(wr[0].year or 0), normalise_title(wr[0].title)))
    ctx = _context(works)
    roles = sorted({r for _, rs in credited for r in rs})
    themes: Counter = Counter()
    for w, _ in credited:
        for k, _s in _tags(w, ["theme", "mood"]):
            themes[k] += 1
    return {
        "slug": slug, "name": name, "kind": kind, "roles": roles,
        "works": [{**_rich_card(w, tax, ctx), "roles": rs} for w, rs in credited],
        "recurring_tags": [{"key": k, "label": tax.get(k).label, "count": n}
                           for k, n in sorted(themes.items(), key=lambda kv: (-kv[1], tax.get(kv[0]).label)) if n > 1][:8],
    }


def parents_guide(w: WorkProfile, tax: Taxonomy) -> dict:
    groups = []
    for group, label in tax.guide_groups:
        items = []
        for term in tax.in_dimension("advisory"):
            if term.group != group:
                continue
            ev = w.terms.get(term.key)
            items.append({
                "key": term.key, "label": term.label, "definition": term.definition, "assessed": ev is not None,
                "level": ev.strength if ev else None, "severity": severity(ev.strength) if ev else "Not assessed",
                "note": ev.note if ev else None, "spoiler_note": ev.spoiler_note if ev else None,
                "basis": basis(ev.is_interpretation, ev.review_status) if ev else None,
            })
        assessed = [i for i in items if i["assessed"]]
        groups.append({
            "slug": group, "label": label,
            "severity": severity(max(i["level"] for i in assessed)) if assessed else "Not assessed",
            "partial": 0 < len(assessed) < len(items),
            "items": items,
        })
    return {
        "ratings": [{"system": r.system, "rating": r.rating, "reason": r.reason} for r in w.ratings],
        "assessed": any(g["severity"] != "Not assessed" for g in groups),
        "groups": groups,
    }


def work_page(w: WorkProfile, works: list[WorkProfile], tax: Taxonomy) -> dict:
    by_slug = {x.slug: x for x in works}
    tags = []
    for d in TAG_DIMENSIONS:
        terms = [{"key": k, "label": tax.get(k).label, "definition": tax.get(k).definition, "strength": ev.strength,
                  "confidence": ev.confidence, "basis": basis(ev.is_interpretation, ev.review_status)}
                 for k, ev in w.terms.items() if k.split(":")[0] == d and ev.strength > 0]
        if terms:
            tags.append({"dimension": d, "label": tax.dimensions[d].label,
                         "terms": sorted(terms, key=lambda t: (-t["strength"], t["key"]))})
    relationships = sorted(
        ({"label": r.label, "type": r.type, "factual": r.factual, "slug": r.other_slug, "title": r.other_title,
          "medium": r.other_medium, "year": by_slug[r.other_slug].year if r.other_slug in by_slug else None,
          "note": r.note, "confidence": r.confidence} for r in w.relations),
        key=lambda r: (not r["factual"], -r["confidence"], r["title"]))
    return {
        "slug": w.slug, "medium": w.medium, "title": w.title, "original_title": w.original_title,
        "original_language": w.language, "countries": w.countries, "year": w.year, "summary": w.summary,
        "length": length_text(w), "runtime_minutes": w.runtime_minutes, "playtime_hours": w.playtime_hours,
        "page_count": w.page_count, "length_is_estimate": w.length_is_estimate, "popularity_tier": w.popularity_tier,
        "attributes": w.attributes,
        "credits": [{"role": c.role, "name": c.name, "kind": c.kind, "slug": slugify(c.name)} for c in w.credits],
        "tags": tags,
        "parents_guide": parents_guide(w, tax),
        "relationships": relationships,
        "time": time_investment(w),
        "continuity": continuity(w, works),
        "images": [{"kind": i.kind, "url": i.url, "source": i.source, "licence": i.licence, "attribution": i.attribution}
                   for i in w.images],
        "scores": [{"publisher": s.publisher, "metric": s.metric, "value": s.value, "scale_max": s.scale_max,
                    "votes": s.votes, "as_of": s.as_of, "source": s.source} for s in w.scores],
        "box_office": [dict(b) for b in w.box_office],
        "links": [dict(link) for link in w.links],
        "tracks": _track_items(w) if w.medium == "album" else [],
        "spotify": spotify_search(w.creators[0] if w.creators else "", w.title) if w.medium == "album" else None,
        "fact_sources": {k: dict(v) for k, v in w.fact_sources.items()},
        "ids": dict(w.ids),
    }


# ====================================================================== time, continuity, shelves, music
# Everything below is mirrored in demo/engine.cjs (parity-tested).

TIME_BUCKETS = ((45, "quick-bite", "Quick bite"), (150, "one-sitting", "One sitting"),
                (360, "evening-or-two", "An evening or two"), (900, "weekend", "A weekend"),
                (2400, "season", "A season"))
LONG_HAUL = ("long-haul", "A long haul")
READING_MINUTES_PER_PAGE = 1.7      # about 35 pages an hour: an unhurried adult reading pace
NOVELLA_MINUTES = 150
CHAIN_TYPES = ("sequel_of", "spin_off_of", "same_universe", "remake_of")
SHELVES_PATH = Path(__file__).parent / "shelves.json"


def load_shelves(path: Path = SHELVES_PATH) -> dict:
    return json.loads(path.read_text())


def time_investment(w: WorkProfile) -> dict | None:
    """How much time a work asks for, with how the figure was reached."""
    if w.runtime_minutes:
        minutes, basis, estimate = w.runtime_minutes, "runtime", w.length_is_estimate
    elif w.playtime_hours:
        minutes, basis, estimate = w.length_minutes, "playtime", w.length_is_estimate
    elif w.medium == "book" and w.page_count:
        minutes, basis, estimate = round(w.page_count * READING_MINUTES_PER_PAGE), "pages", True
    elif w.medium == "book" and w.attributes.get("form") == "novella":
        minutes, basis, estimate = NOVELLA_MINUTES, "form", True
    else:
        return None
    bucket, label = LONG_HAUL
    for limit, slug, name in TIME_BUCKETS:
        if minutes <= limit:
            bucket, label = slug, name
            break
    return {"minutes": minutes, "bucket": bucket, "label": label, "estimate": estimate, "basis": basis}


def _is_forward(r) -> bool:
    return r.label == RELATIONSHIP_TYPES[r.type][0]


def _position_key(position: str | None) -> float:
    try:
        return float(position) if position is not None else 1e9
    except ValueError:
        return 1e9


def continuity(w: WorkProfile, works: list[WorkProfile]) -> dict:
    """Standalone, part of a series, or part of a franchise; plus adaptation links either way."""
    by_slug = {x.slug: x for x in works}
    adapted_from = [r for r in w.relations if r.type == "adaptation_of" and _is_forward(r)]
    adapted_as = [r for r in w.relations if r.type == "adaptation_of" and not _is_forward(r)]
    out = {"kind": "standalone", "group": None, "position": None, "members": [],
           "adapted_from": [{"slug": r.other_slug, "title": r.other_title, "medium": r.other_medium} for r in adapted_from],
           "adapted_as": [{"slug": r.other_slug, "title": r.other_title, "medium": r.other_medium} for r in adapted_as]}
    # A named group wins when the catalogue holds two or more of its works; otherwise the relationship chain
    # decides, so one entry with a series label and its sequel without one still read as the same franchise.
    series = None
    if w.groups:
        g = w.groups[0]
        members = [x for x in works if any(xg.slug == g.slug for xg in x.groups)]
        pos = {x.slug: next(xg.position for xg in x.groups if xg.slug == g.slug) for x in members}
        members.sort(key=lambda x: (_position_key(pos[x.slug]), x.year or 9999, normalise_title(x.title)))
        series = {"kind": g.kind, "group": {"slug": g.slug, "name": g.name}, "position": g.position,
                  "members": [{"slug": x.slug, "title": x.title, "year": x.year, "medium": x.medium, "position": pos[x.slug]}
                              for x in members]}
        if len(members) > 1:
            out.update(series)
            return out
    seen, queue = {w.slug}, [w.slug]
    while queue:
        cur = by_slug.get(queue.pop())
        for r in (cur.relations if cur else []):
            if r.type in CHAIN_TYPES and r.other_slug not in seen and r.other_slug in by_slug:
                seen.add(r.other_slug)
                queue.append(r.other_slug)
    if len(seen) > 1:
        members = sorted((by_slug[s] for s in seen), key=lambda x: (x.year or 9999, normalise_title(x.title)))
        root = members[0]
        out.update(kind="franchise", group={"slug": f"franchise-{root.slug}", "name": root.title},
                   members=[{"slug": x.slug, "title": x.title, "year": x.year, "medium": x.medium, "position": None}
                            for x in members])
    elif series:
        out.update(series)
    return out


def _context(works: list[WorkProfile]) -> dict[str, dict]:
    return {w.slug: continuity(w, works) for w in works}


def _rich_card(w: WorkProfile, tax: Taxonomy, ctx: dict[str, dict]) -> dict:
    img = w.images[0] if w.images else None
    c = ctx[w.slug]
    return {**card(w, tax),
            "image": {"url": img.url, "kind": img.kind, "licence": img.licence, "attribution": img.attribution,
                      "source": img.source} if img else None,
            "time": time_investment(w),
            "continuity": {"kind": c["kind"], "group": c["group"], "position": c["position"], "count": len(c["members"])},
            "scores": [{"publisher": s.publisher, "metric": s.metric, "value": s.value, "scale_max": s.scale_max}
                       for s in w.scores[:2]]}


def _shelf_match(w: WorkProfile, rule: dict, ctx: dict[str, dict]) -> bool:
    if rule.get("media") and w.medium not in rule["media"]:
        return False
    floor = rule.get("min_strength", 0.5)
    if rule.get("all_tags") and any(w.strength(t) < floor for t in rule["all_tags"]):
        return False
    if rule.get("any_tags") and all(w.strength(t) < floor for t in rule["any_tags"]):
        return False
    tier = w.popularity_tier
    if "popularity_min" in rule and (tier is None or tier < rule["popularity_min"]):
        return False
    if "popularity_max" in rule and (tier is None or tier > rule["popularity_max"]):
        return False
    if rule.get("relation_child") and not any(r.type in rule["relation_child"] and _is_forward(r) for r in w.relations):
        return False
    if rule.get("continuity") and ctx[w.slug]["kind"] not in rule["continuity"]:
        return False
    if "max_minutes" in rule or "min_minutes" in rule:
        t = time_investment(w)
        if t is None:
            return False
        if "max_minutes" in rule and t["minutes"] > rule["max_minutes"]:
            return False
        if "min_minutes" in rule and t["minutes"] < rule["min_minutes"]:
            return False
    return True


def _shelf_key(w: WorkProfile, rule: dict):
    title = normalise_title(w.title)
    sort = rule.get("sort", "popular")
    if sort == "strength":
        tags = list(rule.get("any_tags", [])) + list(rule.get("all_tags", []))
        return (-max([w.strength(t) for t in tags] or [0]), w.popularity_tier or 5, title)
    if sort == "obscure":
        return (-(w.popularity_tier or 0), title)
    if sort in ("shortest", "longest"):
        t = time_investment(w)
        m = t["minutes"] if t else 10**9
        return (m if sort == "shortest" else -m, title)
    return (w.popularity_tier or 5, title)


def shelves(works: list[WorkProfile], tax: Taxonomy, spec: dict | None = None, limit: int = 12) -> list[dict]:
    spec = spec or load_shelves()
    ctx = _context(works)
    out = []
    for s in spec["shelves"]:
        hits = sorted((w for w in works if _shelf_match(w, s["rule"], ctx)), key=lambda w: _shelf_key(w, s["rule"]))
        if len(hits) >= spec.get("min_works", 3):
            out.append({"slug": s["slug"], "name": s["name"], "tagline": s["tagline"], "total": len(hits),
                        "works": [_rich_card(w, tax, ctx) for w in hits[:limit]]})
    return out


def shelf(works: list[WorkProfile], tax: Taxonomy, slug: str, spec: dict | None = None) -> dict | None:
    spec = spec or load_shelves()
    s = next((x for x in spec["shelves"] if x["slug"] == slug), None)
    if s is None:
        return None
    ctx = _context(works)
    hits = sorted((w for w in works if _shelf_match(w, s["rule"], ctx)), key=lambda w: _shelf_key(w, s["rule"]))
    return {"slug": s["slug"], "name": s["name"], "tagline": s["tagline"], "total": len(hits),
            "works": [_rich_card(w, tax, ctx) for w in hits]}


def groups_index(works: list[WorkProfile]) -> list[dict]:
    seen: dict[str, dict] = {}
    for w in works:
        c = continuity(w, works)
        if c["group"] and c["group"]["slug"] not in seen:
            seen[c["group"]["slug"]] = {"slug": c["group"]["slug"], "name": c["group"]["name"], "kind": c["kind"],
                                        "count": len(c["members"])}
    return sorted(seen.values(), key=lambda g: (g["kind"], normalise_title(g["name"])))


def group_page(works: list[WorkProfile], tax: Taxonomy, slug: str) -> dict | None:
    ctx = _context(works)
    owner = next((w for w in works if ctx[w.slug]["group"] and ctx[w.slug]["group"]["slug"] == slug), None)
    if owner is None:
        return None
    c = ctx[owner.slug]
    by_slug = {w.slug: w for w in works}
    members = [by_slug[m["slug"]] for m in c["members"]]
    times = [time_investment(m) for m in members]
    return {"slug": slug, "name": c["group"]["name"], "kind": c["kind"],
            "works": [{**_rich_card(m, tax, ctx), "position": cm["position"]} for m, cm in zip(members, c["members"], strict=True)],
            "total_minutes": sum(t["minutes"] for t in times if t), "unknown_length": sum(1 for t in times if not t)}


def spotify_search(*parts: str) -> str:
    return "https://open.spotify.com/search/" + quote(" ".join(p for p in parts if p), safe="")


def _track_items(album: WorkProfile) -> list[dict]:
    artist = album.creators[0] if album.creators else ""
    return [{"title": t["title"], "seconds": t.get("seconds"), "album": album.slug, "album_title": album.title,
             "artist": artist, "spotify": spotify_search(artist, t["title"]),
             "remixes": [{**r, "spotify": spotify_search(r.get("artist") or "", r.get("title") or "")}
                         for r in t.get("remixes", [])]}
            for t in album.tracks]


def mood_rings(works: list[WorkProfile], tax: Taxonomy, spec: dict | None = None) -> list[dict]:
    """Music by mood. Tracks inherit their album's mood until they're classified individually."""
    spec = spec or load_shelves()
    ctx = _context(works)
    out = []
    for ring in spec["mood_rings"]:
        albums = [w for w in works if w.medium == "album" and all(w.strength(t) >= 0.6 for t in ring["tags"])]
        albums.sort(key=lambda w: (-sum(w.strength(t) for t in ring["tags"]), normalise_title(w.title)))
        if albums:
            out.append({"slug": ring["slug"], "name": ring["name"], "tagline": ring["tagline"],
                        "albums": [{**_rich_card(a, tax, ctx), "spotify": spotify_search(a.creators[0] if a.creators else "", a.title)}
                                   for a in albums],
                        "tracks": [t for a in albums for t in _track_items(a)],
                        "mood_basis": "album"})
    return out


def remix_rack(works: list[WorkProfile]) -> list[dict]:
    return [t for w in works if w.medium == "album" for t in _track_items(w) if t["remixes"]]
