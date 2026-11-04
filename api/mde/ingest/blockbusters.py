# ruff: noqa: E501
"""The big films and games: everything with a large budget or a franchise, from Wikidata (CC0). Writes seed/reference-blockbusters.json
(films) and seed/reference-games-more.json (games).

    python -m mde.ingest.blockbusters film       # films with a budget of at least 50 million, or part of a film series, upcoming ones included
    python -m mde.ingest.blockbusters game       # widely covered video games, and every game in a game series

Candidates come from the Wikidata query service; each is fetched, checked against the catalogue (same title and year, or the same
Wikidata item, means it is already there) and converted the same way the other imports are. Franchise names come from the "part of the
series" statement. Nothing is invented: titles, dates, credits and genres are Wikidata's; the summary is Wikidata's one-line
description plus the credits. No parents' guide, mood or theme is claimed here; the enrichment tools add those afterwards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path

from mde.catalogue.model import normalise_title
from mde.catalogue.seedfiles import read_seed
from mde.ingest.http import Client
from mde.ingest.recent import COLLIDES, SPARQL, convert, credit_spellings, fetch, genre_index, item_ids, start_date
from mde.ingest.wikidata import TYPES, Wikidata, label_of

SEED = Path(__file__).parent.parent / "seed"
OUT = {"film": SEED / "reference-blockbusters.json", "game": SEED / "reference-games-more.json"}
BUDGET_MIN = 50_000_000
MIN_SITELINKS = {"film": 5, "game": 8}
SERIES_MIN_SITELINKS = {"film": 6, "game": 5}
HORIZON = "2027-12-31"  # announced films and games are included; nothing further out
# currency units whose 50 million is at least roughly 50 million US dollars
BIG_CURRENCIES = ("wd:Q4917", "wd:Q4916", "wd:Q25224")


def sparql(client: Client, query: str, log=print) -> list[dict]:
    client.timeout = 150  # a big query can take a minute or two on the query service
    for i in range(4):
        client.down.pop("query.wikidata.org", None)  # one slow answer must not mark the whole host as down
        try:
            return client.get_json(SPARQL, {"query": query, "format": "json"})["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 - the query service throttles under load
            log(f"  retry in {10 * (i + 1)}s: {str(e)[:90]}")
            time.sleep(10 * (i + 1))
    return []


def candidates(client: Client, medium: str, log=print) -> dict[str, int]:
    """Wikidata item -> number of Wikipedia editions, for every film or game that qualifies."""
    # The main item type only, and no subclass walk: anything wider makes the series and coverage queries time out on the query service.
    direct = {"film": "?item wdt:P31 wd:Q11424", "game": "?item wdt:P31 wd:Q7889"}[medium]
    kind = {"film": "?item wdt:P31/wdt:P279* wd:Q11424", "game": direct}[medium]
    out: dict[str, int] = {}
    if medium == "film":
        for unit in BIG_CURRENCIES:  # one query per currency: the query service times out on a combined one
            q = f"""SELECT DISTINCT ?item ?sl WHERE {{ {kind} .
              {{ ?item p:P2130/psv:P2130 [wikibase:quantityAmount ?a; wikibase:quantityUnit {unit}] }} UNION {{ ?item p:P2769/psv:P2769 [wikibase:quantityAmount ?a; wikibase:quantityUnit {unit}] }}
              FILTER(?a >= {BUDGET_MIN}) ?item wikibase:sitelinks ?sl }}"""
            rows = sparql(client, q, log)
            out.update({b["item"]["value"].rsplit("/", 1)[1]: int(b["sl"]["value"]) for b in rows})
        log(f"film budget >= 50M (all currencies): {len(out)}")
    # part of a series: list the series first (a small query), then their members in batches; one combined query times out
    series_types = {"film": ("Q24856", "Q196600"), "game": ("Q7058673", "Q196600")}[medium]
    series: set[str] = set()
    for ty in series_types:
        rows = sparql(client, f"SELECT ?s WHERE {{ ?s wdt:P31 wd:{ty}; wikibase:sitelinks ?sl FILTER(?sl >= 12) }}", log)
        series |= {b["s"]["value"].rsplit("/", 1)[1] for b in rows}
    series_sorted = sorted(series)
    found = 0
    for i in range(0, len(series_sorted), 40):
        vals = " ".join("wd:" + s for s in series_sorted[i : i + 40])
        q = f"""SELECT DISTINCT ?item ?sl WHERE {{ VALUES ?s {{ {vals} }} ?item wdt:P179 ?s; {direct.split(' ', 1)[1]}; wikibase:sitelinks ?sl FILTER(?sl >= {SERIES_MIN_SITELINKS[medium]}) }}"""
        rows = sparql(client, q, log)
        found += len(rows)
        out.update({b["item"]["value"].rsplit("/", 1)[1]: int(b["sl"]["value"]) for b in rows})
    log(f"{medium} in {len(series_sorted)} series: {found}")
    if medium == "game":
        # widely covered games, series or not: the ones a catalogue of games is expected to hold
        for lo, hi in ((60, 9999), (40, 60), (30, 40), (24, 30)):
            q = f"""SELECT DISTINCT ?item ?sl WHERE {{ {kind} . ?item wikibase:sitelinks ?sl . FILTER(?sl >= {lo} && ?sl < {hi}) }} LIMIT 4000"""
            rows = sparql(client, q, log)
            out.update({b["item"]["value"].rsplit("/", 1)[1]: int(b["sl"]["value"]) for b in rows})
            log(f"game sitelinks {lo}-{hi}: {len(rows)}")
    return out


def known_titles() -> tuple[set[tuple], set[str], set[str]]:
    seed = [w for w in read_seed()["works"]]
    qids = {(w.get("attributes") or {}).get("wikidata") for w in seed}
    prov = json.loads((SEED.parent / "catalogue" / "reference-provenance.json").read_text())["works"]
    qids |= {p.get("qid") for p in prov.values()}
    known = {(w["medium"], normalise_title(w["title"]), w.get("year")) for w in seed}
    return known, {w["slug"] for w in seed}, qids - {None}


def build(client: Client, medium: str, log=print) -> list[dict]:
    wd = Wikidata(client)
    out_path = OUT[medium]
    mine = {w["slug"] for w in json.loads(out_path.read_text())["works"]} if out_path.exists() else set()
    # rebuilding this tool's own output: its works are not "already in the catalogue"
    seed_all = [w for w in read_seed()["works"] if w["slug"] not in mine]
    known = {(w["medium"], normalise_title(w["title"]), w.get("year")) for w in seed_all}
    taken = {w["slug"] for w in seed_all}
    qids = {(w.get("attributes") or {}).get("wikidata") for w in seed_all}
    prov = json.loads((SEED.parent / "catalogue" / "reference-provenance.json").read_text())["works"]
    qids |= {p.get("qid") for p in prov.values()}
    idx = genre_index()
    today = dt.date.today().isoformat()
    cand = candidates(client, medium, log)
    cand = {q: n for q, n in cand.items() if q not in qids}
    log(f"{len(cand)} candidates not yet in the catalogue by Wikidata item")
    ents = fetch(client, sorted(cand))
    picked = []
    for q, e in ents.items():
        types = set(item_ids(e, "P31"))
        if not (types & TYPES[medium]) and medium == "film":
            continue
        d = start_date(e)
        if not d or d > HORIZON or not label_of(e):
            continue
        year = int(d[:4])
        n = len(e.get("sitelinks", {}))
        if n < MIN_SITELINKS[medium] or normalise_title(label_of(e)) in COLLIDES:
            continue
        key = normalise_title(label_of(e))
        if (medium, key, year) in known or (medium, key, year - 1) in known or (medium, key, year + 1) in known:
            continue
        picked.append((medium, year, n, q, e))
    picked.sort(key=lambda r: (-r[2], r[3]))
    log(f"{len(picked)} new {medium}s to add")
    works = convert(wd, picked, taken, idx, credit_spellings(seed_all))
    # franchise names and upcoming status
    series_ids = {q: item_ids(e, "P179") for _m, _y, _n, q, e in picked}
    labels = wd.labels(sorted({s for v in series_ids.values() for s in v}))
    by_q = {w["attributes"]["wikidata"]: w for w in works}
    for q, w in by_q.items():
        names = []
        for s in series_ids.get(q, [])[:2]:
            name = labels.get(s, "")
            for tail in (" (film series)", " (franchise)", " (media franchise)", " film series", " (video game series)", " (series)"):
                name = name.replace(tail, "")
            if name and name != s and name not in names:
                names.append(name)
        if names:
            w["attributes"]["franchises"] = names
        e = ents[q]
        d = start_date(e)
        if d and d > today:
            w["attributes"]["release_status"] = "upcoming"
            w["attributes"]["release_date"] = d
            w["summary"] = w["summary"].rstrip() + f" Not yet released: expected {d[:4]}."
    return works


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("medium", choices=["film", "game"])
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    client = Client(offline=args.offline, max_age_days=0.04)  # about an hour: a stale or partial query answer must not stick
    works = build(client, args.medium)
    about = {
        "film": "Films with a budget of at least 50 million, or part of a film series, from Wikidata (CC0), including announced ones. ",
        "game": "Widely covered video games and every game in a series, from Wikidata (CC0). ",
    }[args.medium]
    OUT[args.medium].write_text(
        json.dumps(
            {"about": about + "Regenerate with python -m mde.ingest.blockbusters; no parents' guide is claimed.", "works": works},
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    print(f"wrote {len(works)} works to {OUT[args.medium]}")


if __name__ == "__main__":
    main()
