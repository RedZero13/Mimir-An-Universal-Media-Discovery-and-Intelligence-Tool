"""HTTP API. Thin: validation and serialisation only; logic lives in catalogue/ and discovery/."""

from __future__ import annotations

import os
import uuid
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mde import db
from mde import taxonomy as taxonomy_mod
from mde.catalogue import browse, providers, repository
from mde.discovery.engine import discover

app = FastAPI(title="Media Discovery Engine", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

FeedbackKind = Literal["relevant", "irrelevant", "too_long", "wrong_mood", "already_experienced",
                       "not_what_i_meant", "will_try"]


class FeedbackIn(BaseModel):
    event_id: str | None = None
    work_slug: str = Field(max_length=200)
    kind: FeedbackKind
    note: str | None = Field(default=None, max_length=1000)


@app.get("/api/health")
def health() -> dict:
    with db.connect() as conn:
        works = conn.execute("SELECT count(*) AS n FROM work").fetchone()["n"]
    return {"status": "ok", "works": works}


@app.get("/api/discover")
def discover_endpoint(q: str = Query(min_length=2, max_length=500), limit: int = Query(8, ge=1, le=20)) -> dict:
    with db.connect() as conn:
        return discover(conn, q, limit=limit).to_dict()


@app.get("/api/works")
def browse_endpoint(
    medium: list[str] = Query(default=[]),
    tag: list[str] = Query(default=[], description="taxonomy keys such as theme:grief-loss; all must apply"),
    decade: int | None = Query(default=None, ge=1800, le=2100),
    language: str | None = Query(default=None, max_length=8),
    country: str | None = Query(default=None, max_length=8),
    max_minutes: int | None = Query(default=None, ge=1),
    avoid: list[str] = Query(default=[], description="advisory keys; keeps works assessed as none or mild"),
    exclude: list[str] = Query(default=[], description="taxonomy keys that must not apply"),
    year_min: int | None = Query(default=None, ge=1000, le=2100),
    year_max: int | None = Query(default=None, ge=1000, le=2100),
    q: str = Query(default="", max_length=200),
    sort: Literal["popular", "title", "newest", "oldest", "shortest"] = "popular",
) -> dict:
    tax = taxonomy_mod.load()
    unknown = [k for k in [*tag, *avoid, *exclude] if k not in tax.terms]
    if unknown or any(not k.startswith("advisory:") for k in avoid):
        raise HTTPException(422, f"unknown or invalid taxonomy keys: {unknown or avoid}")
    filters = browse.BrowseFilters(media=medium, tags=tag, decade=decade, language=language, country=country,
                                   max_minutes=max_minutes, avoid=avoid, exclude=exclude, year_min=year_min,
                                   year_max=year_max, q=q, sort=sort)
    with db.connect() as conn:
        return browse.browse(repository.load_profiles(conn), tax, filters)


@app.get("/api/works/{slug}")
def work_endpoint(slug: str) -> dict:
    with db.connect() as conn:
        works = repository.load_profiles(conn)
        work = next((w for w in works if w.slug == slug), None)
        if work is None:
            raise HTTPException(404, "work not found")
        return {**browse.work_page(work, works, taxonomy_mod.load()), **repository.work_sources(conn, slug)}


@app.get("/api/works/{slug}/where")
def where_endpoint(slug: str, region: str | None = Query(default=None, max_length=4)) -> dict:
    """Links to watch, listen, read or play on each service (search links; availability varies by region)."""
    with db.connect() as conn:
        work = next((w for w in repository.load_profiles(conn) if w.slug == slug), None)
    if work is None:
        raise HTTPException(404, "work not found")
    return providers.where_to(providers.item_of(work), region)


@app.get("/api/tags")
def tags_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.tag_index(repository.load_profiles(conn), taxonomy_mod.load())


@app.get("/api/tags/{dimension}/{slug}")
def tag_endpoint(dimension: str, slug: str) -> dict:
    with db.connect() as conn:
        page = browse.tag_page(repository.load_profiles(conn), taxonomy_mod.load(), f"{dimension}:{slug}")
    if page is None:
        raise HTTPException(404, "tag not found")
    return page


@app.get("/api/people")
def people_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.people_index(repository.load_profiles(conn))


@app.get("/api/people/{slug}")
def person_endpoint(slug: str) -> dict:
    with db.connect() as conn:
        page = browse.person_page(repository.load_profiles(conn), taxonomy_mod.load(), slug)
    if page is None:
        raise HTTPException(404, "person not found")
    return page


@app.get("/api/shelves")
def shelves_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.shelves(repository.load_profiles(conn), taxonomy_mod.load())


@app.get("/api/shelves/{slug}")
def shelf_endpoint(slug: str) -> dict:
    with db.connect() as conn:
        page = browse.shelf(repository.load_profiles(conn), taxonomy_mod.load(), slug)
    if page is None:
        raise HTTPException(404, "shelf not found")
    return page


@app.get("/api/groups")
def groups_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.groups_index(repository.load_profiles(conn))


@app.get("/api/groups/{slug}")
def group_endpoint(slug: str) -> dict:
    with db.connect() as conn:
        page = browse.group_page(repository.load_profiles(conn), taxonomy_mod.load(), slug)
    if page is None:
        raise HTTPException(404, "group not found")
    return page


@app.get("/api/music/moods")
def mood_rings_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.mood_rings(repository.load_profiles(conn), taxonomy_mod.load())


@app.get("/api/music/remixes")
def remix_rack_endpoint() -> list[dict]:
    with db.connect() as conn:
        return browse.remix_rack(repository.load_profiles(conn))


class RecommendIn(BaseModel):
    ratings: dict[str, Literal["loved", "liked", "disliked", "want"]] = Field(max_length=2000)
    limit: int = Field(default=12, ge=1, le=50)
    medium: str | None = Field(default=None, max_length=20)


@app.post("/api/recommend")
def recommend_endpoint(body: RecommendIn) -> dict:
    """'For you': works closest to what you loved and liked, away from what you didn't, each with its reason."""
    with db.connect() as conn:
        return browse.recommend(repository.load_profiles(conn), taxonomy_mod.load(), body.ratings, body.limit, body.medium)


@app.get("/api/taxonomy")
def taxonomy_endpoint() -> dict:
    tax = taxonomy_mod.load()
    return {
        "version": tax.version,
        "dimensions": [d.__dict__ for d in tax.dimensions.values()],
        "terms": [{"key": t.key, "dimension": t.dimension, "slug": t.slug, "label": t.label,
                   "definition": t.definition, "applies_to": list(t.applies_to), "group": t.group}
                  for t in tax.terms.values()],
        "guide_groups": [{"slug": g, "label": label} for g, label in tax.guide_groups],
    }


@app.post("/api/feedback", status_code=201)
def feedback_endpoint(body: FeedbackIn) -> dict:
    with db.connect() as conn:
        work = conn.execute("SELECT id FROM work WHERE slug = %s", (body.work_slug,)).fetchone()
        if work is None:
            raise HTTPException(404, "work not found")
        event_id = body.event_id
        if event_id is not None:
            try:
                uuid.UUID(event_id)
            except ValueError:
                raise HTTPException(422, "unknown event_id") from None
            if conn.execute("SELECT 1 FROM discovery_event WHERE id = %s", (event_id,)).fetchone() is None:
                raise HTTPException(422, "unknown event_id")
        conn.execute("INSERT INTO feedback (event_id, work_id, kind, note) VALUES (%s, %s, %s, %s)",
                     (event_id, work["id"], body.kind, body.note))
        conn.commit()
    return {"ok": True}
