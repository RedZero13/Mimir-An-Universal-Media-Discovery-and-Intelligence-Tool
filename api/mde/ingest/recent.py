"""Finds recent works (2025 onwards) on Wikidata (CC0) and writes them as a reviewable seed file, seed/recent.json.

    python -m mde.ingest.recent                 # discover, rank by how widely each work is covered, write the seed
    python -m mde.ingest.recent --offline       # rebuild from the HTTP cache only

How it picks: a Wikidata SPARQL query per medium and year for works of the medium's item types whose own publication date is
in range and not in the future, ranked by the number of Wikipedia language editions that cover them (a fair proxy for how
widely known a work is), up to a cap per medium and year.
Nothing is invented: titles, years, credits, countries and genres are Wikidata's; the summary is Wikidata's one-line
description plus the cast. No parents' guide is claimed. Works already in the catalogue are skipped.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from mde.catalogue.model import normalise_title, slugify
from mde.catalogue.seedfiles import read_seed
from mde.ingest.http import Client
from mde.ingest.wikidata import API, TYPES, Wikidata, claim_values, label_of, runtime_minutes, value

OUT = Path(__file__).parent.parent / "seed" / "recent.json"
TAXONOMY = Path(__file__).parent.parent / "taxonomy" / "taxonomy.json"
YEARS = (2025, 2026)
CAPS = {"film": 140, "series": 90, "game": 70, "album": 70, "book": 70}   # per year
MIN_SITELINKS = {"film": 6, "series": 5, "game": 5, "album": 4, "book": 4}
GENRE_ALIASES = {
    "action film": "action", "drama film": "drama", "comedy film": "comedy", "horror film": "horror", "thriller film": "thriller",
    "science fiction film": "science-fiction", "romance film": "romance", "romantic film": "romance", "animated film": "animation",
    "adventure film": "adventure", "fantasy film": "fantasy", "crime film": "crime", "musical film": "musical",
    "biographical film": "biography", "war film": "war", "documentary film": "documentary", "mystery film": "mystery",
    "historical film": "historical", "family film": "family", "superhero film": "superhero", "sports film": "sports",
    "romantic comedy film": "romantic-comedy", "comedy drama": "dramedy", "action-adventure game": "action-adventure",
    "role-playing video game": "rpg", "action role-playing game": "action-rpg", "first-person shooter": "first-person-shooter",
    "platform game": "platformer", "puzzle video game": "puzzle", "strategy video game": "strategy", "roguelike": "roguelike",
    "metroidvania": "metroidvania", "survival horror": "survival-horror", "simulation video game": "life-sim",
    "racing video game": "racing", "stealth video game": "stealth", "shooter game": "shooter", "hip hop music": "hip-hop",
    "pop music": "pop", "rock music": "rock", "r&b": "soul-rnb", "contemporary r&b": "contemporary-rnb", "electronic music": "electronic",
    "folk music": "folk", "indie rock": "indie-rock", "heavy metal": "heavy-metal", "k-pop": "k-pop", "country music": "country",
    "jazz": "jazz", "classical music": "classical", "soundtrack album": "soundtrack", "film score": "film-score", "ambient music": "ambient",
    "alternative rock": "alternative-rock", "electropop": "electropop", "synth-pop": "synth-pop", "punk rock": "punk-rock",
    "soundtrack": "soundtrack", "indian pop": "indian-pop", "reggae": "reggae", "afrobeat": "afrobeat", "latin music": "latin",
    "science fiction": "science-fiction", "fantasy": "fantasy", "horror fiction": "horror", "historical fiction": "historical",
    "crime fiction": "crime", "detective fiction": "detective-story", "romance novel": "romance", "thriller": "thriller",
    "literary fiction": "literary-fiction", "young adult literature": "coming-of-age", "dystopian fiction": "dystopian",
    "television drama": "drama", "sitcom": "sitcom", "crime drama": "crime", "teen drama": "coming-of-age", "anime": "anime",
    "web series": "drama", "miniseries": "drama", "reality television": "drama",
}
PLATFORMS = {"windows": "PC", "personal computer": "PC", "playstation": "PlayStation", "xbox": "Xbox", "nintendo switch": "Nintendo Switch",
             "macos": "PC", "linux": "PC", "steam deck": "PC", "android": "Mobile", "ios": "Mobile"}
CREDITS = {"film": [("director", "P57", 2), ("actor", "P161", 4)], "series": [("creator", "P170", 2), ("director", "P57", 1), ("actor", "P161", 4)],
           "game": [("developer", "P178", 2)], "album": [("artist", "P175", 2)], "book": [("author", "P50", 2)]}


def genre_index(taxonomy_path: Path = TAXONOMY) -> dict[str, dict]:
    """Wikidata genre label (lower case) -> {slug, applies_to}, from the taxonomy's slugs, labels and synonyms plus GENRE_ALIASES."""
    terms = {t["slug"]: t for t in json.loads(taxonomy_path.read_text())["terms"] if t["dimension"] == "genre"}
    idx: dict[str, str] = {}
    for slug, t in terms.items():
        for name in [slug, t["label"], *t.get("synonyms", [])]:
            idx.setdefault(name.lower(), slug)
    idx.update({k: v for k, v in GENRE_ALIASES.items() if v in terms})
    return {k: {"slug": v, "applies": terms[v]["applies_to"]} for k, v in idx.items()}


def genre_terms(labels: list[str], medium: str, idx: dict[str, dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw in labels:
        name = raw.lower().strip()
        hit = idx.get(name) or idx.get(re.sub(r"\s+(film|movie|television series|video game|game|music|novel)$", "", name))
        if hit and ("*" in hit["applies"] or medium in hit["applies"]):
            out[f"genre:{hit['slug']}"] = 0.8
    return dict(list(out.items())[:4])


def tier(sitelinks: int) -> int:
    return 1 if sitelinks >= 70 else 2 if sitelinks >= 35 else 3


SPARQL = "https://query.wikidata.org/sparql"
# Titles that are only an ordinary word people use in requests ("I'd like a romantic film...") are read by the query parser as a
# reference to that title. Until the parser can tell them apart they are left out; see benchmark case "like-is-a-verb".
COLLIDES = {"romantic"}
# Wikidata's full list of book types is too large for one ranked query (it times out), so books use the two that matter.
QUERY_TYPES = {**TYPES, "book": {"Q8261", "Q7725634"}}


def discover(client: Client, medium: str, year: int, today: str, log=print) -> dict[str, int]:
    """The most widely covered works of one medium and year: QID -> number of Wikipedia editions, by SPARQL."""
    types = " ".join(f"wd:{t}" for t in sorted(QUERY_TYPES[medium]))
    end = min(f"{year}-12-31", today)
    query = f"""SELECT ?item ?sl WHERE {{
      VALUES ?type {{ {types} }}
      ?item wdt:P31 ?type .
      {{ ?item wdt:P577 ?d }} UNION {{ ?item wdt:P580 ?d }}
      FILTER(?d >= "{year}-01-01T00:00:00Z"^^xsd:dateTime && ?d <= "{end}T23:59:59Z"^^xsd:dateTime)
      ?item wikibase:sitelinks ?sl . FILTER(?sl >= {MIN_SITELINKS[medium]})
    }} ORDER BY DESC(?sl) LIMIT {CAPS[medium] * 3}"""
    try:
        r = client.get_json(SPARQL, {"query": query, "format": "json"})
    except Exception as e:   # noqa: BLE001 - one failed query should not lose the others
        log(f"  {medium} {year}: {str(e)[:100]}")
        return {}
    return {b["item"]["value"].rsplit("/", 1)[1]: int(b["sl"]["value"]) for b in r["results"]["bindings"]}


def fetch(client: Client, ids: list[str]) -> dict[str, dict]:
    """Entities with every sitelink (Wikidata.entities limits them to English Wikipedia, which cannot rank coverage)."""
    out: dict[str, dict] = {}
    for i in range(0, len(ids), 50):
        data = client.get_json(API, {"action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": "claims|labels|descriptions|sitelinks",
                                     "languages": "en", "format": "json"})
        out.update(data.get("entities", {}))
    return out


def start_date(entity: dict) -> str | None:
    for prop in ("P577", "P580"):
        times = [value(c)["time"] for c in claim_values(entity, prop) if isinstance(value(c), dict) and "time" in value(c)]
        if times:
            return min(times).lstrip("+")[:10]
    return None


def build(wd: Wikidata, client: Client, log=print) -> list[dict]:
    # Skip what the catalogue already holds, except this tool's own previous output, which is being rebuilt.
    mine = {w["slug"] for w in json.loads(OUT.read_text())["works"]} if OUT.exists() else set()
    seed = [w for w in read_seed()["works"] if w["slug"] not in mine]
    known = {(w["medium"], normalise_title(w["title"]), w.get("year")) for w in seed}
    taken = {w["slug"] for w in seed}
    idx = genre_index()
    today = dt.date.today().isoformat()
    picked: list[tuple[str, int, int, str, dict]] = []   # medium, year, sitelinks, qid, entity
    for medium in CAPS:
        for year in YEARS:
            cand = discover(client, medium, year, today, log)
            ents = fetch(client, sorted(cand))
            rows = []
            for q, e in ents.items():
                d = start_date(e)
                if not d or d[:4] != str(year) or d > today:
                    continue
                if not (set(item_ids(e, "P31")) & TYPES[medium]):
                    continue
                n = len(e.get("sitelinks", {}))
                if n < MIN_SITELINKS[medium] or not label_of(e):
                    continue
                if normalise_title(label_of(e)) in COLLIDES:
                    continue
                if (medium, normalise_title(label_of(e)), year) in known or (medium, normalise_title(label_of(e)), year - 1) in known:
                    continue
                rows.append((n, q, e))
            rows.sort(key=lambda r: (-r[0], r[1]))
            log(f"{medium} {year}: {len(cand)} found, {len(rows)} eligible, keeping {min(len(rows), CAPS[medium])}")
            picked += [(medium, year, n, q, e) for n, q, e in rows[:CAPS[medium]]]
    # one batch of label and code lookups for everything the picked works point at
    refs: set[str] = set()
    for medium, _y, _n, _q, e in picked:
        for prop in ("P136", "P495", "P364", "P400"):
            refs |= set(item_ids(e, prop))
        for _role, prop, limit in CREDITS[medium]:
            refs |= set(item_ids(e, prop)[:limit + 2])
    labels = wd.labels(sorted(refs))
    codes = {q: e for q, e in wd.entities(sorted(refs), props="claims").items()}
    works = []
    for medium, year, n, q, e in picked:
        title = label_of(e)
        slug = f"{slugify(title)}-{year}"
        if slug in taken:
            slug = f"{slug}-{q.lower()}"
        taken.add(slug)
        w: dict = {"slug": slug, "medium": medium, "title": title, "year": year, "popularity_tier": tier(n)}
        lang = [iso(codes.get(x), "P218") for x in item_ids(e, "P364")[:1]]
        if lang and lang[0]:
            w["language"] = lang[0]
        countries = [c for c in (iso(codes.get(x), "P297") for x in item_ids(e, "P495")[:3]) if c]
        if countries:
            w["countries"] = countries
        rt = runtime_minutes(e)
        if medium == "film" and rt:
            w["runtime_minutes"] = rt
        credits = []
        for role, prop, limit in CREDITS[medium]:
            for x in item_ids(e, prop)[:limit]:
                if labels.get(x) and labels[x] != x:
                    credits.append([role, labels[x]])
        if credits:
            w["credits"] = credits
        desc = (e.get("descriptions", {}).get("en", {}) or {}).get("value", "")
        parts = [f"{'An' if desc[:1].lower() in 'aeiou' else 'A'} {desc}." if desc else f"{title} ({year})."]
        by_role: dict[str, list[str]] = {}
        for role, name in credits:
            by_role.setdefault(role, []).append(name)
        for role, lead in (("director", "Directed by"), ("creator", "Created by"), ("developer", "Developed by"), ("artist", "By"),
                           ("author", "By"), ("actor", "Starring")):
            names = [n for n in by_role.get(role, []) if n not in desc]   # the description often says it already
            if lead in ("By", "Directed by") and f" {lead.lower()} " in desc.lower() + " ":   # the description already credits them
                continue
            if names and not (role == "director" and "creator" in by_role):
                parts.append(f"{lead} " + (", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]) + ".")
        if len(" ".join(parts).split()) < 5:
            parts.append("More details are not in the catalogue yet.")
        w["summary"] = " ".join(parts)
        terms = genre_terms([labels.get(x, "") for x in item_ids(e, "P136")], medium, idx)
        if terms:
            w["terms"] = terms
        attrs: dict = {"wikidata": q}
        if medium == "game":
            plats = sorted({p for x in item_ids(e, "P400") for k, p in PLATFORMS.items() if k in labels.get(x, "").lower()})
            if plats:
                attrs["platforms"] = plats
        w["attributes"] = attrs
        works.append(w)
    return works


def item_ids(entity: dict, prop: str) -> list[str]:
    return [v["id"] for c in claim_values(entity, prop) if isinstance((v := value(c)), dict) and "id" in v]


def iso(entity: dict | None, prop: str) -> str | None:
    if not entity:
        return None
    for c in claim_values(entity, prop):
        v = value(c)
        if isinstance(v, str):
            return v.lower() if prop == "P218" else v.upper()
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    client = Client(offline=args.offline, max_age_days=365)
    works = build(Wikidata(client), client)
    about = ("Recent works (2025 onwards) from Wikidata (CC0), ranked by Wikipedia coverage. "
             "Regenerate with python -m mde.ingest.recent; review before merging. No parents' guide is claimed.")
    OUT.write_text(json.dumps({"about": about, "works": works}, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(works)} works to {OUT}")


if __name__ == "__main__":
    main()
