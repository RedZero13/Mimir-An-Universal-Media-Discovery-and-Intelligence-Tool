"""Read-side access to the catalogue. Returns plain dataclasses so ranking can be tested without a database."""

from __future__ import annotations

import re

import psycopg

from mde.catalogue.model import PRIMARY_ROLES, Relation, TermEvidence, WorkProfile, normalise_title

__all__ = ["Relation", "TermEvidence", "WorkProfile", "get_work", "keyword_scores", "load_profiles", "resolve_title"]


def load_profiles(conn: psycopg.Connection) -> list[WorkProfile]:
    """Loads every work with its classifications and relationships.

    The pilot catalogue is hundreds of works, so ranking in memory is simpler and fully inspectable. When
    the catalogue outgrows this, retrieval moves into SQL / pgvector and only the shortlist is loaded.
    """
    rows = conn.execute(
        "SELECT id::text, slug, medium, title, original_title, release_year, original_language, countries, summary, "
        "runtime_minutes, playtime_hours, length_is_estimate, popularity_tier, advisories_assessed FROM work"
    ).fetchall()
    works = {
        r["id"]: WorkProfile(
            id=r["id"], slug=r["slug"], medium=r["medium"], title=r["title"], original_title=r["original_title"],
            year=r["release_year"], language=r["original_language"], countries=list(r["countries"]),
            summary=r["summary"], runtime_minutes=r["runtime_minutes"],
            playtime_hours=float(r["playtime_hours"]) if r["playtime_hours"] is not None else None,
            length_is_estimate=r["length_is_estimate"], popularity_tier=r["popularity_tier"],
            advisories_assessed=r["advisories_assessed"],
        )
        for r in rows
    }
    for r in conn.execute(
        "SELECT c.work_id::text, t.dimension || ':' || t.slug AS key, c.strength, c.confidence, c.origin, "
        "c.review_status, c.is_interpretation FROM classification c JOIN taxonomy_term t ON t.id = c.term_id "
        "WHERE c.review_status <> 'rejected' AND NOT t.deprecated AND NOT c.is_spoiler"
    ).fetchall():
        w = works[r["work_id"]]
        ev = TermEvidence(r["strength"], r["confidence"], r["origin"], r["review_status"], r["is_interpretation"])
        # Several origins may classify the same term; keep the most confident claim.
        if r["key"] not in w.terms or w.terms[r["key"]].confidence < ev.confidence:
            w.terms[r["key"]] = ev
    for r in conn.execute(
        "SELECT cr.work_id::text, coalesce(p.name, o.name) AS name FROM credit cr "
        "LEFT JOIN person p ON p.id = cr.person_id LEFT JOIN organisation o ON o.id = cr.organisation_id "
        "WHERE cr.role = ANY(%s) ORDER BY cr.ordinal", (list(PRIMARY_ROLES),)
    ).fetchall():
        works[r["work_id"]].creators.append(r["name"])
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


def get_work(conn: psycopg.Connection, slug: str) -> dict | None:
    work = conn.execute(
        "SELECT id, slug, medium, title, original_title, original_language, countries, release_year, summary, "
        "summary_spoiler, runtime_minutes, page_count, playtime_hours, length_is_estimate, popularity_tier, "
        "attributes, advisories_assessed, updated_at FROM work WHERE slug = %s", (slug,)
    ).fetchone()
    if work is None:
        return None
    wid = work.pop("id")
    if work["playtime_hours"] is not None:
        work["playtime_hours"] = float(work["playtime_hours"])
    work["updated_at"] = work["updated_at"].isoformat()
    work["credits"] = conn.execute(
        "SELECT cr.role, coalesce(p.name, o.name) AS name, CASE WHEN p.id IS NULL THEN 'organisation' ELSE 'person' "
        "END AS kind, s.slug AS source FROM credit cr LEFT JOIN person p ON p.id = cr.person_id "
        "LEFT JOIN organisation o ON o.id = cr.organisation_id JOIN source s ON s.id = cr.source_id "
        "WHERE cr.work_id = %s ORDER BY cr.ordinal", (wid,)
    ).fetchall()
    work["classifications"] = conn.execute(
        "SELECT t.dimension, t.slug, t.label, t.definition, c.strength, c.confidence, c.origin, c.review_status, "
        "c.is_interpretation, c.is_spoiler, c.taxonomy_version, s.slug AS source FROM classification c "
        "JOIN taxonomy_term t ON t.id = c.term_id JOIN source s ON s.id = c.source_id "
        "WHERE c.work_id = %s AND c.review_status <> 'rejected' ORDER BY t.dimension, c.strength DESC", (wid,)
    ).fetchall()
    work["relationships"] = conn.execute(
        "SELECT CASE WHEN r.from_work_id = %(id)s THEN rt.label ELSE rt.inverse END AS label, r.type, rt.factual, "
        "w.slug, w.title, w.medium, w.release_year, r.note, r.confidence, r.origin, r.review_status, r.is_spoiler "
        "FROM relationship r JOIN relationship_type rt ON rt.slug = r.type "
        "JOIN work w ON w.id = CASE WHEN r.from_work_id = %(id)s THEN r.to_work_id ELSE r.from_work_id END "
        "WHERE (r.from_work_id = %(id)s OR r.to_work_id = %(id)s) AND r.review_status <> 'rejected' "
        "ORDER BY rt.factual DESC, r.confidence DESC", {"id": wid}
    ).fetchall()
    work["provenance"] = conn.execute(
        "SELECT fp.field, fp.value, s.slug AS source, s.name AS source_name, fp.observed_at::date::text AS observed "
        "FROM field_provenance fp JOIN source s ON s.id = fp.source_id WHERE fp.work_id = %s AND fp.is_selected "
        "ORDER BY fp.field", (wid,)
    ).fetchall()
    work["sources"] = conn.execute(
        "SELECT DISTINCT s.slug, s.name, s.kind, s.notes FROM source s WHERE s.id IN ("
        "SELECT source_id FROM credit WHERE work_id = %(id)s UNION SELECT source_id FROM classification "
        "WHERE work_id = %(id)s UNION SELECT source_id FROM field_provenance WHERE work_id = %(id)s)", {"id": wid}
    ).fetchall()
    return work
