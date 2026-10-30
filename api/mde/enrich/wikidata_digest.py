# ruff: noqa: E501, E731
"""One compact fact record per work from its Wikidata entity (CC0): ratings, length, episodes, credits, awards, series, ids.

    python -m mde.enrich.wikidata_digest            fetch what is missing (resumable); writes data/work-facts/wikidata-digest.jsonl
    python -m mde.enrich.wikidata_digest --labels   then fetch the labels of the linked items the digest refers to most (ratings, awards...)

Entity JSON is 100 to 300 KB; only the fields below are kept. Linked items stay as QIDs here and are named by the labels file.
"""

from __future__ import annotations

import argparse
import collections

from mde.enrich import pool
from mde.enrich.worklist import FACTS, worklist

ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{}.json"
DIGEST = FACTS / "wikidata-digest.jsonl"
LABELS = FACTS / "wikidata-labels.jsonl"

# entity-valued properties kept as QID lists (limit per property)
LISTS = {
    "P136": ("genre", 8),
    "P161": ("cast", 14),
    "P57": ("director", 4),
    "P58": ("writer", 4),
    "P86": ("composer", 3),
    "P162": ("producer", 4),
    "P344": ("cinematographer", 2),
    "P170": ("creator", 4),
    "P50": ("author", 3),
    "P178": ("developer", 4),
    "P123": ("publisher", 4),
    "P272": ("company", 4),
    "P449": ("network", 3),
    "P750": ("distributor", 3),
    "P166": ("award", 12),
    "P1411": ("nominated", 12),
    "P144": ("based_on", 3),
    "P8345": ("franchise", 3),
    "P840": ("setting", 4),
    "P921": ("subject", 6),
    "P400": ("platform", 12),
    "P495": ("origin", 4),
    "P364": ("language", 2),
    "P1657": ("mpaa", 1),
    "P852": ("esrb", 1),
    "P908": ("pegi", 1),
    "P2629": ("bbfc", 1),
    "P1981": ("fsk", 1),
    "P674": ("character", 8),
    "P1431": ("showrunner", 3),
    "P2093": ("n/a", 0),
}
SINGLE = {"P1113": "episodes", "P2437": "seasons", "P1104": "pages", "P1082": "population"}
QTY = {"P2047": "duration", "P2142": "box_office", "P2769": "budget"}
IDS = {
    "P345": "imdb",
    "P4947": "tmdb_movie",
    "P4983": "tmdb_tv",
    "P1733": "steam",
    "P436": "musicbrainz_rg",
    "P648": "openlibrary",
    "P2207": "spotify_album",
    "P2281": "apple_music_album",
    "P1258": "rotten_tomatoes",
    "P1712": "metacritic",
    "P6127": "letterboxd",
    "P5749": "amazon",
    "P2002": "twitter",
    "P856": "website",
    "P9751": "gog",
    "P8310": "epic",
}


def _vals(claims: dict, prop: str):
    for c in claims.get(prop, []):
        if c.get("rank") == "deprecated":
            continue
        dv = (c.get("mainsnak") or {}).get("datavalue")
        if dv:
            yield c, dv["value"]


def _qid(v) -> str | None:
    return v.get("id") if isinstance(v, dict) and "id" in v else None


def digest(entity: dict) -> dict:
    cl = entity.get("claims", {})
    out: dict = {
        "qid": entity.get("id"),
        "label": (entity.get("labels", {}).get("en") or {}).get("value"),
        "description": (entity.get("descriptions", {}).get("en") or {}).get("value"),
        "enwiki": (entity.get("sitelinks", {}).get("enwiki") or {}).get("title"),
        "sitelinks": len(entity.get("sitelinks", {})),
    }
    for prop, (name, limit) in LISTS.items():
        if not limit:
            continue
        q = [x for _, v in _vals(cl, prop) if (x := _qid(v))]
        if q:
            out[name] = list(dict.fromkeys(q))[:limit]
    for prop, name in SINGLE.items():
        for _, v in _vals(cl, prop):
            try:
                out[name] = int(float(v["amount"]))
            except (KeyError, ValueError, TypeError):
                pass
            break
    for prop, name in QTY.items():
        if prop == "P2142":  # box office keeps its place qualifier (worldwide, a country) so each figure is labelled correctly
            rows = []
            for c, v in _vals(cl, prop):
                try:
                    place = next((x["datavalue"]["value"].get("id") for x in c.get("qualifiers", {}).get("P3005", []) if x.get("datavalue")), None)
                    rows.append({"v": float(v["amount"]), "u": v["unit"].rsplit("/", 1)[-1], "place": place})
                except (KeyError, ValueError, TypeError):
                    pass
            if rows:
                out[name] = rows[:4]
            continue
        for _, v in _vals(cl, prop):
            try:
                out[name] = [float(v["amount"]), v["unit"].rsplit("/", 1)[-1]]
            except (KeyError, ValueError, TypeError):
                pass
            break
    reviews = []
    for c, v in _vals(cl, "P444"):
        by = next((x["datavalue"]["value"].get("id") for x in c.get("qualifiers", {}).get("P447", []) if x.get("datavalue")), None)
        when = next((x["datavalue"]["value"]["time"].lstrip("+")[:10] for x in c.get("qualifiers", {}).get("P585", []) if x.get("datavalue")), None)
        votes = next((x["datavalue"]["value"].get("amount") for x in c.get("qualifiers", {}).get("P7887", []) if x.get("datavalue")), None)
        if isinstance(v, str) and by:
            reviews.append({"v": v, "by": by, "t": when, "n": votes})
    if reviews:
        out["reviews"] = reviews[:6]
    image = next((v for _, v in _vals(cl, "P18") if isinstance(v, str)), None)
    if image:
        out["image"] = image
    dates = []
    for prop in ("P577", "P580", "P582"):
        for _, v in _vals(cl, prop):
            if isinstance(v, dict) and "time" in v:
                dates.append((prop, v["time"].lstrip("+")[:10]))
    if dates:
        out["dates"] = {p: min(d for q, d in dates if q == p) for p in {q for q, _ in dates}}
    ids = {}
    for prop, name in IDS.items():
        for _, v in _vals(cl, prop):
            if isinstance(v, str):
                ids[name] = v
                break
    if ids:
        out["ids"] = ids
    series = []
    for c, v in _vals(cl, "P179"):
        q = _qid(v)
        if q:
            ordinal = next((s["datavalue"]["value"] for s in c.get("qualifiers", {}).get("P1545", []) if s.get("datavalue")), None)
            series.append({"q": q, "n": ordinal})
    if series:
        out["series"] = series[:3]
    return {k: v for k, v in out.items() if v not in (None, [], {})}


def fetch(qid: str) -> dict | None:
    d = pool.get_json(ENTITY.format(qid), timeout=60)
    if not d:
        return None
    e = d["entities"].get(qid) or next(iter(d["entities"].values()))
    return digest(e)


def fetch_labels(limit_per_kind: int = 400) -> None:
    """Names for the linked items that matter most: age-rating classes, platforms, awards and the most-used franchises, series, subjects."""
    have = pool.load(DIGEST)
    use: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for rec in have.values():
        if not rec:
            continue
        for kind in (
            "mpaa",
            "esrb",
            "pegi",
            "bbfc",
            "fsk",
            "platform",
            "award",
            "nominated",
            "franchise",
            "subject",
            "setting",
            "genre",
            "network",
            "based_on",
        ):
            for q in rec.get(kind, []):
                use[kind][q] += 1
        for s in rec.get("series", []):
            use["series"][s["q"]] += 1
    wanted = {}
    for kind, c in use.items():
        n = 10**6 if kind in ("mpaa", "esrb", "pegi", "bbfc", "fsk", "platform") else limit_per_kind
        for q, _ in c.most_common(n):
            wanted[q] = q
    pool.run(wanted.items(), lambda q: _label(q), LABELS, workers=6)


def _label(qid: str) -> dict | None:
    d = pool.get_json(ENTITY.format(qid), timeout=60)
    if not d:
        return None
    e = d["entities"].get(qid) or next(iter(d["entities"].values()))
    return {"label": (e.get("labels", {}).get("en") or {}).get("value"), "description": (e.get("descriptions", {}).get("en") or {}).get("value")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.labels:
        fetch_labels()
        return
    items = [(w["qid"], w["qid"]) for w in worklist()]
    pool.run(items[: a.limit] if a.limit else items, fetch, DIGEST, workers=6)


if __name__ == "__main__":
    main()
