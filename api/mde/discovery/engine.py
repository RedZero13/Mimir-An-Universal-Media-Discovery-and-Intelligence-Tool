"""Discovery pipeline: interpret → retrieve → rank → diversify → explain → log."""

from __future__ import annotations

from dataclasses import dataclass

import psycopg
from psycopg.types.json import Jsonb

from mde import taxonomy as taxonomy_mod
from mde.catalogue import repository
from mde.discovery.explain import explain
from mde.discovery.intent import Intent, IntentParser, RuleBasedIntentParser
from mde.discovery.rank import DEFAULT_WEIGHTS, RANKER_VERSION, RankingWeights, rank


@dataclass
class DiscoveryResponse:
    event_id: str | None
    intent: Intent
    results: list[dict]
    excluded: dict[str, int]
    weak_dropped: int
    considered: int
    reference: dict | None
    parser: str
    ranker: str

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "interpretation": self.intent.to_dict(),
            "results": self.results,
            "excluded": self.excluded,
            "weak_matches_hidden": self.weak_dropped,
            "considered": self.considered,
            "reference": self.reference,
            "parser": self.parser,
            "ranker": self.ranker,
            "message": None if self.results else (
                "Nothing in the catalogue matches this well enough to recommend. The pilot catalogue is small; "
                "try describing the experience you want rather than a specific subject."),
        }


def discover(conn: psycopg.Connection, query: str, limit: int = 8, log: bool = True,
             parser: IntentParser | None = None, weights: RankingWeights = DEFAULT_WEIGHTS) -> DiscoveryResponse:
    tax = taxonomy_mod.load()
    parser = parser or RuleBasedIntentParser(tax, lambda phrase: repository.resolve_title(conn, phrase))
    intent = parser.parse(query)
    works = repository.load_profiles(conn)
    kw = repository.keyword_scores(conn, intent.keywords)
    ranked = rank(intent, works, kw, limit=limit, weights=weights)
    results = [explain(s, tax) for s in ranked.results]
    ref = ranked.reference

    event_id = None
    if log:
        event_id = str(conn.execute(
            "INSERT INTO discovery_event (query, intent, results, ranker) VALUES (%s, %s, %s, %s) RETURNING id",
            (query, Jsonb(intent.to_dict()),
             Jsonb([{"slug": r["slug"], "rank": i + 1, "score": r["score"]} for i, r in enumerate(results)]),
             f"{parser.name}/{RANKER_VERSION}"),
        ).fetchone()["id"])
        conn.commit()

    return DiscoveryResponse(
        event_id=event_id, intent=intent, results=results, excluded=dict(ranked.excluded),
        weak_dropped=ranked.weak_dropped, considered=ranked.considered,
        reference={"slug": ref.slug, "title": ref.title, "medium": ref.medium} if ref else None,
        parser=parser.name, ranker=RANKER_VERSION,
    )
