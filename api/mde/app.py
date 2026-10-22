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
from mde.catalogue import repository
from mde.discovery.engine import discover

app = FastAPI(title="Media Discovery Engine", version="0.1.0")
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


@app.get("/api/works/{slug}")
def work_endpoint(slug: str) -> dict:
    with db.connect() as conn:
        work = repository.get_work(conn, slug)
    if work is None:
        raise HTTPException(404, "work not found")
    return work


@app.get("/api/taxonomy")
def taxonomy_endpoint() -> dict:
    tax = taxonomy_mod.load()
    return {
        "version": tax.version,
        "dimensions": [d.__dict__ for d in tax.dimensions.values()],
        "terms": [{"key": t.key, "dimension": t.dimension, "slug": t.slug, "label": t.label,
                   "definition": t.definition, "applies_to": list(t.applies_to)} for t in tax.terms.values()],
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
