"""Wikidata (CC0): identity, dates, runtime, series, box office, published review scores and external IDs.

Matching is conservative: a candidate must be of the right type and its publication year must agree with the
seed (±1). Anything else is reported for editorial review instead of being guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from mde.catalogue.model import normalise_title
from mde.ingest.http import Client

API = "https://www.wikidata.org/w/api.php"
LICENCE = "CC0 1.0"

# Accepted P31 (instance of) values per medium.
TYPES = {
    "film": {"Q11424", "Q24869", "Q29168811", "Q202866", "Q506240", "Q93204", "Q20650540", "Q24862", "Q226730"},
    "series": {"Q5398426", "Q1259759", "Q117467246", "Q63952888", "Q526877", "Q15416", "Q581714", "Q3464665", "Q1366112"},
    "book": {"Q7725634", "Q8261", "Q149537", "Q49084", "Q47461344", "Q571", "Q1279564", "Q112983", "Q725377", "Q8274"},
    "game": {"Q7889", "Q21125433", "Q64170203"},
    "album": {"Q482994", "Q208569", "Q209939", "Q222910", "Q169930", "Q4176708"},
}
UNIT_MINUTES = {"Q7727": 1.0, "Q25235": 60.0, "Q11574": 1 / 60}
CURRENCIES = {"Q4917": "USD", "Q4916": "EUR", "Q25224": "GBP", "Q8146": "JPY", "Q202040": "KRW", "Q80524": "INR",
              "Q1104069": "CAD", "Q259502": "AUD", "Q41044": "RUB", "Q39099": "CNY"}
SCOPES = {"Q13780930": "worldwide", "Q30": "United States", "Q49": "North America", "Q2017699": "US & Canada"}
EXTERNAL_IDS = {"P345": "imdb", "P4947": "tmdb_movie", "P4983": "tmdb_tv", "P1258": "rotten_tomatoes",
                "P6127": "letterboxd", "P1712": "metacritic", "P648": "openlibrary", "P436": "musicbrainz_release_group",
                "P5794": "igdb", "P1733": "steam", "P2002": "twitter"}


@dataclass
class Match:
    qid: str | None
    confidence: float
    reason: str
    candidates: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ pure helpers (unit-tested)

def claim_values(entity: dict, prop: str) -> list[dict]:
    """Main-snak data values for a property, preferred rank first, deprecated dropped."""
    claims = entity.get("claims", {}).get(prop, [])
    ranked = sorted((c for c in claims if c.get("rank") != "deprecated"),
                    key=lambda c: 0 if c.get("rank") == "preferred" else 1)
    return [c for c in ranked if c.get("mainsnak", {}).get("snaktype") == "value"]


def value(claim: dict):
    return claim["mainsnak"]["datavalue"]["value"]


def qualifier_values(claim: dict, prop: str) -> list:
    return [q["datavalue"]["value"] for q in claim.get("qualifiers", {}).get(prop, []) if q.get("snaktype") == "value"]


def year_of(entity: dict, prop: str = "P577") -> int | None:
    years = []
    for c in claim_values(entity, prop):
        m = re.match(r"[+-](\d{4})", value(c)["time"])
        if m:
            years.append(int(m.group(1)))
    return min(years) if years else None


def label_of(entity: dict) -> str:
    """English label, else the language-neutral 'mul' label Wikidata now uses for many names."""
    labels = entity.get("labels", {})
    return (labels.get("en") or labels.get("mul") or {}).get("value", "")


def names_of(entity: dict) -> list[str]:
    aliases = entity.get("aliases", {})
    return [label_of(entity), *(a["value"] for lang in ("en", "mul") for a in aliases.get(lang, []))]


def instance_types(entity: dict) -> set[str]:
    return {value(c)["id"] for c in claim_values(entity, "P31")}


def runtime_minutes(entity: dict) -> int | None:
    for c in claim_values(entity, "P2047"):
        v = value(c)
        unit = v.get("unit", "").rsplit("/", 1)[-1]
        if unit in UNIT_MINUTES:
            return round(float(v["amount"]) * UNIT_MINUTES[unit])
    return None


def parse_score(text: str) -> tuple[float, float] | None:
    """'93%' → (93, 100); '81/100' → (81, 100); '8.1/10' → (8.1, 10)."""
    text = text.strip()
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*%", text):
        return float(m.group(1)), 100.0
    if m := re.fullmatch(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", text):
        return float(m.group(1)), float(m.group(2))
    return None


def review_scores(entity: dict, labels: dict[str, str]) -> list[dict]:
    out = []
    for c in claim_values(entity, "P444"):
        parsed = parse_score(value(c)) if isinstance(value(c), str) else None
        if not parsed:
            continue
        by = [q["id"] for q in qualifier_values(c, "P447")]
        method = [q["id"] for q in qualifier_values(c, "P459")]
        when = [q["time"][1:11] for q in qualifier_values(c, "P585")]
        votes = [q["amount"] for q in qualifier_values(c, "P7887")]
        publisher = labels.get(by[0], by[0]) if by else None
        if not publisher or re.fullmatch(r"Q\d+", publisher):   # no publisher with a name: nobody can weigh the score
            continue
        metric = labels.get(method[0], method[0]) if method else "score"
        out.append({
            "publisher": publisher,
            "metric": "score" if re.fullmatch(r"Q\d+", metric) else metric,
            "value": parsed[0], "scale_max": parsed[1],
            "votes": int(float(votes[0])) if votes else None,
            "as_of": when[0] if when else None,
        })
    # One value per publisher+metric: keep the most recent.
    best: dict[tuple, dict] = {}
    for s in out:
        k = (s["publisher"], s["metric"])
        if k not in best or (s["as_of"] or "") > (best[k]["as_of"] or ""):
            best[k] = s
    return sorted(best.values(), key=lambda s: (s["publisher"], s["metric"]))


def box_office(entity: dict) -> list[dict]:
    rows: dict[str, dict] = {}
    for c in claim_values(entity, "P2142"):
        v = value(c)
        currency = CURRENCIES.get(v.get("unit", "").rsplit("/", 1)[-1])
        if not currency:
            continue
        places = [q["id"] for q in qualifier_values(c, "P3005")]
        scope = SCOPES.get(places[0], "other") if places else "unspecified"
        amount = float(v["amount"])
        if scope not in rows or amount > rows[scope]["amount"]:
            rows[scope] = {"scope": scope, "amount": amount, "currency": currency}
    return sorted(rows.values(), key=lambda r: -r["amount"])


def series(entity: dict) -> list[dict]:
    out = []
    for c in claim_values(entity, "P179"):
        ordinal = qualifier_values(c, "P1545")
        out.append({"qid": value(c)["id"], "position": ordinal[0] if ordinal else None})
    return out


def item_ids(entity: dict, prop: str) -> list[str]:
    return [value(c)["id"] for c in claim_values(entity, prop)]


def external_ids(entity: dict) -> dict[str, str]:
    out = {}
    for prop, name in EXTERNAL_IDS.items():
        vals = claim_values(entity, prop)
        if vals:
            out[name] = value(vals[0])
    return out


def is_exact(entity: dict, titles: list[str]) -> bool:
    return bool({normalise_title(t) for t in titles} & {normalise_title(n) for n in names_of(entity) if n})


def score_candidate(entity: dict, title: str | list[str], medium: str, year: int | None) -> tuple[float, str]:
    """0 means reject. Type must match; year must agree within one; exact title (or a known alternative) earns most."""
    titles = [title] if isinstance(title, str) else title
    if not instance_types(entity) & TYPES[medium]:
        return 0.0, "wrong type"
    y = year_of(entity)
    if year is not None and y is not None and abs(y - year) > 1:
        return 0.0, f"year {y} vs {year}"
    exact = is_exact(entity, titles)
    conf = 0.5 + (0.3 if exact else 0) + (0.2 if y == year else 0.1 if y is not None else 0)
    return round(conf, 2), f"type ok, year {y}, {'exact' if exact else 'partial'} title"


# ------------------------------------------------------------------ fetching

def choose(ents: dict[str, dict], titles: list[str], medium: str, year: int | None) -> list[tuple[float, str, str]]:
    """Candidates scored best first. Ties are broken by item completeness (claim count), which favours the canonical
    work over editions and re-releases. When nothing passes the year check but exactly one candidate has the right
    type and an exact title, it is accepted at 0.6 with the year difference stated (e.g. a game finished years after
    its first episode), and the disagreement is reported as a conflict for review."""
    scored = []
    for q, e in ents.items():
        conf, why = score_candidate(e, titles, medium, year)
        scored.append((conf, len(e.get("claims", {})), q, why))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    if scored and scored[0][0] > 0 and len(scored) > 1 and scored[1][0] == scored[0][0] and scored[1][1] != scored[0][1]:
        conf, _, q, why = scored[0]
        scored[0] = (round(conf + 0.01, 2), scored[0][1], q, f"{why}; tie broken by completeness")
    if (not scored or scored[0][0] < 0.7):
        typed = [(q, e) for q, e in ents.items() if instance_types(e) & TYPES[medium] and is_exact(e, titles)]
        if len(typed) == 1:
            q, e = typed[0]
            scored = [(0.6, 0, q, f"only exact-title match of the right type; year {year_of(e)} differs from {year}")] + \
                     [s for s in scored if s[2] != q]
    return [(c, q, why) for c, _, q, why in scored]


class Wikidata:
    def __init__(self, client: Client):
        self.client = client
        self._labels: dict[str, str] = {}

    def entities(self, ids: list[str], props: str = "claims|labels|aliases|sitelinks|descriptions") -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 50):
            chunk = ids[i:i + 50]
            data = self.client.get_json(API, {"action": "wbgetentities", "ids": "|".join(chunk), "props": props,
                                              "languages": "en|mul", "sitefilter": "enwiki", "format": "json"})
            out.update(data.get("entities", {}))
        return out

    def labels(self, ids: list[str]) -> dict[str, str]:
        missing = sorted(set(ids) - self._labels.keys())
        if missing:
            for q, e in self.entities(missing, props="labels").items():
                self._labels[q] = label_of(e) or q
        return {q: self._labels.get(q, q) for q in ids}

    def _search(self, title: str) -> list[str]:
        found = self.client.get_json(API, {"action": "wbsearchentities", "search": title, "language": "en",
                                           "type": "item", "limit": 12, "format": "json"})
        return [c["id"] for c in found.get("search", [])]

    def _typed_search(self, title: str, medium: str) -> list[str]:
        """Full-text search restricted to the medium's item types, for titles buried under common words (Moon, Columbus)."""
        types = "|".join(f"P31={t}" for t in sorted(TYPES[medium]))
        found = self.client.get_json(API, {"action": "query", "list": "search", "srsearch": f'"{title}" haswbstatement:{types}',
                                           "srlimit": 10, "format": "json"})
        return [h["title"] for h in found.get("query", {}).get("search", []) if h.get("title", "").startswith("Q")]

    def find(self, title: str, medium: str, year: int | None, creator: str | None = None,
             aka: list[str] | None = None) -> tuple[Match, dict | None]:
        titles = [title, *(aka or [])]
        cands: list[str] = []
        for t in titles:
            cands += [q for q in self._search(t) if q not in cands]
        ents = self.entities(cands) if cands else {}
        scored = choose(ents, titles, medium, year)
        if not scored or scored[0][0] < 0.7:
            extra = [q for t in titles for q in self._typed_search(t, medium) if q not in ents]
            if extra:
                ents.update(self.entities(sorted(set(extra))))
                scored = choose(ents, titles, medium, year)
        if not scored:
            return Match(None, 0, "no search results"), None
        summary = [{"qid": q, "label": label_of(ents[q]) or None,
                    "description": ents[q].get("descriptions", {}).get("en", {}).get("value"),
                    "confidence": c, "reason": why} for c, q, why in scored[:5]]
        best = scored[0]
        if best[0] < 0.6:
            return Match(None, best[0], "no confident match", summary), None
        if len(scored) > 1 and scored[1][0] == best[0]:
            return Match(None, best[0], "ambiguous: two equally good candidates", summary), None
        return Match(best[1], best[0], best[2], summary), ents[best[1]]

    def enrich(self, work: dict) -> dict:
        match, entity = self.find(work["title"], work["medium"], work.get("year"), aka=(work.get("attributes") or {}).get("aka"))
        if entity is None:
            return {"match": None, "reason": match.reason, "candidates": match.candidates}
        refs = []
        for c in claim_values(entity, "P444"):
            refs += [q["id"] for q in qualifier_values(c, "P447")] + [q["id"] for q in qualifier_values(c, "P459")]
        ser = series(entity)
        refs += [s["qid"] for s in ser]
        labels = self.labels(refs) if refs else {}
        facts = {}
        if (y := year_of(entity)) is not None:
            facts["release_year"] = y
        # Album durations on Wikidata often include bonus tracks; MusicBrainz track lists are used for albums instead.
        if work["medium"] == "film" and (rt := runtime_minutes(entity)) is not None:
            facts["runtime_minutes"] = rt
        images = []
        for c in claim_values(entity, "P18")[:1]:
            images.append({"kind": "still", "commons_file": value(c)})
        enwiki = entity.get("sitelinks", {}).get("enwiki", {}).get("title")
        return {
            "match": {"qid": match.qid, "confidence": match.confidence, "reason": match.reason},
            "facts": facts,
            "ids": external_ids(entity),
            "scores": review_scores(entity, labels),
            "box_office": box_office(entity),
            "series": [{"qid": s["qid"], "name": labels.get(s["qid"], s["qid"]), "position": s["position"]} for s in ser],
            "follows": item_ids(entity, "P155"),
            "followed_by": item_ids(entity, "P156"),
            "based_on": item_ids(entity, "P144"),
            "images": images,
            "wikipedia": f"https://en.wikipedia.org/wiki/{enwiki.replace(' ', '_')}" if enwiki else None,
        }
