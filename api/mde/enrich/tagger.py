# ruff: noqa: E501, E731
"""Derives tags for an imported work from open evidence, with a rule set small enough to read (lexicon.py).

Evidence: the work's Wikidata description, Wikipedia lead, TVmaze / Steam / Open Library descriptions, genres and subjects from those
sources, MusicBrainz tags, plus the genre tags it already has. Strength is how much of that evidence agrees:

    from text          0.35 + 0.25 per distinct matching rule (weak, generic rules count half), capped at 0.95; one weak hit is not enough
    from genre priors  the typical feel of the genre (lexicon.PRIORS), modest by design; agreeing with text adds 0.1
    pacing             also from runtime for films (long and dialogue-led reads slow, short and action-led reads brisk)

Nothing here is a human judgement: every tag is ai-assisted and unreviewed, like the pilot's, and the work page says so.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from mde.enrich.lexicon import PRIORS, TEXT

TAXONOMY = Path(__file__).resolve().parent.parent / "taxonomy" / "taxonomy.json"
WEAK = {
    r"\bfamily\b",
    r"\bfather\b",
    r"\bmother\b",
    r"\bsons?\b",
    r"\bbrothers?\b",
    r"\bsisters?\b",
    r"\bparents?\b",
    r"\bfriends\b",
    r"\bwar\b",
    r"\bdeath\b",
    r"\bdaughter",
    r"\brelationship",
    r"\bcouple\b",
    r"\bocean",
    r"\banimals?\b",
    r"\bscience\b",
    r"\bcareer",
    r"\bfame\b",
    r"\buniverse\b",
    r"\bplanets?\b",
    r"\bspace\b",
    r"\bmountain",
    r"\bforest",
    r"\bfun\b",
    r"\bkids?\b",
    r"\bteens?\b",
    r"\bpolice\b",
    r"\bcourt(room)?\b",
    r"\bsoldiers?\b",
    r"\barmy\b",
    r"\bremember",
    r"\bmystery\b",
    r"\bmemor(y|ies)\b",
    r"\bhero(es|ic|ine)?\b",
    r"\bnature\b",
    r"\bsolve",
    r"\bdiscover(y|ies|s)\b",
    r"\bfestival",
    r"\bbrave",
    r"\brescue",
    r"\bchased?\b",
    r"\bgrand\b",
    r"\bquiet\b",
    r"\bminimal\b",
    r"\bcomic\b",
    r"\bdeath",
    r"\bspirits?\b",
    r"\bgods?\b",
    r"\bcomed(y|ic|ian)",
    r"\bhumou?r",
    r"\bromance",
    r"\bromantic",
    r"\bthriller",
    r"\bhorror",
    r"\bwealth(y)?\b",
    r"\bconsequences",
    r"\bconversation",
}

# subgenres the text can add (genre slug -> patterns), only when the taxonomy lets the genre apply to the medium
GENRE_TEXT: dict[str, list[str]] = {
    "cyberpunk": [r"cyberpunk"],
    "neo-noir": [r"neo-?noir", r"film noir"],
    "slasher": [r"\bslasher"],
    "heist": [r"\bheist"],
    "time-travel": [r"time[- ]travel", r"time machine", r"time loop"],
    "zombie-horror": [r"\bzombie"],
    "post-apocalyptic": [r"post-?apocalyp"],
    "space-opera": [r"space opera"],
    "courtroom": [r"courtroom", r"\btrial of\b"],
    "whodunit": [r"whodunit|whodunnit"],
    "coming-of-age": [r"coming[- ]of[- ]age"],
    "found-footage": [r"found[- ]footage"],
    "mockumentary": [r"mockumentary"],
    "biography": [r"\bbiograph", r"\bbiopic", r"based on the (life|true story)"],
    "true-crime": [r"true[- ]crime"],
    "police-procedural": [r"police procedural", r"procedural"],
    "romantic-comedy": [r"romantic comedy|rom-?com"],
    "dark-comedy-crime": [r"crime comedy"],
    "psychological-thriller": [r"psychological thriller"],
    "psychological-horror": [r"psychological horror"],
    "supernatural-horror": [r"supernatural horror"],
    "folk-horror": [r"folk horror"],
    "gothic-horror": [r"gothic"],
    "body-horror-genre": [r"body horror"],
    "creature-feature": [r"creature feature"],
    "disaster": [r"disaster film|disaster movie"],
    "martial-arts": [r"martial arts?|kung fu"],
    "wuxia": [r"wuxia"],
    "swashbuckler": [r"swashbuckl"],
    "road-trip": [r"road (trip|movie)"],
    "buddy-comedy": [r"buddy (comedy|film|cop)"],
    "sitcom": [r"situation comedy|sitcom"],
    "anime": [r"\banime\b"],
    "stop-motion": [r"stop[- ]motion"],
    "computer-animation": [r"computer[- ]animated"],
    "adult-animation": [r"adult animated"],
    "holiday-movie": [r"christmas (film|movie|special)"],
    "sports-drama": [r"sports (drama|film)"],
    "underdog-story": [r"underdog"],
    "period-drama": [r"period (drama|piece)"],
    "historical-epic": [r"historical epic"],
    "war": [r"\bwar (film|movie|drama)"],
    "superhero": [r"superhero"],
    "spy-thriller": [r"spy (thriller|film|series)|espionage"],
    "political-thriller": [r"political thriller"],
    "survival-thriller": [r"survival thriller"],
    "revenge-thriller": [r"revenge thriller"],
    "dystopian": [r"dystopi"],
    "artificial-intelligence": [r"artificial intelligence|\bAI\b"],
    "alien-encounter": [r"alien invasion|first contact"],
    "urban-fantasy": [r"urban fantasy"],
    "dark-fantasy": [r"dark fantasy"],
    "high-fantasy": [r"high fantasy|epic fantasy"],
    "fairy-tale": [r"fairy[- ]?tale"],
    "cozy-mystery": [r"cozy mystery|cosy mystery"],
    "detective-story": [r"detective"],
    "gangster": [r"gangster|mafia|organi[sz]ed crime"],
    "family-drama": [r"family drama"],
    "melodrama": [r"melodrama"],
    "musical": [r"\bmusical\b"],
    "nature-documentary": [r"nature documentary|wildlife documentary"],
    "sports-documentary": [r"sports documentary"],
    "soulslike": [r"soulslike|souls-like"],
    "roguelike": [r"roguelike|roguelite"],
    "metroidvania": [r"metroidvania"],
    "farming-sim": [r"farming sim"],
    "deckbuilder": [r"deck[- ]?build"],
    "cozy-game": [r"cozy game|cosy game|wholesome game"],
    "survival-horror": [r"survival horror"],
    "sandbox-survival": [r"survival (crafting|sandbox)|crafting and survival"],
    "first-person-shooter": [r"first-person shooter"],
    "third-person-shooter": [r"third-person shooter"],
    "4x-strategy": [r"\b4x\b"],
    "tactics": [r"tactical (rpg|strategy|turn-based)"],
    "action-roguelite": [r"action roguelite"],
    "platformer": [r"platformer|platform game"],
    "puzzle-platformer": [r"puzzle[- ]platformer"],
    "workplace-drama": [r"medical drama", r"legal drama", r"workplace (drama|comedy)", r"hospital drama"],
    "memoir": [r"\bmemoir"],
    "graphic-novel": [r"graphic novel"],
    "short-stories": [r"short stor(y|ies) collection|collection of short stories"],
    "classic-literature": [r"classic (novel|literature)"],
}


@lru_cache(maxsize=1)
def taxonomy() -> dict[str, dict]:
    return {f"{t['dimension']}:{t['slug']}": t for t in json.loads(TAXONOMY.read_text())["terms"]}


def applies(term: str, medium: str) -> bool:
    t = taxonomy().get(term)
    return bool(t) and ("*" in t["applies_to"] or medium in t["applies_to"])


CLEAN = [
    (re.compile(r"\bUnited Kingdom\b", re.I), "UK"),
    (re.compile(r"\bUnited States\b", re.I), "US"),
    (
        re.compile(r"\b(Imperial|Crown|Empire|Kingdom|Royal) (Records|Pictures|Studios|Films|Entertainment|Theatre|Theater|Cinema|Airlines)\b", re.I),
        "studio",
    ),
    (re.compile(r"\b(released|recorded|produced|published|developed|distributed) (by|at|in|on)\b[^.]*\.", re.I), " "),
]  # production notes are not about the story
# world and mythic terms need a genre that makes them plausible, or two separate pieces of evidence
GATES = {
    "world:rich-worldbuilding": {
        "fantasy",
        "science-fiction",
        "high-fantasy",
        "dark-fantasy",
        "space-opera",
        "rpg",
        "crpg",
        "jrpg",
        "action-rpg",
        "cyberpunk",
        "dystopian",
        "mecha",
        "anime",
    },
    "world:mythic": {"fantasy", "high-fantasy", "mythic-fantasy", "dark-fantasy", "fairy-tale", "action-adventure", "rpg", "jrpg"},
    "world:space-setting": {"science-fiction", "space-opera", "hard-science-fiction", "alien-encounter"},
    "world:open-world": {"rpg", "action-adventure", "sandbox-survival", "open-world-racing", "crpg", "action-rpg"},
}
ALBUM_DIMS = {"mood", "style", "complexity", "narrative"}

_TEXT = {term: [(re.compile(rx.pattern, rx.flags), 0.5 if rx.pattern in WEAK else 1.0) for rx, _ in pats] for term, pats in TEXT.items()}
_GENRE = {slug: [re.compile(p, re.I) for p in pats] for slug, pats in GENRE_TEXT.items()}


def tag(medium: str, text: str, genres: list[str], runtime: int | None = None, year: int | None = None, keep: int = 14) -> dict[str, float]:
    """Terms (excluding the genres already on the work) with strengths, for a work with this evidence."""
    out: dict[str, float] = {}
    for rx, repl in CLEAN:
        text = rx.sub(repl, text)
    if text:
        for term, pats in _TEXT.items():
            if not applies(term, medium) or (medium == "album" and term.split(":")[0] not in ALBUM_DIMS and term.split(":")[0] != "theme"):
                continue
            hit = sum(w for rx, w in pats if rx.search(text))
            need = 2.0 if (medium == "album" and term.startswith("theme:")) or (term in GATES and not (set(genres) & GATES[term])) else 1.0
            if hit >= need:
                out[term] = min(0.95, 0.35 + 0.25 * min(hit, 2.4))
    for g in genres:
        for term, s in PRIORS.get(g, []):
            if applies(term, medium):
                out[term] = min(0.95, out[term] + 0.1) if term in out else s
    if medium == "film" and runtime and "pacing:slow-burn" not in out and "pacing:brisk" not in out:
        action = any(g in genres for g in ("action", "thriller", "martial-arts", "disaster", "heist"))
        if runtime >= 150 and not action and any(g in genres for g in ("drama", "historical", "biography", "period-drama", "character-study")):
            out["pacing:slow-burn"] = 0.45
        elif runtime <= 100 and action:
            out["pacing:brisk"] = 0.55
    ranked = sorted(out.items(), key=lambda kv: (-kv[1], kv[0]))
    return {k: round(v, 2) for k, v in ranked[:keep] if v >= 0.4}


def subgenres(medium: str, text: str, have: set[str], limit: int = 3) -> dict[str, float]:
    """Genre terms the description names outright (a slasher, a heist, a roguelike) that the work does not carry yet."""
    out: dict[str, float] = {}
    for slug, pats in _GENRE.items():
        term = f"genre:{slug}"
        if term in have or not applies(term, medium):
            continue
        if any(p.search(text) for p in pats):
            out[term] = 0.7
    return dict(list(out.items())[:limit])


@lru_cache(maxsize=1)
def _genre_names() -> dict[str, str]:
    """normalised genre label, slug or synonym -> genre term"""
    out: dict[str, str] = {}
    for key, t in taxonomy().items():
        if t["dimension"] != "genre":
            continue
        for name in [t["slug"], t["label"], *t.get("synonyms", [])]:
            out.setdefault(re.sub(r"[^a-z0-9]+", " ", name.lower()).strip(), key)
    return out


def genres_from_tags(medium: str, tags: list[str], have: set[str], limit: int = 4) -> dict[str, float]:
    """Genre terms named by a source's own genres, tags or subjects (Steam 'RPG', MusicBrainz 'art rock', Open Library 'Dystopias')."""
    names, out = _genre_names(), {}
    for tag_ in tags:
        norm = re.sub(r"[^a-z0-9]+", " ", tag_.lower()).strip()
        for cand in (norm, norm.rstrip("s")):
            term = names.get(cand)
            if term and term not in have and term not in out and applies(term, medium):
                out[term] = 0.7
                break
    return dict(list(out.items())[:limit])
