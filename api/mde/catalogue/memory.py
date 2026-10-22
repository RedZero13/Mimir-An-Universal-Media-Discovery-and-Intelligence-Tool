"""An in-memory catalogue built straight from the seed file, with no database.

Used by the browser demo (Pyodide) and by the offline benchmark test. It mirrors what load.py writes and
repository.py reads. Keyword search is a simple stand-in for PostgreSQL full-text search: whole-word matches
on title and summary after light suffix stripping, title words counting double.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mde.catalogue import browse
from mde.catalogue.enrich import apply as apply_enrichment
from mde.catalogue.enrich import load_enrichment
from mde.catalogue.model import (
    ORGANISATION_ROLES,
    PRIMARY_ROLES,
    RELATIONSHIP_TYPES,
    Credit,
    Rating,
    Relation,
    TermEvidence,
    WorkProfile,
    normalise_title,
    parse_advisory,
)
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
        for slug, value in (w.get("advisories") or {}).items():
            level, note, spoiler = parse_advisory(value)
            terms[f"advisory:{slug}"] = TermEvidence(level, d["advisory_confidence"], "ai_assisted", "unreviewed", True,
                                                     note, spoiler)
        works[w["slug"]] = WorkProfile(
            id=w["slug"], slug=w["slug"], medium=w["medium"], title=w["title"], original_title=w.get("original_title"),
            year=w.get("year"), language=w.get("language"), countries=w.get("countries", []), summary=w.get("summary"),
            runtime_minutes=w.get("runtime_minutes"), playtime_hours=w.get("playtime_hours"),
            length_is_estimate=bool(w.get("length_is_estimate")), popularity_tier=w.get("popularity_tier"),
            advisories_assessed=bool(w.get("advisories")),
            creators=[c[1] for c in w.get("credits", []) if c[0] in PRIMARY_ROLES],
            terms=terms,
            credits=[Credit(c[0], c[1], c[2] if len(c) == 3 else ("organisation" if c[0] in ORGANISATION_ROLES else "person"))
                     for c in w.get("credits", [])],
            ratings=[Rating(*r) for r in w.get("ratings", [])],
            attributes=w.get("attributes", {}),
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
    def __init__(self, data: dict, tax: Taxonomy | None = None, enrichment: dict | None = None):
        self.data = data
        self.tax = tax or load_taxonomy()
        self.enrichment = load_enrichment() if enrichment is None else enrichment
        self.works = apply_enrichment(profiles_from_catalogue(data, self.tax), self.enrichment)
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

    def get(self, slug: str) -> WorkProfile | None:
        return next((w for w in self.works if w.slug == slug), None)

    def work(self, slug: str) -> dict | None:
        w = self.get(slug)
        return browse.work_page(w, self.works, self.tax) if w else None

    def browse(self, filters: browse.BrowseFilters) -> dict:
        return browse.browse(self.works, self.tax, filters)

    def tag(self, key: str) -> dict | None:
        return browse.tag_page(self.works, self.tax, key)

    def tags(self) -> list[dict]:
        return browse.tag_index(self.works, self.tax)

    def person(self, slug: str) -> dict | None:
        return browse.person_page(self.works, self.tax, slug)

    def people(self) -> list[dict]:
        return browse.people_index(self.works)

    def shelves(self) -> list[dict]:
        return browse.shelves(self.works, self.tax)

    def shelf(self, slug: str) -> dict | None:
        return browse.shelf(self.works, self.tax, slug)

    def groups(self) -> list[dict]:
        return browse.groups_index(self.works)

    def group(self, slug: str) -> dict | None:
        return browse.group_page(self.works, self.tax, slug)

    def mood_rings(self) -> list[dict]:
        return browse.mood_rings(self.works, self.tax)

    def remix_rack(self) -> list[dict]:
        return browse.remix_rack(self.works)
