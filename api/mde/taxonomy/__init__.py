"""The controlled taxonomy: loading, lookup and syncing to the database."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import psycopg

TAXONOMY_PATH = Path(__file__).parent / "taxonomy.json"


@dataclass(frozen=True)
class Term:
    dimension: str
    slug: str
    label: str
    definition: str
    applies_to: tuple[str, ...]
    synonyms: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.dimension}:{self.slug}"


@dataclass(frozen=True)
class Dimension:
    slug: str
    label: str
    description: str
    kind: str


@dataclass
class Taxonomy:
    version: str
    dimensions: dict[str, Dimension]
    terms: dict[str, Term] = field(default_factory=dict)  # keyed by "dimension:slug"

    def get(self, key: str) -> Term:
        try:
            return self.terms[key]
        except KeyError:
            raise KeyError(f"unknown taxonomy term {key!r}") from None

    def in_dimension(self, dimension: str) -> list[Term]:
        return [t for t in self.terms.values() if t.dimension == dimension]


def parse(data: dict) -> Taxonomy:
    dims = {d["slug"]: Dimension(d["slug"], d["label"], d["description"], d["kind"]) for d in data["dimensions"]}
    tax = Taxonomy(version=data["version"], dimensions=dims)
    seen_synonyms: dict[str, str] = {}
    for raw in data["terms"]:
        if raw["dimension"] not in dims:
            raise ValueError(f"term {raw['slug']!r} uses unknown dimension {raw['dimension']!r}")
        term = Term(
            dimension=raw["dimension"],
            slug=raw["slug"],
            label=raw["label"],
            definition=raw["definition"],
            applies_to=tuple(raw.get("applies_to", ["*"])),
            synonyms=tuple(s.lower() for s in raw.get("synonyms", [])),
        )
        if term.key in tax.terms:
            raise ValueError(f"duplicate term {term.key}")
        for s in term.synonyms:
            # One phrase must mean one thing, or the intent parser becomes order-dependent.
            if s in seen_synonyms and seen_synonyms[s] != term.key:
                raise ValueError(f"synonym {s!r} used by both {seen_synonyms[s]} and {term.key}")
            seen_synonyms[s] = term.key
        tax.terms[term.key] = term
    return tax


@lru_cache(maxsize=1)
def load() -> Taxonomy:
    return parse(json.loads(TAXONOMY_PATH.read_text()))


def sync(conn: psycopg.Connection, tax: Taxonomy) -> dict[str, int]:
    """Upserts dimensions and terms. Terms are never deleted, only marked deprecated."""
    for d in tax.dimensions.values():
        conn.execute(
            "INSERT INTO taxonomy_dimension (slug, label, description, kind) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (slug) DO UPDATE SET label = EXCLUDED.label, description = EXCLUDED.description, "
            "kind = EXCLUDED.kind",
            (d.slug, d.label, d.description, d.kind),
        )
    for t in tax.terms.values():
        conn.execute(
            "INSERT INTO taxonomy_term (dimension, slug, label, definition, applies_to, synonyms, version_introduced) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (dimension, slug) DO UPDATE SET label = EXCLUDED.label, definition = EXCLUDED.definition, "
            "applies_to = EXCLUDED.applies_to, synonyms = EXCLUDED.synonyms, deprecated = false",
            (t.dimension, t.slug, t.label, t.definition, list(t.applies_to), list(t.synonyms), tax.version),
        )
    live = [(t.dimension, t.slug) for t in tax.terms.values()]
    cur = conn.execute(
        "UPDATE taxonomy_term SET deprecated = true WHERE (dimension, slug) NOT IN "
        "(SELECT * FROM unnest(%s::text[], %s::text[]))",
        ([d for d, _ in live], [s for _, s in live]),
    )
    return {"terms": len(tax.terms), "deprecated": cur.rowcount}
