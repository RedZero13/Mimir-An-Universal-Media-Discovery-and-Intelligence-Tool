"""Idempotent catalogue import.

The whole file is validated before anything is written; a run either applies completely or not at all.
Re-running with the same input changes nothing. Each source owns its own rows: credits and
classifications from a source are replaced as a set, so removing a term from the seed removes it here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from mde import taxonomy as taxonomy_mod
from mde.catalogue import enrich
from mde.catalogue.model import ORGANISATION_ROLES, RELATIONSHIP_TYPES, WorkProfile, normalise_title, parse_advisory, slugify
from mde.catalogue.seedfiles import read_seed
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

# Open sources, registered when their enrichment is imported. Terms summarised in docs/SOURCES.md.
OPEN_SOURCES = {
    "wikidata": {"name": "Wikidata", "kind": "open_dataset", "licence": "CC0 1.0", "commercial_use": "yes",
                 "may_store": "yes", "may_display": "yes", "ai_use": "yes",
                 "attribution": "Data from Wikidata", "notes": "Identity, dates, series, box office, published review scores, IDs"},
    "openlibrary": {"name": "Open Library", "kind": "open_dataset", "licence": "Open data; cover images remain the publishers'",
                    "commercial_use": "yes", "may_store": "yes", "may_display": "restricted", "ai_use": "unknown",
                    "attribution": "Open Library", "notes": "Book covers (identification), page counts, reader ratings"},
    "musicbrainz": {"name": "MusicBrainz & Cover Art Archive", "kind": "open_dataset",
                    "licence": "Core data CC0; cover art rights remain with owners", "commercial_use": "yes",
                    "may_store": "yes", "may_display": "restricted", "ai_use": "yes",
                    "attribution": "MusicBrainz / Cover Art Archive", "notes": "Tracklists, lengths, remixes, album covers"},
    "tmdb": {"name": "TMDB", "kind": "official_api", "licence": "TMDB API terms", "commercial_use": "restricted",
             "may_store": "restricted", "may_display": "yes", "ai_use": "unknown",
             "attribution": "This product uses the TMDB API but is not endorsed or certified by TMDB.",
             "notes": "Film posters; commercial use needs a TMDB agreement"},
    "publisher": {"name": "Publisher-supplied", "kind": "licensed_dataset", "licence": "Supplied by the rights holder",
                  "commercial_use": "yes", "may_store": "yes", "may_display": "yes", "ai_use": "yes",
                  "attribution": "Courtesy of the publisher", "notes": "Covers, page counts and store links for Terratales titles"},
    "youtube": {"name": "YouTube channel pages and RSS feeds", "kind": "official_api",
                "licence": "Public channel pages and feeds; avatars and thumbnails remain the creators'", "commercial_use": "restricted",
                "may_store": "restricted", "may_display": "yes", "ai_use": "unknown", "attribution": "Via YouTube",
                "notes": "Channel and video titles, dates, IDs, thumbnails and links for the YouTube section"},
}

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
            if isinstance(value, list) and not (2 <= len(value) <= 3 and all(isinstance(x, str) for x in value[1:])):
                errors.append(f"{where}: advisory {slug} must be a number or [intensity, note, spoiler note?]")
                continue
            level = value[0] if isinstance(value, list) else value
            if not isinstance(level, (int, float)) or not 0 <= level <= 1:
                errors.append(f"{where}: intensity for advisory {slug} must be in [0, 1]")
        for r in w.get("ratings", []):
            if len(r) != 3 or not all(isinstance(x, str) for x in r[:2]) or not (r[2] is None or isinstance(r[2], str)):
                errors.append(f"{where}: rating must be [system, rating, reason or null], got {r!r}")
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
        if r[1] not in RELATIONSHIP_TYPES:
            errors.append(f"relationships[{i}]: unknown relationship type {r[1]!r}")
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
               "attributes", "advisories_assessed", "page_count")


def _work_values(w: dict, profile: WorkProfile) -> dict:
    # Year, runtime and page count come from the merged profile: a fetched source value replaces the
    # unverified seed value (the seed value stays in field_provenance, not selected).
    return {
        "medium": w["medium"],
        "title": w["title"],
        "original_title": w.get("original_title"),
        "original_language": w.get("language"),
        "countries": w.get("countries", []),
        "release_year": profile.year,
        "summary": w.get("summary"),
        "runtime_minutes": profile.runtime_minutes,
        "playtime_hours": w.get("playtime_hours"),
        "length_is_estimate": bool(w.get("length_is_estimate", False)),
        "popularity_tier": w.get("popularity_tier"),
        "attributes": w.get("attributes", {}),
        "advisories_assessed": bool(w.get("advisories")),
        "page_count": profile.page_count,
    }


def _upsert_work(conn: psycopg.Connection, w: dict, stats: ImportStats, profile: WorkProfile) -> str:
    values = _work_values(w, profile)
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


def import_catalogue(conn: psycopg.Connection, data: dict, tax: Taxonomy | None = None,
                     enrichment: dict | None = None) -> ImportStats:
    from mde.catalogue.memory import profiles_from_catalogue

    tax = tax or taxonomy_mod.load()
    errors = validate(data, tax)
    if errors:
        raise ValidationFailed(errors)
    enrichment = enrichment or {}
    profiles = {p.slug: p for p in enrich.apply(profiles_from_catalogue(data, tax), enrichment)}
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
            work_id = _upsert_work(conn, w, stats, profiles[w["slug"]])
            work_ids[w["slug"]] = work_id

            if w.get("original_title"):
                conn.execute(
                    "INSERT INTO work_title (work_id, title, language, kind) VALUES (%s, %s, %s, 'original') "
                    "ON CONFLICT DO NOTHING",
                    (work_id, w["original_title"], w.get("language")),
                )

            prof = profiles[w["slug"]]
            for fname, key in (("release_year", "year"), ("runtime_minutes", "runtime_minutes"),
                               ("playtime_hours", "playtime_hours")):
                if w.get(key) is not None:
                    conn.execute(
                        "INSERT INTO field_provenance (work_id, field, value, source_id, is_selected) VALUES (%s, %s, %s, %s, %s) "
                        "ON CONFLICT (work_id, field, source_id) DO UPDATE SET value = EXCLUDED.value, is_selected = EXCLUDED.is_selected",
                        (work_id, fname, Jsonb(w[key]), sources["editorial-seed"], fname not in prof.fact_sources),
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
                rows.append((key, strength, conf, None, None))
            # Only listed advisory categories were assessed. A listed 0 means "assessed, none"; an unlisted
            # category stays absent, which reads as "not assessed".
            for slug, value in (w.get("advisories") or {}).items():
                level, note, spoiler = parse_advisory(value)
                rows.append((f"advisory:{slug}", level, defaults["advisory_confidence"], note, spoiler))
            for key, strength, conf, note, spoiler in rows:
                conn.execute(
                    "INSERT INTO classification (work_id, term_id, strength, confidence, origin, is_interpretation, "
                    "evidence, spoiler_evidence, source_id, taxonomy_version) "
                    "VALUES (%s, %s, %s, %s, 'ai_assisted', %s, %s, %s, %s, %s)",
                    # Everything from this source is an interpretation, genres included: none of it has
                    # been checked against an authoritative source yet.
                    (work_id, term_ids[key], strength, conf, True, note, spoiler, sources["ai-assisted-seed"],
                     tax.version),
                )
                stats.classifications += 1

            conn.execute("DELETE FROM content_rating WHERE work_id = %s AND source_id = %s",
                         (work_id, sources["editorial-seed"]))
            for system, rating, reason in w.get("ratings", []):
                conn.execute(
                    "INSERT INTO content_rating (work_id, system, rating, reason, source_id) VALUES (%s, %s, %s, %s, %s)",
                    (work_id, system, rating, reason, sources["editorial-seed"]),
                )

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

        _import_enrichment(conn, profiles, enrichment, work_ids)

        conn.execute(
            "UPDATE import_run SET finished_at = now(), stats = %s WHERE id = %s",
            (Jsonb({k: v for k, v in stats.__dict__.items() if k != "warnings"}), run_id),
        )
    return stats


def _import_enrichment(conn: psycopg.Connection, profiles: dict[str, WorkProfile], enrichment: dict,
                       work_ids: dict[str, str]) -> None:
    """Persists the merged enrichment. Rows are replaced per source, so re-importing changes nothing."""
    src_ids = {}
    for slug, meta in OPEN_SOURCES.items():
        if slug in enrichment:
            src_ids[slug] = conn.execute(
                "INSERT INTO source (slug, name, kind, licence, commercial_use, may_store, may_display, ai_use, attribution, notes) "
                "VALUES (%(slug)s, %(name)s, %(kind)s, %(licence)s, %(commercial_use)s, %(may_store)s, %(may_display)s, "
                "%(ai_use)s, %(attribution)s, %(notes)s) ON CONFLICT (slug) DO UPDATE SET licence = EXCLUDED.licence, "
                "attribution = EXCLUDED.attribution, notes = EXCLUDED.notes RETURNING id", {"slug": slug, **meta},
            ).fetchone()["id"]
    # Every enrichment source is replaced, including one no longer in the import, so a dropped source leaves nothing behind.
    ids = [r["id"] for r in conn.execute("SELECT id FROM source WHERE slug = ANY(%s)", (list(OPEN_SOURCES),)).fetchall()]
    if not ids:
        return
    conn.execute("DELETE FROM source_record WHERE source_id = ANY(%s) AND NOT source_id = ANY(%s)",
                 (ids, list(src_ids.values())))
    for table in ("work_image", "work_score", "box_office", "work_link"):
        if table == "work_link":
            conn.execute("DELETE FROM work_link")
        else:
            conn.execute(f"DELETE FROM {table} WHERE source_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM work_group WHERE source_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM field_provenance WHERE source_id = ANY(%s)", (ids,))
    for source, data in enrichment.items():
        if source not in src_ids:
            continue
        # A source's file is a complete snapshot: records it no longer contains (e.g. a corrected match) must go.
        conn.execute("DELETE FROM source_record WHERE source_id = %s", (src_ids[source],))
        for slug, rec in data.get("works", {}).items():
            if slug in work_ids and rec.get("match"):
                ext = rec["match"].get("qid") or rec["match"].get("key") or rec["match"].get("mbid") or str(rec["match"].get("tmdb"))
                conn.execute(
                    "INSERT INTO source_record (source_id, external_id, work_id, payload, fetched_at) VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (source_id, external_id) DO UPDATE SET work_id = EXCLUDED.work_id, payload = EXCLUDED.payload, "
                    "fetched_at = EXCLUDED.fetched_at",
                    (src_ids[source], ext, work_ids[slug], Jsonb(rec), data["generated_at"]),
                )
    groups: dict[str, str] = {}
    for slug, p in profiles.items():
        wid = work_ids[slug]
        for fact, info in p.fact_sources.items():
            value = {"release_year": p.year, "runtime_minutes": p.runtime_minutes, "page_count": p.page_count}[fact]
            conn.execute("INSERT INTO field_provenance (work_id, field, value, source_id, is_selected) VALUES (%s, %s, %s, %s, true)",
                         (wid, fact, Jsonb(value), src_ids[info["source"]]))
        for img in p.images:
            conn.execute("INSERT INTO work_image (work_id, kind, url, source_id, licence, attribution) VALUES (%s, %s, %s, %s, %s, %s)",
                         (wid, img.kind, img.url, src_ids[img.source], img.licence, img.attribution))
        for sc in p.scores:
            conn.execute("INSERT INTO work_score (work_id, publisher, metric, value, scale_max, votes, source_id, as_of) "
                         "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                         (wid, sc.publisher, sc.metric, sc.value, sc.scale_max, sc.votes, src_ids[sc.source], sc.as_of))
        for b in p.box_office:
            conn.execute("INSERT INTO box_office (work_id, scope, amount, currency, source_id) VALUES (%s, %s, %s, %s, %s) "
                         "ON CONFLICT DO NOTHING", (wid, b["scope"], b["amount"], b["currency"], src_ids[b["source"]]))
        for link in p.links:
            conn.execute("INSERT INTO work_link (work_id, kind, url, label) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                         (wid, link["kind"], link["url"], link["label"]))
        for g in p.groups:
            if g.source not in src_ids:
                continue  # editorial series groups come from the seed's attributes; not duplicated here
            if g.slug not in groups:
                groups[g.slug] = conn.execute(
                    "INSERT INTO work_group (slug, name, kind, source_id) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name RETURNING id",
                    (g.slug, g.name, g.kind, src_ids[g.source])).fetchone()["id"]
            conn.execute("INSERT INTO work_group_member (group_id, work_id, position) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                         (groups[g.slug], wid, float(g.position) if g.position and g.position.replace(".", "", 1).isdigit() else None))


def load_seed(conn: psycopg.Connection, path: Path | None = None, enrichment: dict | None = None) -> ImportStats:
    """Imports the whole seed (all seed/*.json), or one file when a path is given."""
    return import_catalogue(conn, read_seed() if path is None else json.loads(path.read_text()),
                            enrichment=enrich.load_enrichment() if enrichment is None else enrichment)
