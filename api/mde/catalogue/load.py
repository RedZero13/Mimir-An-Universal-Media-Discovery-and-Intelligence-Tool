"""Idempotent catalogue import.

The whole file is validated before anything is written; a run either applies completely or not at all.
Re-running with the same input changes nothing. Each source owns its own rows: credits and
classifications from a source are replaced as a set, so removing a term from the seed removes it here.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from mde import taxonomy as taxonomy_mod
from mde.taxonomy import Taxonomy

SEED_PATH = Path(__file__).parent.parent / "seed" / "catalogue.json"

# Internal sources used by the seed. External providers are added to the register only once their
# terms have been reviewed (see docs/SOURCES.md).
SEED_SOURCES = {
    "editorial-seed": {
        "name": "Editorial seed (unverified)",
        "kind": "editorial",
        "commercial_use": "yes", "may_store": "yes", "may_display": "yes", "ai_use": "yes",
        "notes": "Factual fields compiled for the pilot from general knowledge. Must be verified against "
                 "primary sources before launch.",
    },
    "ai-assisted-seed": {
        "name": "AI-assisted classification (unreviewed)",
        "kind": "ai_assisted",
        "commercial_use": "yes", "may_store": "yes", "may_display": "yes", "ai_use": "yes",
        "notes": "Experiential and thematic classifications drafted with AI assistance. Interpretations, "
                 "pending editorial review.",
    },
}

ORGANISATION_ROLES = {"developer", "publisher", "studio", "label", "distributor"}
VALID_MEDIA = {"film", "series", "episode", "book", "comic", "game", "album", "track", "podcast", "online_video", "channel"}


class ValidationFailed(Exception):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} validation error(s):\n  " + "\n  ".join(errors))
        self.errors = errors


@dataclass
class ImportStats:
    works_inserted: int = 0
    works_updated: int = 0
    works_unchanged: int = 0
    classifications: int = 0
    credits: int = 0
    relationships: int = 0
    warnings: list[str] = field(default_factory=list)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalise_title(title: str) -> str:
    t = slugify(title)
    return re.sub(r"^(the|a|an)-", "", t)


def validate(data: dict, tax: Taxonomy) -> list[str]:
    errors: list[str] = []
    slugs: set[str] = set()
    for i, w in enumerate(data.get("works", [])):
        where = f"works[{i}] ({w.get('slug', '?')})"
        for key in ("slug", "medium", "title"):
            if not w.get(key):
                errors.append(f"{where}: missing {key}")
        if w.get("slug") in slugs:
            errors.append(f"{where}: duplicate slug")
        slugs.add(w.get("slug"))
        if w.get("medium") not in VALID_MEDIA:
            errors.append(f"{where}: unknown medium {w.get('medium')!r}")
        for key, value in w.get("terms", {}).items():
            if key not in tax.terms:
                errors.append(f"{where}: unknown term {key!r}")
            elif key.startswith("advisory:"):
                errors.append(f"{where}: advisories belong under 'advisories', not 'terms' ({key})")
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                errors.append(f"{where}: strength for {key} must be in [0, 1]")
        for slug, value in (w.get("advisories") or {}).items():
            if f"advisory:{slug}" not in tax.terms:
                errors.append(f"{where}: unknown advisory {slug!r}")
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                errors.append(f"{where}: intensity for advisory {slug} must be in [0, 1]")
        for c in w.get("credits", []):
            if len(c) not in (2, 3) or (len(c) == 3 and c[2] not in ("person", "organisation")):
                errors.append(f"{where}: malformed credit {c!r}")
        tier = w.get("popularity_tier")
        if tier is not None and tier not in (1, 2, 3, 4):
            errors.append(f"{where}: popularity_tier must be 1-4")
    for i, r in enumerate(data.get("relationships", [])):
        if len(r) != 5:
            errors.append(f"relationships[{i}]: expected [from, type, to, note, confidence]")
            continue
        if r[0] not in slugs or r[2] not in slugs:
            errors.append(f"relationships[{i}]: unknown work in {r[0]!r} -> {r[2]!r}")
    return errors


def possible_duplicates(works: list[dict]) -> list[str]:
    """Same medium + normalised title + year under different slugs is almost certainly one work twice."""
    seen: dict[tuple, str] = {}
    found = []
    for w in works:
        key = (w["medium"], normalise_title(w["title"]), w.get("year"))
        if key in seen:
            found.append(f"{w['slug']} looks like a duplicate of {seen[key]}")
        else:
            seen[key] = w["slug"]
    return found


def _ensure_sources(conn: psycopg.Connection) -> dict[str, int]:
    ids = {}
    for slug, s in SEED_SOURCES.items():
        row = conn.execute(
            "INSERT INTO source (slug, name, kind, commercial_use, may_store, may_display, ai_use, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, notes = EXCLUDED.notes RETURNING id",
            (slug, s["name"], s["kind"], s["commercial_use"], s["may_store"], s["may_display"], s["ai_use"], s["notes"]),
        ).fetchone()
        ids[slug] = row["id"]
    return ids


def _upsert_party(conn: psycopg.Connection, name: str, kind: str) -> tuple[str | None, str | None]:
    table = "person" if kind == "person" else "organisation"
    row = conn.execute(
        f"INSERT INTO {table} (slug, name) VALUES (%s, %s) "
        f"ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id",
        (slugify(name), name),
    ).fetchone()
    return (row["id"], None) if kind == "person" else (None, row["id"])


WORK_FIELDS = ("medium", "title", "original_title", "original_language", "countries", "release_year",
               "summary", "runtime_minutes", "playtime_hours", "length_is_estimate", "popularity_tier",
               "attributes", "advisories_assessed")


def _work_values(w: dict) -> dict:
    return {
        "medium": w["medium"],
        "title": w["title"],
        "original_title": w.get("original_title"),
        "original_language": w.get("language"),
        "countries": w.get("countries", []),
        "release_year": w.get("year"),
        "summary": w.get("summary"),
        "runtime_minutes": w.get("runtime_minutes"),
        "playtime_hours": w.get("playtime_hours"),
        "length_is_estimate": bool(w.get("length_is_estimate", False)),
        "popularity_tier": w.get("popularity_tier"),
        "attributes": w.get("attributes", {}),
        "advisories_assessed": "advisories" in w,
    }


def _upsert_work(conn: psycopg.Connection, w: dict, stats: ImportStats) -> str:
    values = _work_values(w)
    existing = conn.execute(
        f"SELECT id, {', '.join(WORK_FIELDS)} FROM work WHERE slug = %s", (w["slug"],)
    ).fetchone()
    params = {k: (Jsonb(v) if k == "attributes" else v) for k, v in values.items()}
    if existing is None:
        cols = ", ".join(WORK_FIELDS)
        placeholders = ", ".join(f"%({k})s" for k in WORK_FIELDS)
        row = conn.execute(
            f"INSERT INTO work (slug, {cols}) VALUES (%(slug)s, {placeholders}) RETURNING id",
            {"slug": w["slug"], **params},
        ).fetchone()
        stats.works_inserted += 1
        return row["id"]
    current = {k: existing[k] for k in WORK_FIELDS}
    if current["playtime_hours"] is not None:
        current["playtime_hours"] = float(current["playtime_hours"])
    if current == values:
        stats.works_unchanged += 1
    else:
        sets = ", ".join(f"{k} = %({k})s" for k in WORK_FIELDS)
        conn.execute(f"UPDATE work SET {sets}, updated_at = now() WHERE id = %(id)s", {"id": existing["id"], **params})
        stats.works_updated += 1
    return existing["id"]


def import_catalogue(conn: psycopg.Connection, data: dict, tax: Taxonomy | None = None) -> ImportStats:
    tax = tax or taxonomy_mod.load()
    errors = validate(data, tax)
    if errors:
        raise ValidationFailed(errors)
    stats = ImportStats(warnings=possible_duplicates(data["works"]))
    defaults = {"genre_confidence": 0.9, "term_confidence": 0.7, "advisory_confidence": 0.75, **data.get("defaults", {})}

    with conn.transaction():
        taxonomy_mod.sync(conn, tax)
        sources = _ensure_sources(conn)
        run_id = conn.execute(
            "INSERT INTO import_run (source_id) VALUES (%s) RETURNING id", (sources["editorial-seed"],)
        ).fetchone()["id"]
        term_ids = {f"{r['dimension']}:{r['slug']}": r["id"]
                    for r in conn.execute("SELECT id, dimension, slug FROM taxonomy_term").fetchall()}
        work_ids: dict[str, str] = {}

        for w in data["works"]:
            work_id = _upsert_work(conn, w, stats)
            work_ids[w["slug"]] = work_id

            if w.get("original_title"):
                conn.execute(
                    "INSERT INTO work_title (work_id, title, language, kind) VALUES (%s, %s, %s, 'original') "
                    "ON CONFLICT DO NOTHING",
                    (work_id, w["original_title"], w.get("language")),
                )

            for fname, key in (("release_year", "year"), ("runtime_minutes", "runtime_minutes"),
                               ("playtime_hours", "playtime_hours")):
                if w.get(key) is not None:
                    conn.execute(
                        "INSERT INTO field_provenance (work_id, field, value, source_id) VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (work_id, field, source_id) DO UPDATE SET value = EXCLUDED.value",
                        (work_id, fname, Jsonb(w[key]), sources["editorial-seed"]),
                    )

            conn.execute("DELETE FROM credit WHERE work_id = %s AND source_id = %s", (work_id, sources["editorial-seed"]))
            for ordinal, c in enumerate(w.get("credits", [])):
                role, name = c[0], c[1]
                kind = c[2] if len(c) == 3 else ("organisation" if role in ORGANISATION_ROLES else "person")
                person_id, org_id = _upsert_party(conn, name, kind)
                conn.execute(
                    "INSERT INTO credit (work_id, person_id, organisation_id, role, ordinal, source_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (work_id, person_id, org_id, role, ordinal, sources["editorial-seed"]),
                )
                stats.credits += 1

            conn.execute(
                "DELETE FROM classification WHERE work_id = %s AND source_id = %s",
                (work_id, sources["ai-assisted-seed"]),
            )
            rows = []
            for key, strength in w.get("terms", {}).items():
                conf = defaults["genre_confidence"] if key.startswith("genre:") else defaults["term_confidence"]
                rows.append((key, strength, conf))
            if "advisories" in w:
                # Assessed works get an explicit 0 for every advisory not listed: "assessed absent" is
                # different from "never assessed".
                for term in tax.in_dimension("advisory"):
                    rows.append((term.key, w["advisories"].get(term.slug, 0.0), defaults["advisory_confidence"]))
            for key, strength, conf in rows:
                conn.execute(
                    "INSERT INTO classification (work_id, term_id, strength, confidence, origin, is_interpretation, "
                    "source_id, taxonomy_version) VALUES (%s, %s, %s, %s, 'ai_assisted', %s, %s, %s)",
                    # Everything from this source is an interpretation, genres included: none of it has
                    # been checked against an authoritative source yet.
                    (work_id, term_ids[key], strength, conf, True, sources["ai-assisted-seed"], tax.version),
                )
                stats.classifications += 1

        for from_slug, rel_type, to_slug, note, confidence in data.get("relationships", []):
            factual = conn.execute("SELECT factual FROM relationship_type WHERE slug = %s", (rel_type,)).fetchone()
            if factual is None:
                raise ValidationFailed([f"unknown relationship type {rel_type!r}"])
            conn.execute(
                "INSERT INTO relationship (from_work_id, to_work_id, type, note, confidence, origin, source_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (from_work_id, to_work_id, type) DO UPDATE SET note = EXCLUDED.note, "
                "confidence = EXCLUDED.confidence",
                (work_ids[from_slug], work_ids[to_slug], rel_type, note, confidence,
                 "editorial" if factual["factual"] else "ai_assisted",
                 sources["editorial-seed" if factual["factual"] else "ai-assisted-seed"]),
            )
            stats.relationships += 1

        conn.execute(
            "UPDATE import_run SET finished_at = now(), stats = %s WHERE id = %s",
            (Jsonb({k: v for k, v in stats.__dict__.items() if k != "warnings"}), run_id),
        )
    return stats


def load_seed(conn: psycopg.Connection, path: Path = SEED_PATH) -> ImportStats:
    return import_catalogue(conn, json.loads(path.read_text()))
