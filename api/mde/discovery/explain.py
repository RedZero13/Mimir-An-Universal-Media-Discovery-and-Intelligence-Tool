"""Turns ranking evidence into user-facing reasons.

Explanations are assembled from templates over the same evidence the ranker used. Nothing is generated
free-form, so every sentence can be traced to a classification, a fact or a relationship. Each reason
carries its basis so the UI can distinguish recorded facts from interpretations.
"""

from __future__ import annotations

from mde.discovery.rank import ScoredWork
from mde.taxonomy import Taxonomy

DIMENSION_ORDER = ["genre", "theme", "mood", "complexity", "narrative", "world", "style", "pacing"]


def _degree(strength: float) -> str:
    if strength >= 0.8:
        return "strongly"
    if strength >= 0.55:
        return "clearly"
    return "partly"


def _basis(is_interpretation: bool, review_status: str) -> str:
    if not is_interpretation:
        return "catalogue"
    return "interpretation" if review_status != "reviewed" else "reviewed_interpretation"


def explain(s: ScoredWork, taxonomy: Taxonomy) -> dict:
    w = s.work
    reasons = []

    if s.relation:
        r = s.relation
        text = f"{r.label[0].upper()}{r.label[1:]} {r.other_title}"
        if r.note:
            text += f": {r.note}"
        reasons.append({"kind": "relationship", "text": text, "basis": "catalogue" if r.factual else "interpretation",
                        "confidence": r.confidence})

    matched = sorted(s.matched, key=lambda m: (DIMENSION_ORDER.index(m.term.split(":")[0])
                                                if m.term.split(":")[0] in DIMENSION_ORDER else 99, -m.strength))
    for m in matched:
        term = taxonomy.get(m.term)
        dim = taxonomy.dimensions[term.dimension].label
        via = "you asked for" if m.source == "request" else "shared with your reference"
        reasons.append({
            "kind": "match",
            "text": f"{dim}: {_degree(m.strength)} {term.label.lower()} ({via})",
            "term": m.term,
            "definition": term.definition,
            "strength": m.strength,
            "confidence": m.confidence,
            "basis": _basis(m.is_interpretation, m.review_status),
        })

    for note in s.constraint_notes:
        reasons.append({"kind": "constraint", "text": note, "basis": "catalogue"})

    if "novelty" in s.breakdown and w.popularity_tier and w.popularity_tier >= 3:
        reasons.append({"kind": "novelty", "text": "Less widely known, by our editorial popularity estimate.",
                        "basis": "interpretation"})

    caveats = list(s.caveats)
    if s.unmatched:
        labels = [taxonomy.get(t).label.lower() for t in s.unmatched]
        caveats.append(f"Not a match for: {', '.join(labels)}.")

    return {
        "slug": w.slug,
        "title": w.title,
        "original_title": w.original_title,
        "medium": w.medium,
        "year": w.year,
        "creators": w.creators,
        "length": _length_text(w),
        "summary": w.summary,
        "headline": _headline(s, taxonomy),
        "reasons": reasons,
        "caveats": caveats,
        "score": s.score,
        "score_breakdown": s.breakdown,
    }


def _length_text(w) -> str | None:
    approx = "~" if w.length_is_estimate else ""
    if w.runtime_minutes:
        return f"{approx}{w.runtime_minutes} min"
    if w.playtime_hours:
        return f"{approx}{w.playtime_hours:g} h"
    return None


def _headline(s: ScoredWork, taxonomy: Taxonomy) -> str:
    """One sentence built from the strongest non-genre matches."""
    top = [m for m in sorted(s.matched, key=lambda m: -m.strength * m.weight) if not m.term.startswith("genre:")][:3]
    if s.relation and s.relation.factual:
        lead = f"{s.relation.label[0].upper()}{s.relation.label[1:]} {s.relation.other_title}"
        if top:
            return lead + "; " + ", ".join(taxonomy.get(m.term).label.lower() for m in top) + "."
        return lead + "."
    if not top:
        return "Matches your search terms." if s.breakdown.get("keyword_match") else "A broad match for your request."
    labels = [taxonomy.get(m.term).label.lower() for m in top]
    if len(labels) == 1:
        return f"{labels[0].capitalize()}."
    return f"{', '.join(labels[:-1]).capitalize()} and {labels[-1]}."
