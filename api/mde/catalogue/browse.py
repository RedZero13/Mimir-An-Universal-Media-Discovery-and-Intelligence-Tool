"""Catalogue views: browse with filters and facets, tag pages, people pages and full work pages.

Pure functions over WorkProfile lists, so the API (PostgreSQL-backed) and the browser demo (seed file)
render identical pages. demo/engine.cjs mirrors this module; tests/test_demo_parity.py checks they agree.

At pilot scale every view is computed in memory over the whole catalogue. Before the catalogue reaches tens
of thousands of works, browse filtering and facet counts move into SQL with the same output shape.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from mde.catalogue.model import WorkProfile, normalise_title, severity, slugify
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
    return {
        "total": len(hits),
        "results": [card(w, tax) for w in hits],
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
        "works": [{**card(w, tax), "strength": w.strength(key)} for w in tagged],
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
    roles = sorted({r for _, rs in credited for r in rs})
    themes: Counter = Counter()
    for w, _ in credited:
        for k, _s in _tags(w, ["theme", "mood"]):
            themes[k] += 1
    return {
        "slug": slug, "name": name, "kind": kind, "roles": roles,
        "works": [{**card(w, tax), "roles": rs} for w, rs in credited],
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
        "length_is_estimate": w.length_is_estimate, "popularity_tier": w.popularity_tier, "attributes": w.attributes,
        "credits": [{"role": c.role, "name": c.name, "kind": c.kind, "slug": slugify(c.name)} for c in w.credits],
        "tags": tags,
        "parents_guide": parents_guide(w, tax),
        "relationships": relationships,
    }
