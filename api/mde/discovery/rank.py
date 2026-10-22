"""Transparent, tunable ranking.

Every number that contributes to a score is kept in `ScoredWork.breakdown`, and every reason shown to a
user is derived from the same evidence the score used. Weights live in `RankingWeights` so they can be
tuned against the benchmark rather than edited in place.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from mde.catalogue.repository import Relation, WorkProfile
from mde.discovery.intent import Intent

RANKER_VERSION = "transparent-v1"


@dataclass(frozen=True)
class RankingWeights:
    reference_weight_alone: float = 1.0
    reference_weight_with_prefs: float = 0.7
    keyword_weight_alone: float = 1.0
    keyword_weight_with_others: float = 0.25
    relation_boost: float = 0.2
    obscure_bonus: float = 0.15
    popular_bonus: float = 0.1
    soft_avoid_penalty: float = 0.3
    near_threshold_penalty: float = 0.15
    unknown_advisory_penalty: float = 0.08
    over_length_penalty_per_hour: float = 0.25
    max_over_length_penalty: float = 0.3
    unknown_length_penalty: float = 0.06
    out_of_era_penalty: float = 0.1
    min_relevance: float = 0.12
    same_medium_diversity: float = 0.04
    same_creator_diversity: float = 0.08
    match_threshold: float = 0.4     # a term only counts as a stated match at or above this strength


DEFAULT_WEIGHTS = RankingWeights()


@dataclass
class MatchedTerm:
    term: str
    weight: float
    strength: float
    confidence: float
    is_interpretation: bool
    review_status: str
    source: str            # "request" or "reference"


@dataclass
class ScoredWork:
    work: WorkProfile
    score: float = 0.0
    relevance: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    matched: list[MatchedTerm] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)         # requested terms this work lacks
    relation: Relation | None = None
    caveats: list[str] = field(default_factory=list)
    constraint_notes: list[str] = field(default_factory=list)


@dataclass
class RankResult:
    results: list[ScoredWork]
    considered: int
    excluded: Counter
    weak_dropped: int
    reference: WorkProfile | None


def _length_label(w: WorkProfile) -> str:
    approx = "about " if w.length_is_estimate else ""
    if w.runtime_minutes is not None:
        return f"{approx}{w.runtime_minutes} min"
    if w.playtime_hours is not None:
        return f"{approx}{w.playtime_hours:g} hours to finish"
    return "length unknown"


def _reference_vector(ref: WorkProfile) -> dict[str, float]:
    return {k: ev.strength for k, ev in ref.terms.items()
            if not k.startswith("advisory:") and ev.strength >= 0.4}


def rank(intent: Intent, works: list[WorkProfile], keyword_scores: dict[str, float] | None = None,
         limit: int = 8, weights: RankingWeights = DEFAULT_WEIGHTS) -> RankResult:
    keyword_scores = keyword_scores or {}
    by_slug = {w.slug: w for w in works}
    ref = by_slug.get(intent.reference_slug) if intent.reference_slug else None
    ref_vec = _reference_vector(ref) if ref else {}
    excluded: Counter = Counter()
    candidates: list[ScoredWork] = []

    for w in works:
        if ref and w.slug == ref.slug:
            continue
        reason = _hard_exclusion(intent, w, ref)
        if reason:
            excluded[reason] += 1
            continue
        candidates.append(_score(intent, w, ref, ref_vec, keyword_scores, weights))

    has_signal = bool(intent.preferences or ref or intent.keywords)
    # Weak: too little relevance overall, or (when qualities were requested) none of them present — a stray
    # keyword hit alone shouldn't surface a work that matches nothing the person described.
    weak = [c for c in candidates if c.relation is None and has_signal and (
        c.relevance < weights.min_relevance
        or (intent.preferences and not ref and c.breakdown.get("request_match", 0) < 0.05))]
    kept = [c for c in candidates if c not in weak]
    kept.sort(key=lambda c: (-c.score, c.work.title))
    return RankResult(_diversify(kept, intent, limit, weights), len(works), excluded, len(weak), ref)


def _hard_exclusion(intent: Intent, w: WorkProfile, ref: WorkProfile | None) -> str | None:
    if intent.media and w.medium not in intent.media:
        return "different medium"
    if w.medium in intent.excluded_media:
        return "excluded medium"
    if ref and intent.reference_other_medium and w.medium == ref.medium:
        return "same medium as the reference"
    if intent.languages and w.language not in intent.languages:
        return "different original language"
    if intent.excluded_languages and w.language in intent.excluded_languages:
        return "excluded original language"
    if intent.year_hard and w.year is not None:
        if intent.year_min and w.year < intent.year_min:
            return "outside the requested years"
        if intent.year_max and w.year > intent.year_max:
            return "outside the requested years"
    for a in intent.avoid:
        if a.hard and a.term in w.terms and w.terms[a.term].strength >= a.threshold:
            return "content you asked to avoid"
    if intent.length and intent.length.hard and w.length_minutes is not None \
            and w.length_minutes > intent.length.for_medium(w.medium):
        return "longer than your limit"
    return None


def _score(intent: Intent, w: WorkProfile, ref: WorkProfile | None, ref_vec: dict[str, float],
           keyword_scores: dict[str, float], weights: RankingWeights) -> ScoredWork:
    s = ScoredWork(work=w)
    components: list[tuple[float, float]] = []

    # Explicit preferences: weighted mean of how strongly each requested term applies, moderated by confidence.
    if intent.preferences:
        total = sum(p.weight for p in intent.preferences)
        got = 0.0
        for p in intent.preferences:
            ev = w.terms.get(p.term)
            if ev and ev.strength > 0:
                got += p.weight * ev.strength * (0.5 + 0.5 * ev.confidence)
                if ev.strength >= weights.match_threshold:
                    s.matched.append(MatchedTerm(p.term, p.weight, ev.strength, ev.confidence,
                                                 ev.is_interpretation, ev.review_status, "request"))
                else:
                    s.unmatched.append(p.term)
            else:
                s.unmatched.append(p.term)
        explicit = got / total
        s.breakdown["request_match"] = round(explicit, 3)
        components.append((explicit, 1.0))

    # Reference similarity: how much of the reference's profile this work shares. Genre only counts within
    # the same medium; a novel isn't "less similar" to a game for lacking the 'rpg' tag.
    if ref:
        vec = {k: v for k, v in ref_vec.items() if w.medium == ref.medium or not k.startswith("genre:")}
        denom = sum(vec.values()) or 1.0
        shared = 0.0
        for k, rv in vec.items():
            ev = w.terms.get(k)
            if ev and ev.strength >= weights.match_threshold:
                shared += min(rv, ev.strength)
                if not any(m.term == k for m in s.matched):
                    s.matched.append(MatchedTerm(k, rv, ev.strength, ev.confidence, ev.is_interpretation,
                                                 ev.review_status, "reference"))
        similarity = shared / denom
        s.breakdown["reference_similarity"] = round(similarity, 3)
        weight = weights.reference_weight_with_prefs if intent.preferences else weights.reference_weight_alone
        components.append((similarity, weight))
        rel = next((r for r in w.relations if r.other_slug == ref.slug), None)
        if rel:
            s.relation = rel
            s.breakdown["relationship"] = round(weights.relation_boost * rel.confidence, 3)

    if intent.keywords:
        # Unmatched keywords still count (as zero): a request whose only content is words the catalogue
        # doesn't contain should return nothing, not everything.
        kw = keyword_scores.get(w.slug, 0.0)
        s.breakdown["keyword_match"] = round(kw, 3)
        others = bool(intent.preferences or ref)
        components.append((kw, weights.keyword_weight_with_others if others else weights.keyword_weight_alone))

    s.relevance = sum(v * wt for v, wt in components) / sum(wt for _, wt in components) if components else 0.5
    penalty = 0.0

    for a in intent.avoid:
        ev = w.terms.get(a.term)
        if ev is None:
            if a.hard:
                if a.term.startswith("advisory:") and not w.advisories_assessed:
                    s.caveats.append("Content advisories haven't been assessed for this work yet.")
                penalty += weights.unknown_advisory_penalty
            continue
        if a.hard:
            if ev.strength >= 0.2:
                penalty += weights.near_threshold_penalty * ev.strength
        elif ev.strength >= a.threshold * 0.5:
            penalty += weights.soft_avoid_penalty * ev.strength
    if intent.avoid:
        s.breakdown["avoid_penalty"] = round(-penalty, 3)

    if intent.length:
        limit = intent.length.for_medium(w.medium)
        length = w.length_minutes
        if length is None:
            p = weights.unknown_length_penalty * (2 if intent.length.hard else 1)
            penalty += p
            s.breakdown["length_penalty"] = round(-p, 3)
            s.caveats.append("Length isn't recorded, so it couldn't be checked against your limit."
                             if w.medium != "book" else "Reading length isn't tracked yet.")
        elif length <= limit:
            s.constraint_notes.append(f"{_length_label(w)}: fits your {limit}-minute limit.")
        else:
            over = length - limit
            p = min(weights.max_over_length_penalty, weights.over_length_penalty_per_hour * over / 60)
            penalty += p
            s.breakdown["length_penalty"] = round(-p, 3)
            s.caveats.append(f"{_length_label(w)}: {over} min over your preferred {limit}.")

    if not intent.year_hard and w.year is not None and intent.year_min and w.year < intent.year_min:
        penalty += weights.out_of_era_penalty

    novelty = 0.0
    tier = w.popularity_tier
    if tier is not None and intent.novelty == "obscure":
        novelty = weights.obscure_bonus * (tier - 1) / 3
    elif tier is not None and intent.novelty == "popular":
        novelty = weights.popular_bonus * (4 - tier) / 3
    if novelty:
        s.breakdown["novelty"] = round(novelty, 3)

    s.score = round(s.relevance + s.breakdown.get("relationship", 0.0) + novelty - penalty, 4)
    s.breakdown["relevance"] = round(s.relevance, 3)
    s.breakdown["total"] = s.score
    return s


def _diversify(ranked: list[ScoredWork], intent: Intent, limit: int, weights: RankingWeights) -> list[ScoredWork]:
    """Greedy re-rank: small penalties for repeating a medium (when none was requested) or a creator."""
    pool = ranked[: limit * 3]
    chosen: list[ScoredWork] = []
    media: Counter = Counter()
    creators: Counter = Counter()
    while pool and len(chosen) < limit:
        def adjusted(c: ScoredWork) -> float:
            adj = c.score
            if not intent.media:
                adj -= weights.same_medium_diversity * media[c.work.medium]
            adj -= weights.same_creator_diversity * sum(creators[n] for n in c.work.creators)
            return adj
        best = max(pool, key=lambda c: (adjusted(c), -pool.index(c)))
        pool.remove(best)
        chosen.append(best)
        media[best.work.medium] += 1
        creators.update(best.work.creators)
    return chosen
