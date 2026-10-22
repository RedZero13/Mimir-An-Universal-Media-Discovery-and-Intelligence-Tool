"""Catalogue data shapes and helpers with no database dependency.

Everything the discovery pipeline needs is defined here, so the same ranking code runs against PostgreSQL
(repository.py) or an in-memory catalogue (memory.py).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Mirrors the rows inserted into relationship_type by migration 0001 (checked by a test).
RELATIONSHIP_TYPES: dict[str, tuple[str, str, bool]] = {  # slug: (label, inverse, factual)
    "adaptation_of": ("is an adaptation of", "was adapted as", True),
    "sequel_of": ("is a sequel to", "is followed by", True),
    "remake_of": ("is a remake of", "was remade as", True),
    "same_universe": ("shares a fictional universe with", "shares a fictional universe with", True),
    "same_creator": ("shares a creator with", "shares a creator with", True),
    "influenced_by": ("was influenced by", "influenced", False),
    "thematic_kin": ("explores similar questions to", "explores similar questions to", False),
    "similar_experience": ("offers a similar experience to", "offers a similar experience to", False),
    "contrasting_take": ("offers a contrasting take on the themes of", "offers a contrasting take on the themes of", False),
    "track_of": ("is a track on", "includes the track", True),
    "remix_of": ("is a remix of", "was remixed as", True),
    "spin_off_of": ("is a spin-off of", "spun off", True),
    "soundtrack_of": ("is the soundtrack of", "has the soundtrack", True),
}

# How much each dimension counts when comparing works ("something like X", taste profiles): mostly what a work is
# about and how it feels; genre and accessibility matter less.
SIMILARITY_WEIGHTS = {"theme": 1.0, "mood": 0.9, "narrative": 0.8, "world": 0.8, "style": 0.7, "pacing": 0.6,
                      "genre": 0.5, "complexity": 0.4}

PRIMARY_ROLES = ("director", "creator", "author", "developer", "artist")
ORGANISATION_ROLES = {"developer", "publisher", "studio", "label", "distributor"}


def parse_advisory(value: float | list) -> tuple[float, str | None, str | None]:
    """Seed advisory value: an intensity, or [intensity, note] or [intensity, note, spoiler note]."""
    if isinstance(value, list):
        return float(value[0]), (value[1] if len(value) > 1 else None), (value[2] if len(value) > 2 else None)
    return float(value), None, None


def severity(level: float) -> str:
    """Parents' guide wording for an advisory intensity."""
    if level <= 0:
        return "None"
    if level < 0.45:
        return "Mild"
    if level < 0.75:
        return "Moderate"
    return "Severe"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalise_title(title: str) -> str:
    return re.sub(r"^(the|a|an)-", "", slugify(title))


@dataclass(frozen=True)
class TermEvidence:
    strength: float
    confidence: float
    origin: str
    review_status: str
    is_interpretation: bool
    note: str | None = None             # non-spoiler evidence (parents' guide notes)
    spoiler_note: str | None = None     # hidden unless the reader asks


@dataclass(frozen=True)
class Credit:
    role: str
    name: str
    kind: str            # "person" | "organisation"


@dataclass(frozen=True)
class Rating:
    system: str          # MPA, BBFC, ESRB, PEGI …
    rating: str
    reason: str | None


@dataclass(frozen=True)
class Image:
    kind: str            # poster | cover | still | logo
    url: str
    source: str
    licence: str
    attribution: str | None = None


@dataclass(frozen=True)
class Score:
    publisher: str       # who published the score (Rotten Tomatoes, Metacritic, Open Library readers …)
    metric: str
    value: float
    scale_max: float
    votes: int | None
    as_of: str | None
    source: str          # where we got it (wikidata, openlibrary …)


@dataclass(frozen=True)
class GroupRef:
    slug: str
    name: str
    kind: str            # series | franchise | collection | universe
    position: str | None
    source: str


@dataclass(frozen=True)
class Relation:
    other_slug: str
    other_title: str
    other_medium: str
    type: str
    label: str           # phrased from this work's point of view: "<this> <label> <other>"
    note: str | None
    confidence: float
    origin: str
    factual: bool


@dataclass
class WorkProfile:
    id: str
    slug: str
    medium: str
    title: str
    original_title: str | None
    year: int | None
    language: str | None
    countries: list[str]
    summary: str | None
    runtime_minutes: int | None
    playtime_hours: float | None
    length_is_estimate: bool
    popularity_tier: int | None
    advisories_assessed: bool
    creators: list[str] = field(default_factory=list)            # primary credits, for display and diversity
    terms: dict[str, TermEvidence] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    credits: list[Credit] = field(default_factory=list)          # all credits, in billing order
    ratings: list[Rating] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)
    # Open-source enrichment (catalogue/enrich.py); empty until a source has been fetched.
    page_count: int | None = None
    images: list[Image] = field(default_factory=list)
    scores: list[Score] = field(default_factory=list)
    box_office: list[dict] = field(default_factory=list)
    groups: list[GroupRef] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    ids: dict = field(default_factory=dict)
    tracks: list[dict] = field(default_factory=list)
    fact_sources: dict = field(default_factory=dict)             # field -> {"source", "seed"} when a source replaced the seed

    def strength(self, key: str) -> float:
        ev = self.terms.get(key)
        return ev.strength if ev else 0.0

    @property
    def length_minutes(self) -> int | None:
        """A comparable length across media, where one is meaningful."""
        if self.runtime_minutes is not None:
            return self.runtime_minutes
        if self.playtime_hours is not None:
            return round(self.playtime_hours * 60)
        return series_minutes(self)


def series_minutes(w: WorkProfile) -> int | None:
    """Total watching time for a TV series: episodes x typical episode length."""
    if w.medium != "series":
        return None
    eps, mins = w.attributes.get("episodes"), w.attributes.get("episode_minutes")
    if isinstance(eps, int) and isinstance(mins, int | float) and not isinstance(mins, bool):
        return round(eps * mins)
    return None


def series_length_text(w: WorkProfile) -> str | None:
    if w.medium != "series" or not isinstance(w.attributes.get("episodes"), int):
        return None
    seasons, eps = w.attributes.get("seasons"), w.attributes["episodes"]
    if isinstance(seasons, int):
        return f"{seasons} season{'' if seasons == 1 else 's'}, {eps} ep"
    return f"{eps} ep"

