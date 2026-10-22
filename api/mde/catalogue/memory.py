"""An in-memory catalogue built straight from the seed file, with no database.

Used by the browser demo (Pyodide) and by the offline benchmark test. It mirrors what load.py writes and
repository.py reads. Keyword search is a simple stand-in for PostgreSQL full-text search: whole-word matches
on title and summary after light suffix stripping, title words counting double.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mde.catalogue.model import RELATIONSHIP_TYPES, Relation, TermEvidence, WorkProfile, normalise_title
from mde.discovery.pipeline import DiscoveryResponse, run_pipeline
from mde.taxonomy import Taxonomy
from mde.taxonomy import load as load_taxonomy

SEED_PATH = Path(__file__).parent.parent / "seed" / "catalogue.json"


def profiles_from_catalogue(data: dict, tax: Taxonomy) -> list[WorkProfile]:
    d = {"genre_confidence": 0.9, "term_confidence": 0.7, "advisory_confidence": 0.75, **data.get("defaults", {})}
    works: dict[str, WorkProfile] = {}
    for w in data["works"]:
        terms = {}
        for key, strength in w.get("terms", {}).items():
            conf = d["genre_confidence"] if key.startswith("genre:") else d["term_confidence"]
            terms[key] = TermEvidence(strength, conf, "ai_assisted", "unreviewed", True)
        if "advisories" in w:
            for term in tax.in_dimension("advisory"):
                terms[term.key] = TermEvidence(w["advisories"].get(term.slug, 0.0), d["advisory_confidence"],
                                               "ai_assisted", "unreviewed", True)
        works[w["slug"]] = WorkProfile(
            id=w["slug"], slug=w["slug"], medium=w["medium"], title=w["title"], original_title=w.get("original_title"),
            year=w.get("year"), language=w.get("language"), countries=w.get("countries", []), summary=w.get("summary"),
            runtime_minutes=w.get("runtime_minutes"), playtime_hours=w.get("playtime_hours"),
            length_is_estimate=bool(w.get("length_is_estimate")), popularity_tier=w.get("popularity_tier"),
            advisories_assessed="advisories" in w,
            creators=[c[1] for c in w.get("credits", []) if c[0] in ("director", "author", "developer", "artist")],
            terms=terms,
        )
    for a_slug, rel_type, b_slug, note, confidence in data.get("relationships", []):
        label, inverse, factual = RELATIONSHIP_TYPES[rel_type]
        origin = "editorial" if factual else "ai_assisted"
        a, b = works[a_slug], works[b_slug]
        a.relations.append(Relation(b.slug, b.title, b.medium, rel_type, label, note, confidence, origin, factual))
        b.relations.append(Relation(a.slug, a.title, a.medium, rel_type, inverse, note, confidence, origin, factual))
    return list(works.values())


def _stem(word: str) -> str:
    for suffix in ("ing", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def _words(text: str | None) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", (text or "").lower())}


class MemoryCatalogue:
    def __init__(self, data: dict, tax: Taxonomy | None = None):
        self.data = data
        self.tax = tax or load_taxonomy()
        self.works = profiles_from_catalogue(data, self.tax)
        self._titles = {w.slug: {normalise_title(t) for t in (w.title, w.original_title) if t} for w in self.works}
        self._index = {w.slug: (_words(f"{w.title} {w.original_title or ''}"), _words(w.summary)) for w in self.works}

    @classmethod
    def from_seed(cls, path: Path = SEED_PATH) -> MemoryCatalogue:
        return cls(json.loads(path.read_text()))

    def keyword_scores(self, keywords: list[str]) -> dict[str, float]:
        stems = {_stem(k.lower()) for k in keywords}
        raw = {slug: 2 * len(stems & title) + len(stems & summary) for slug, (title, summary) in self._index.items()}
        top = max(raw.values(), default=0)
        return {slug: n / top for slug, n in raw.items() if n} if top else {}

    def resolve_title(self, phrase: str) -> str | None:
        target = normalise_title(phrase)
        hits = [w for w in self.works if target and target in self._titles[w.slug]]
        return min(hits, key=lambda w: w.popularity_tier or 5).slug if hits else None

    def discover(self, query: str, limit: int = 8) -> DiscoveryResponse:
        return run_pipeline(query, self.works, self.keyword_scores, self.resolve_title, limit=limit)

    def work(self, slug: str) -> dict | None:
        """Work-page data in the same shape as GET /api/works/{slug}, minus database-only fields."""
        raw = next((w for w in self.data["works"] if w["slug"] == slug), None)
        if raw is None:
            return None
        profile = next(w for w in self.works if w.slug == slug)
        by_slug = {w.slug: w for w in self.works}
        classifications = []
        for key, ev in profile.terms.items():
            term = self.tax.get(key)
            classifications.append({
                "dimension": term.dimension, "slug": term.slug, "label": term.label, "definition": term.definition,
                "strength": ev.strength, "confidence": ev.confidence, "origin": ev.origin,
                "review_status": ev.review_status, "is_interpretation": ev.is_interpretation, "is_spoiler": False,
            })
        classifications.sort(key=lambda c: (c["dimension"], -c["strength"]))
        return {
            "slug": slug, "medium": raw["medium"], "title": raw["title"], "original_title": raw.get("original_title"),
            "original_language": raw.get("language"), "countries": raw.get("countries", []),
            "release_year": raw.get("year"), "summary": raw.get("summary"), "summary_spoiler": None,
            "runtime_minutes": raw.get("runtime_minutes"), "playtime_hours": raw.get("playtime_hours"),
            "length_is_estimate": bool(raw.get("length_is_estimate")), "attributes": raw.get("attributes", {}),
            "advisories_assessed": "advisories" in raw,
            "credits": [{"role": c[0], "name": c[1]} for c in raw.get("credits", [])],
            "classifications": classifications,
            "relationships": sorted(
                ({"label": r.label, "type": r.type, "factual": r.factual, "slug": r.other_slug, "title": r.other_title,
                  "medium": r.other_medium, "release_year": by_slug[r.other_slug].year, "note": r.note,
                  "confidence": r.confidence, "is_spoiler": False} for r in profile.relations),
                key=lambda r: (not r["factual"], -r["confidence"])),
        }
