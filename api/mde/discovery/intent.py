"""Natural-language intent → structured, inspectable constraints and preferences.

`RuleBasedIntentParser` is deterministic and driven by the taxonomy's synonyms. It is the baseline any
LLM-backed parser must beat on the benchmark; both implement `IntentParser`, so they are swappable.
Every interpretation the parser makes is recorded in `Intent.notes` so the UI can show its reading.
"""

from __future__ import annotations

import re
from functools import lru_cache
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Protocol

from mde.taxonomy import Taxonomy


@dataclass
class Preference:
    term: str          # taxonomy key, e.g. "mood:contemplative"
    weight: float
    phrase: str        # the words that triggered it


@dataclass
class Avoidance:
    term: str
    hard: bool         # hard: exclude above `threshold`; soft: penalise
    threshold: float
    phrase: str


@dataclass
class LengthLimit:
    max_minutes: int
    hard: bool
    phrase: str
    per_medium: dict[str, int] = field(default_factory=dict)  # vague limits ("short") mean different things per medium

    def for_medium(self, medium: str) -> int:
        return self.per_medium.get(medium, self.max_minutes)


@dataclass
class Intent:
    query: str
    media: list[str] = field(default_factory=list)            # empty = any medium
    excluded_media: list[str] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    avoid: list[Avoidance] = field(default_factory=list)
    length: LengthLimit | None = None
    languages: list[str] = field(default_factory=list)        # original language, hard
    excluded_languages: list[str] = field(default_factory=list)
    year_min: int | None = None
    year_max: int | None = None
    year_hard: bool = True
    novelty: str | None = None                                 # "obscure" | "popular" | None
    reference_phrase: str | None = None                        # "like <X>" as written
    reference_slug: str | None = None                          # the catalogue work it resolved to
    reference_other_medium: bool = False
    keywords: list[str] = field(default_factory=list)          # leftovers for full-text search
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class IntentParser(Protocol):
    name: str

    def parse(self, query: str) -> Intent: ...


# ------------------------------------------------------------------------------------------ lexicons

MEDIUM_WORDS = {
    "film": ["film", "films", "movie", "movies", "cinema", "flick"],
    "book": ["book", "books", "novel", "novels", "novella", "novellas", "something to read", "a read", "reading"],
    "game": ["game", "games", "video game", "video games", "videogame", "something to play", "to play", "gaming"],
    "album": ["album", "albums", "record", "records", "music", "something to listen to", "listen to", "listening"],
    "series": ["tv show", "tv shows", "tv series", "series", "show to watch", "miniseries", "mini-series", "limited series",
               "web series", "k-drama", "k-dramas", "kdrama", "kdramas", "to binge", "binge-watch", "binge watch",
               "something to binge"],
}
WATCH_WORDS = ["to watch", "watch tonight", "something to watch", "watch"]  # → screen media

LANGUAGE_WORDS = {
    "japanese": "ja", "korean": "ko", "french": "fr", "german": "de", "italian": "it", "russian": "ru",
    "polish": "pl", "spanish": "es", "english": "en", "english-language": "en", "belarusian": "be", "finnish": "fi",
    "hindi": "hi", "tamil": "ta", "telugu": "te", "malayalam": "ml", "bengali": "bn", "kannada": "kn",
    "marathi": "mr", "punjabi": "pa", "urdu": "ur", "mandarin": "zh", "chinese": "zh", "cantonese": "yue",
    "portuguese": "pt", "swedish": "sv", "danish": "da", "norwegian": "no", "persian": "fa", "farsi": "fa",
    "arabic": "ar", "icelandic": "is", "indonesian": "id", "dutch": "nl", "hebrew": "he",
}
# Words that imply an original language but also mean something else (a genre or medium), so they are not consumed.
LANGUAGE_HINTS = {
    "k-pop": "ko", "kpop": "ko", "k-drama": "ko", "kdrama": "ko", "k-dramas": "ko", "kdramas": "ko",
    "j-pop": "ja", "anime": "ja", "manga": "ja", "bollywood": "hi", "tollywood": "te", "kollywood": "ta",
    "mollywood": "ml",
}
NON_ENGLISH = ["foreign language", "foreign-language", "non-english", "not in english", "subtitled", "world cinema",
               "international"]

NUMBER_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "ninety": 90, "forty": 40, "thirty": 30, "twenty": 20, "fifty": 50, "sixty": 60}

LENGTH_RE = re.compile(
    r"\b(?P<cue>under|less than|no more than|at most|max(?:imum)?(?: of)?|shorter than|within|up to|below|no longer than)\s+"
    r"(?P<num>\d+(?:\.\d+)?|an?|one|two|three|four|five|six|twenty|thirty|forty|fifty|sixty|ninety)\s*"
    r"(?P<half>and a half\s+)?(?P<unit>hours?|hrs?|h|minutes?|mins?|m)\b"
)
SOFT_CUES = ["ideally", "preferably", "if possible", "roughly", "around", "or so", "-ish", "ish", "would be nice",
             "would be great", "would be good", "if it can be", "not essential", "doesn't have to be", "bonus"]
HARD_CUES = ["must", "strictly", "has to be", "need it", "absolutely", "at most", "no more than", "no longer than"]
# Vague length words → soft limits per medium, in minutes.
VAGUE_LENGTHS = {
    "a weekend": {"film": 300, "game": 900, "album": 180, "book": 900, "series": 900},
    "one weekend": {"film": 300, "game": 900, "album": 180, "book": 900, "series": 900},
    "one evening": {"film": 150, "game": 240, "album": 90, "book": 300, "series": 180},
    "an evening": {"film": 150, "game": 240, "album": 90, "book": 300, "series": 180},
    "one sitting": {"film": 150, "game": 240, "album": 90, "book": 240, "series": 150},
    "short evening": {"film": 110, "game": 180, "album": 60, "book": 180, "series": 120},
    "something short": {"film": 100, "game": 240, "album": 45, "book": 240, "series": 300},
    "short": {"film": 100, "game": 240, "album": 45, "book": 240, "series": 300},
    "quick": {"film": 100, "game": 180, "album": 45, "book": 180, "series": 240},
    "bite-sized": {"film": 60, "game": 120, "album": 30, "book": 120, "series": 120},
}

OBSCURE_CUES = ["not something obvious", "not obvious", "nothing obvious", "underrated", "hidden gem", "hidden gems",
                "lesser-known", "lesser known", "overlooked", "obscure", "deep cut", "not mainstream",
                "everyone recommends", "haven't heard of", "off the beaten", "under the radar", "little-known",
                "little known", "not the usual"]
POPULAR_CUES = ["popular", "crowd-pleaser", "crowd pleaser", "blockbuster", "mainstream", "well-known", "well known",
                "everyone has seen", "must-see", "must see", "essential"]

REFERENCE_CUES = ["similar to", "something like", "anything like", "more like", "in the vein of", "reminds me of",
                  "same vibe as", "same feeling as", "if i loved", "if i liked", "if you loved", "if you liked",
                  "fans of", "fan of", "i loved", "i liked", "i enjoyed", "like"]
OTHER_MEDIUM_CUES = ["different medium", "another medium", "other medium", "not the same medium", "different format",
                     "in another format", "but not a", "other than a"]

STRICT_NEGATION = ["no", "without", "avoid", "avoiding", "nothing", "zero", "free of", "none", "not", "don't want",
                   "do not want", "skip", "never", "please no", "can't handle", "cannot handle", "hate"]
GENTLE_NEGATION = ["very little", "little", "minimal", "not too", "not overly", "not much", "light on", "low on",
                   "not a lot of", "limited", "too much", "too many", "too"]

INTENSIFIERS = {"very": 1.3, "really": 1.3, "deeply": 1.3, "truly": 1.2, "extremely": 1.4, "lots of": 1.3,
                "strong": 1.3, "ambitious": 1.2, "real": 1.1, "properly": 1.2}
SOFTENERS = {"a bit": 0.6, "slightly": 0.6, "somewhat": 0.6, "a little": 0.6, "a touch of": 0.6, "some": 0.8,
             "maybe": 0.6, "ideally": 0.8}

STOPWORDS = frozenset("""
a an the and or but if i me my we you your it its is are was be been being to of in on for with at by from as
that this these those something anything some any want wanted would like love loved need looking look find
give recommend recommendation please tonight evening today really very just about into than what which who
whom whose there their them they then so not no can could should might may maybe ideally want'd i'm im i've
ive also kind sort bit lot lots more most much one ones get got have has had do does did make makes made feel
feeling mood vibe something's thing things stuff good great nice after before questions question story
stories recommends recommend everyone people ambitious strong real deep lot
finish finished binge binged through will watching reading playing listening start show shows
""".split())

DECADE_RE = re.compile(r"\b(?:the\s+)?(?:(19|20)(\d)0s|'?(\d)0s)\b")
BEFORE_RE = re.compile(r"\b(?:before|pre|older than|prior to)\s+((?:19|20)\d\d)\b")
AFTER_RE = re.compile(r"\b(?:after|since|post|newer than|from)\s+((?:19|20)\d\d)\b")
CURRENT_YEAR = 2026

CLAUSE_SPLIT_RE = re.compile(r"[,.;!?]|\s(?:but|though|although|however|while)\s")


@lru_cache(maxsize=None)   # ~700 synonyms outgrow re's own cache; compile each once
def _phrase_re(phrase: str, plural: bool = False) -> re.Pattern:
    # Whole-phrase match; hyphens count as word characters so "world-class" never matches "class".
    suffix = r"(?:s|es)?" if plural and phrase[-1].isalpha() else ""
    return re.compile(r"(?<![\w-])" + re.escape(phrase) + suffix + r"(?![\w-])")


def _contains(text: str, phrase: str) -> bool:
    return _phrase_re(phrase).search(text) is not None


class RuleBasedIntentParser:
    name = "rules-v1"

    def __init__(self, taxonomy: Taxonomy, resolve_title: Callable[[str], str | None] | None = None):
        """`resolve_title` maps a title as typed to a work slug, or None. Without it, references are ignored."""
        self.taxonomy = taxonomy
        self.resolve_title = resolve_title or (lambda _: None)
        self._synonyms: list[tuple[str, str, re.Pattern]] = sorted(
            ((syn, t.key, _phrase_re(syn, plural=True)) for t in taxonomy.terms.values() for syn in t.synonyms),
            key=lambda x: -len(x[0]),
        )

    # -------------------------------------------------------------------------------- entry point
    def parse(self, query: str) -> Intent:
        intent = Intent(query=query)
        text = " " + re.sub(r"\s+", " ", query.lower().replace("’", "'")).strip() + " "

        text = self._extract_reference(text, intent)
        text = self._extract_novelty(text, intent)
        text = self._extract_length(text, intent)
        text = self._extract_media(text, intent)
        text = self._extract_language(text, intent)
        text = self._extract_years(text, intent)
        text = self._extract_terms(text, intent)
        intent.keywords = [w for w in re.findall(r"[a-z][a-z-]{2,}(?!')", text) if w not in STOPWORDS and w not in INTENSIFIERS]
        if intent.keywords:
            intent.notes.append(f"Also searching titles and descriptions for: {', '.join(intent.keywords)}.")
        return intent

    # -------------------------------------------------------------------------------- pieces
    def _extract_reference(self, text: str, intent: Intent) -> str:
        quoted = re.search(r"[\"“]([^\"”]{2,80})[\"”]", text)
        if quoted:
            phrase = quoted.group(1).strip()
            slug = self.resolve_title(phrase)
            intent.reference_phrase = phrase
            intent.reference_slug = slug
            text = text.replace(quoted.group(0), " ")
            if slug is None:
                intent.notes.append(f"Couldn't find '{phrase}' in the catalogue.")
        else:
            for cue in REFERENCE_CUES:
                for m in _phrase_re(cue).finditer(text):
                    words = text[m.end():].split()[:8]
                    # Longest run of words after the cue that names a catalogue work.
                    for n in range(len(words), 0, -1):
                        phrase = " ".join(words[:n]).strip(",.;!?")
                        slug = self.resolve_title(phrase)
                        if slug:
                            intent.reference_phrase, intent.reference_slug = phrase, slug
                            span = re.compile(re.escape(cue) + r"\s+" + r"\s+".join(re.escape(w) for w in words[:n]))
                            text = span.sub(" ", text, count=1)
                            break
                    if intent.reference_slug:
                        break
                if intent.reference_slug:
                    break
        if intent.reference_slug:
            intent.notes.append(f"Using '{intent.reference_phrase}' as a reference point.")
            if any(_contains(text, c) for c in OTHER_MEDIUM_CUES):
                intent.reference_other_medium = True
                intent.notes.append("Looking in other media than the reference.")
                for c in OTHER_MEDIUM_CUES:
                    text = _phrase_re(c).sub(" ", text)
        return text

    def _extract_novelty(self, text: str, intent: Intent) -> str:
        for cue in OBSCURE_CUES:
            if _contains(text, cue):
                intent.novelty = "obscure"
                intent.notes.append(f"'{cue}': favouring less widely known works.")
                text = _phrase_re(cue).sub(" ", text)
                return text
        for cue in POPULAR_CUES:
            if _contains(text, cue):
                intent.novelty = "popular"
                intent.notes.append(f"'{cue}': favouring widely known works.")
                text = _phrase_re(cue).sub(" ", text)
                return text
        return text

    def _extract_length(self, text: str, intent: Intent) -> str:
        m = LENGTH_RE.search(text)
        if m:
            raw = m.group("num")
            num = float(raw) if raw[0].isdigit() else NUMBER_WORDS[raw]
            if m.group("half"):
                num += 0.5
            minutes = num * 60 if m.group("unit").startswith("h") else num
            window = text[max(0, m.start() - 30): m.end() + 25]
            hard = not any(_contains(window, c) or c in window for c in SOFT_CUES)
            if any(_contains(window, c) for c in HARD_CUES):
                hard = True
            intent.length = LengthLimit(round(minutes), hard, m.group(0).strip())
            kind = "a firm limit" if hard else "a preference, not a cut-off"
            intent.notes.append(f"'{m.group(0).strip()}': treated as {kind} ({round(minutes)} min).")
            text = text[:m.start()] + " " + text[m.end():]
            for c in SOFT_CUES + HARD_CUES:
                text = _phrase_re(c).sub(" ", text)
            return text
        for w, limits in VAGUE_LENGTHS.items():
            if _contains(text, w):
                intent.length = LengthLimit(limits["film"], False, w, dict(limits))
                intent.notes.append(f"'{w}': preferring roughly {limits['film']} min for films, "
                                    f"{limits['game'] // 60} hours for games, {limits['album']} min for albums.")
                for other in VAGUE_LENGTHS:
                    text = _phrase_re(other).sub(" ", text)
                return text
        return text

    def _extract_media(self, text: str, intent: Intent) -> str:
        found: list[str] = []
        excluded: list[str] = []
        for medium, words in MEDIUM_WORDS.items():
            for w in sorted(words, key=len, reverse=True):
                for m in list(_phrase_re(w).finditer(text)):
                    before = text[max(0, m.start() - 16): m.start()]
                    if re.search(r"(not an?|no|other than an?|except|but not an?|anything but an?)\s*$", before):
                        excluded.append(medium)
                    else:
                        found.append(medium)
                text = _phrase_re(w).sub(" ", text)
        if not found and any(_contains(text, w) for w in WATCH_WORDS):
            found = ["film", "series"]
            intent.notes.append("'watch': limiting to films and series.")
        for w in WATCH_WORDS:
            text = _phrase_re(w).sub(" ", text)
        for phrase in ("across any medium", "across all media", "across media", "any medium", "any format", "any media",
                       "anything at all", "in any form", "any form"):
            text = _phrase_re(phrase).sub(" ", text)
        intent.media = sorted(set(found) - set(excluded))
        intent.excluded_media = sorted(set(excluded))
        return text

    def _extract_language(self, text: str, intent: Intent) -> str:
        for phrase in NON_ENGLISH:
            if _contains(text, phrase):
                intent.excluded_languages = ["en"]
                intent.notes.append(f"'{phrase}': excluding works originally in English.")
                text = _phrase_re(phrase).sub(" ", text)
        for word, code in LANGUAGE_WORDS.items():
            if _contains(text, word):
                intent.languages.append(code)
                text = _phrase_re(word).sub(" ", text)
        original = " " + re.sub(r"\s+", " ", intent.query.lower().replace("’", "'")).strip() + " "
        for word, code in LANGUAGE_HINTS.items():   # read from the whole query: these words may already be consumed
            if _contains(original, word) and code not in intent.languages:
                intent.languages.append(code)
        if intent.languages:
            intent.notes.append(f"Original language: {', '.join(intent.languages)}.")
        return text

    def _extract_years(self, text: str, intent: Intent) -> str:
        if m := DECADE_RE.search(text):
            if m.group(1):
                start = int(m.group(1) + m.group(2) + "0")
            else:
                d = int(m.group(3))
                start = 1900 + d * 10 if d >= 3 else 2000 + d * 10
            intent.year_min, intent.year_max = start, start + 9
            text = text[:m.start()] + " " + text[m.end():]
        if m := BEFORE_RE.search(text):
            intent.year_max = int(m.group(1)) - 1
            text = text[:m.start()] + " " + text[m.end():]
        if m := AFTER_RE.search(text):
            intent.year_min = int(m.group(1)) + (0 if m.group(0).startswith("from") or "since" in m.group(0) else 1)
            text = text[:m.start()] + " " + text[m.end():]
        for w in ("recent", "newer", "latest"):
            if _contains(text, w) and intent.year_min is None:
                intent.year_min, intent.year_hard = CURRENT_YEAR - 10, False
                text = _phrase_re(w).sub(" ", text)
        if intent.year_min or intent.year_max:
            intent.notes.append(f"Release years: {intent.year_min or '…'}–{intent.year_max or '…'}"
                                + ("" if intent.year_hard else " (preference)") + ".")
        return text

    def _extract_terms(self, text: str, intent: Intent) -> str:
        """Match taxonomy phrases clause by clause.

        A negation cue applies to the next matched phrase, and carries over to phrases coordinated with it
        ("no gore or jump scares"), but not past an unrelated word ("not too slow sci-fi" avoids slow, not
        sci-fi).
        """
        prefs: dict[str, Preference] = {}
        avoids: dict[str, Avoidance] = {}
        leftover_parts = []
        for clause in CLAUSE_SPLIT_RE.split(text):
            clause = " " + clause + " "
            matches: list[tuple[int, int, str, str]] = []
            taken = [False] * len(clause)
            for syn, key, pattern in self._synonyms:
                if syn not in clause:   # cheap pre-check: a match needs the literal phrase
                    continue
                for m in pattern.finditer(clause):
                    if any(taken[m.start():m.end()]):
                        continue
                    for i in range(m.start(), m.end()):
                        taken[i] = True
                    matches.append((m.start(), m.end(), syn, key))
            matches.sort()

            prev_end, prev_neg = 0, None
            for start, end, syn, key in matches:
                gap = " " + clause[prev_end:start] + " "
                negation = self._negation_in(gap)
                if negation is None and prev_neg is not None and re.fullmatch(r"\s*(?:,|and|or|nor)\s*(?:(?:any|other)\s+)*", gap):
                    negation = prev_neg
                if negation is not None:
                    hard, threshold = negation
                    is_hard = hard and key.startswith("advisory:")
                    prev = avoids.get(key)
                    if prev is None or (is_hard and not prev.hard):
                        avoids[key] = Avoidance(key, is_hard, threshold, syn)
                else:
                    weight = 1.0
                    for word, w in {**INTENSIFIERS, **SOFTENERS}.items():
                        if re.search(r"(?<![\w-])" + re.escape(word) + r"\s+(?:[\w-]+\s+)?$", gap):
                            weight = w
                            break
                    if key.startswith("genre:"):
                        weight *= 1.2
                    if key not in prefs or prefs[key].weight < weight:
                        prefs[key] = Preference(key, round(weight, 2), syn)
                prev_end, prev_neg = end, negation

            remaining = "".join(" " if t else c for c, t in zip(clause, taken, strict=True))
            leftover_parts.append(self._strip_negations(remaining))

        for key in avoids:  # an avoided term never also counts as wanted
            prefs.pop(key, None)
        intent.preferences = list(prefs.values())
        intent.avoid = list(avoids.values())
        for a in intent.avoid:
            label = self.taxonomy.get(a.term).label.lower()
            if a.hard:
                intent.notes.append(f"Excluding works with notable {label} (intensity ≥ {a.threshold}).")
            else:
                intent.notes.append(f"Ranking down works that are {label}.")
        return " ".join(leftover_parts)

    @staticmethod
    def _negation_in(seg: str) -> tuple[bool, float] | None:
        for cue in sorted(GENTLE_NEGATION, key=len, reverse=True):
            if _contains(seg, cue):
                return (True, 0.6)
        for cue in sorted(STRICT_NEGATION, key=len, reverse=True):
            if _contains(seg, cue):
                return (True, 0.4)
        return None

    @staticmethod
    def _strip_negations(seg: str) -> str:
        for cue in sorted(GENTLE_NEGATION + STRICT_NEGATION, key=len, reverse=True):
            seg = _phrase_re(cue).sub(" ", seg)
        return seg
