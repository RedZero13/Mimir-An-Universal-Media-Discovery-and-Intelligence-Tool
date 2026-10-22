"""Discovery against PostgreSQL: runs the pipeline over the stored catalogue and logs the event."""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from mde.catalogue import repository
from mde.discovery.intent import IntentParser
from mde.discovery.pipeline import DiscoveryResponse, run_pipeline
from mde.discovery.rank import DEFAULT_WEIGHTS, RANKER_VERSION, RankingWeights

__all__ = ["DiscoveryResponse", "discover"]


def discover(conn: psycopg.Connection, query: str, limit: int = 8, log: bool = True,
             parser: IntentParser | None = None, weights: RankingWeights = DEFAULT_WEIGHTS) -> DiscoveryResponse:
    resp = run_pipeline(
        query,
        repository.load_profiles(conn),
        lambda keywords: repository.keyword_scores(conn, keywords),
        lambda phrase: repository.resolve_title(conn, phrase),
        limit=limit, parser=parser, weights=weights,
    )
    if log:
        resp.event_id = str(conn.execute(
            "INSERT INTO discovery_event (query, intent, results, ranker) VALUES (%s, %s, %s, %s) RETURNING id",
            (query, Jsonb(resp.intent.to_dict()),
             Jsonb([{"slug": r["slug"], "rank": i + 1, "score": r["score"]} for i, r in enumerate(resp.results)]),
             f"{resp.parser}/{RANKER_VERSION}"),
        ).fetchone()["id"])
        conn.commit()
    return resp
