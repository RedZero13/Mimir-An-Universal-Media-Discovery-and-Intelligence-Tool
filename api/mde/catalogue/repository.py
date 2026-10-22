"""Read-side access to the catalogue. Returns plain dataclasses so ranking can be tested without a database."""

from __future__ import annotations

import re

import psycopg

from mde.catalogue.model import PRIMARY_ROLES, Credit, Rating, Relation, TermEvidence, WorkProfile, normalise_title

__all__ = ["Relation", "TermEvidence", "WorkProfile", "keyword_scores", "load_profiles", "resolve_title", "work_sources"]


def load_profiles(conn: psycopg.Connection) -> list[WorkProfile]:
    """Loads every work with its classifications and relationships.

    The pilot catalogue is hundreds of works, so ranking in memory is simpler and fully inspectable. When
    the catalogue outgrows this, retrieval moves into SQL / pgvector and only the shortlist is loaded.
    """
    rows = conn.execute(
        "SELECT id::text, slug, medium, title, original_title, release_year, original_language, countries, summary, "
        "runtime_minutes, playtime_hours, length_is_estimate, popularity_tier, advisories_assessed, attributes FROM work"
    ).fetchall()
    works = {
        r["id"]: WorkProfile(
            id=r["id"], slug=r["slug"], medium=r["medium"], title=r["title"], original_title=r["original_title"],
            year=r["release_year"], language=r["original_language"], countries=list(r["countries"]),
            summary=r["summary"], runtime_minutes=r["runtime_minutes"],
            playtime_hours=float(r["playtime_hours"]) if r["playtime_hours"] is not None else None,
            length_is_estimate=r["length_is_estimate"], popularity_tier=r["popularity_tier"],
            advisories_assessed=r["advisories_assessed"], attributes=r["attributes"],
        )
        for r in rows
    }
    for r in conn.execute(
        "SELECT c.work_id::text, t.dimension || ':' || t.slug AS key, c.strength, c.confidence, c.origin, "
        "c.review_status, c.is_interpretation, c.evidence, c.spoiler_evidence FROM classification c "
        "JOIN taxonomy_term t ON t.id = c.term_id "
        "WHERE c.review_status <> 'rejected' AND NOT t.deprecated AND NOT c.is_spoiler"
    ).fetchall():
        w = works[r["work_id"]]
        ev = TermEvidence(r["strength"], r["confidence"], r["origin"], r["review_status"], r["is_interpretation"],
                          r["evidence"], r["spoiler_evidence"])
        # Several origins may classify the same term; keep the most confident claim.
        if r["key"] not in w.terms or w.terms[r["key"]].confidence < ev.confidence:
            w.terms[r["key"]] = ev
    for r in conn.execute(
        "SELECT cr.work_id::text, cr.role, coalesce(p.name, o.name) AS name, "
        "CASE WHEN p.id IS NULL THEN 'organisation' ELSE 'person' END AS kind FROM credit cr "
        "LEFT JOIN person p ON p.id = cr.person_id LEFT JOIN organisation o ON o.id = cr.organisation_id "
        "ORDER BY cr.work_id, cr.ordinal"
    ).fetchall():
        w = works[r["work_id"]]
        w.credits.append(Credit(r["role"], r["name"], r["kind"]))
        if r["role"] in PRIMARY_ROLES:
            w.creators.append(r["name"])
    for r in conn.execute(
        "SELECT work_id::text, system, rating, reason FROM content_rating ORDER BY work_id, system"
    ).fetchall():
        works[r["work_id"]].ratings.append(Rating(r["system"], r["rating"], r["reason"]))
    for r in conn.execute(
        "SELECT r.from_work_id::text AS a, r.to_work_id::text AS b, r.type, r.note, r.confidence, r.origin, "
        "rt.label, rt.inverse, rt.factual FROM relationship r JOIN relationship_type rt ON rt.slug = r.type "
        "WHERE r.review_status <> 'rejected' AND NOT r.is_spoiler"
    ).fetchall():
        a, b = works[r["a"]], works[r["b"]]
        a.relations.append(Relation(b.slug, b.title, b.medium, r["type"], r["label"], r["note"], r["confidence"],
                                    r["origin"], r["factual"]))
        b.relations.append(Relation(a.slug, a.title, a.medium, r["type"], r["inverse"], r["note"], r["confidence"],
                                    r["origin"], r["factual"]))
    return list(works.values())


def keyword_scores(conn: psycopg.Connection, keywords: list[str]) -> dict[str, float]:
    """Full-text relevance per work slug, normalised to [0, 1]. Keywords are OR-ed."""
    words = [w for w in (re.sub(r"[^a-z0-9]", "", k.lower()) for k in keywords) if w]
    if not words:
        return {}
    rows = conn.execute(
        "SELECT slug, ts_rank(search, q) AS rank FROM work, to_tsquery('english', %s) q WHERE search @@ q",
        (" | ".join(words),),
    ).fetchall()
    if not rows:
        return {}
    top = max(r["rank"] for r in rows) or 1.0
    return {r["slug"]: r["rank"] / top for r in rows}


def resolve_title(conn: psycopg.Connection, phrase: str) -> str | None:
    """Exact (normalised) title or alternative-title match. Ambiguity picks the best-known work."""
    target = normalise_title(phrase)
    if not target:
        return None
    rows = conn.execute(
        "SELECT w.slug, w.title, w.popularity_tier, array_remove(array_agg(wt.title), NULL) AS alts "
        "FROM work w LEFT JOIN work_title wt ON wt.work_id = w.id GROUP BY w.id"
    ).fetchall()
    hits = [r for r in rows if target in {normalise_title(t) for t in [r["title"], *r["alts"]]}]
    if not hits:
        return None
    hits.sort(key=lambda r: (r["popularity_tier"] or 5))
    return hits[0]["slug"]


def work_sources(conn: psycopg.Connection, slug: str) -> dict | None:
    """Database-only provenance for a work page: which source supplied each fact, and the sources involved."""
    row = conn.execute("SELECT id FROM work WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        return None
    wid = row["id"]
    return {
        "provenance": conn.execute(
            "SELECT fp.field, fp.value, s.slug AS source, s.name AS source_name, fp.observed_at::date::text AS observed "
            "FROM field_provenance fp JOIN source s ON s.id = fp.source_id WHERE fp.work_id = %s AND fp.is_selected "
            "ORDER BY fp.field", (wid,)
        ).fetchall(),
        "sources": conn.execute(
            "SELECT DISTINCT s.slug, s.name, s.kind, s.notes FROM source s WHERE s.id IN ("
            "SELECT source_id FROM credit WHERE work_id = %(id)s UNION SELECT source_id FROM classification "
            "WHERE work_id = %(id)s UNION SELECT source_id FROM field_provenance WHERE work_id = %(id)s "
            "UNION SELECT source_id FROM content_rating WHERE work_id = %(id)s) ORDER BY s.slug", {"id": wid}
        ).fetchall(),
    }
