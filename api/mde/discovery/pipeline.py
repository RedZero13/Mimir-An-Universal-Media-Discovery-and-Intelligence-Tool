"""The discovery pipeline with no storage dependency: interpret → retrieve → rank → diversify → explain.

Storage is supplied by the caller as a list of work profiles, a keyword scorer and a title resolver, so the
same code serves PostgreSQL (engine.py) and the in-memory catalogue (memory.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mde import taxonomy as taxonomy_mod
from mde.catalogue.model import WorkProfile
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
                "Nothing in the catalogue matches this well enough to recommend. The beta catalogue is still growing; "
                "try describing the experience you want rather than a specific subject."),
        }


def run_pipeline(query: str, works: list[WorkProfile], keyword_scorer: Callable[[list[str]], dict[str, float]],
                 resolve_title: Callable[[str], str | None], limit: int = 8, parser: IntentParser | None = None,
                 weights: RankingWeights = DEFAULT_WEIGHTS) -> DiscoveryResponse:
    tax = taxonomy_mod.load()
    parser = parser or RuleBasedIntentParser(tax, resolve_title)
    intent = parser.parse(query)
    ranked = rank(intent, works, keyword_scorer(intent.keywords), limit=limit, weights=weights)
    ref = ranked.reference
    return DiscoveryResponse(
        event_id=None, intent=intent, results=[explain(s, tax) for s in ranked.results],
        excluded=dict(ranked.excluded), weak_dropped=ranked.weak_dropped, considered=ranked.considered,
        reference={"slug": ref.slug, "title": ref.title, "medium": ref.medium} if ref else None,
        parser=parser.name, ranker=RANKER_VERSION,
    )
