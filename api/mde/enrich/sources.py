# ruff: noqa: E501, E731
"""Medium-specific sources, one fetcher each. Results are third-party data kept under data/work-text/ (not committed); `apply` derives the
facts that go into the seed (lengths, platforms, episode counts, scores, content notes) and the tagger reads the descriptions and tags.

    python -m mde.enrich.sources tvmaze|steam|deezer|musicbrainz|openlibrary     (each resumable)
"""

from __future__ import annotations

import argparse
import re
import urllib.parse

from mde.catalogue.model import normalise_title
from mde.enrich import pool
from mde.enrich.worklist import TEXT, worklist

q = urllib.parse.quote


def _first_credit(w: dict, roles=("artist", "author", "director", "creator")) -> str:
    return w.get("_credit", "")


# ---------------------------------------------------------------------------------------------------------- TVmaze (series)
def tvmaze(arg) -> dict | None:
    imdb, title, year = arg
    show = pool.get_json(f"https://api.tvmaze.com/lookup/shows?imdb={imdb}") if imdb else None
    if not show:
        hits = pool.get_json(f"https://api.tvmaze.com/search/shows?q={q(title)}") or []
        cand = [
            h["show"]
            for h in hits
            if normalise_title(h["show"]["name"]) == normalise_title(title)
            and (not year or not h["show"].get("premiered") or abs(int(h["show"]["premiered"][:4]) - year) <= 1)
        ]
        show = cand[0] if cand else None
    if not show:
        return None
    full = pool.get_json(f"https://api.tvmaze.com/shows/{show['id']}?embed[]=episodes") or show
    eps = (full.get("_embedded") or {}).get("episodes") or []
    seasons = sorted({e["season"] for e in eps if e.get("season")})
    runtimes = [e["runtime"] for e in eps if e.get("runtime")]
    return {
        "id": show["id"],
        "name": full.get("name"),
        "type": full.get("type"),
        "genres": full.get("genres"),
        "status": full.get("status"),
        "runtime": full.get("runtime") or full.get("averageRuntime"),
        "episode_runtime": round(sum(runtimes) / len(runtimes)) if runtimes else None,
        "premiered": full.get("premiered"),
        "ended": full.get("ended"),
        "language": full.get("language"),
        "network": ((full.get("network") or full.get("webChannel")) or {}).get("name"),
        "country": (((full.get("network") or {}).get("country") or {}).get("code")),
        "rating": (full.get("rating") or {}).get("average"),
        "episodes": len(eps) or None,
        "seasons": len(seasons) or None,
        "summary": re.sub(r"<[^>]+>", "", full.get("summary") or "") or None,
        "official_site": full.get("officialSite"),
        "url": full.get("url"),
    }


# ---------------------------------------------------------------------------------------------------------- Steam (games)
def steam(arg) -> dict | None:
    appid, title, year = arg
    if not appid:
        r = pool.get_json(f"https://store.steampowered.com/api/storesearch/?term={q(title)}&cc=us&l=en") or {}
        cand = [i for i in r.get("items", []) if i.get("type") == "app" and normalise_title(i["name"]) == normalise_title(title)]
        if not cand:
            return None
        appid = cand[0]["id"]
    d = pool.get_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en") or {}
    e = (d.get(str(appid)) or {}).get("data")
    if not e or e.get("type") not in ("game", "dlc", "demo"):
        return None
    ratings = {k: {"rating": v.get("rating"), "descriptors": v.get("descriptors")} for k, v in (e.get("ratings") or {}).items()}
    return {
        "appid": appid,
        "name": e.get("name"),
        "required_age": e.get("required_age"),
        "description": e.get("short_description"),
        "genres": [g["description"] for g in e.get("genres", [])],
        "categories": [c["description"] for c in e.get("categories", [])],
        "developers": e.get("developers"),
        "publishers": e.get("publishers"),
        "platforms": e.get("platforms"),
        "metacritic": (e.get("metacritic") or {}).get("score"),
        "release": (e.get("release_date") or {}).get("date"),
        "recommendations": (e.get("recommendations") or {}).get("total"),
        "content_notes": (e.get("content_descriptors") or {}).get("notes"),
        "content_ids": (e.get("content_descriptors") or {}).get("ids"),
        "ratings": ratings,
        "website": e.get("website"),
    }


# ---------------------------------------------------------------------------------------------------------- Deezer (albums)
def deezer(arg) -> dict | None:
    artist, title, year = arg
    query = q('artist:"' + artist + '" album:"' + title + '"')
    r = pool.get_json(f"https://api.deezer.com/search/album?q={query}&limit=5") or {}
    cand = [a for a in r.get("data", []) if normalise_title(a["title"]) == normalise_title(title)]
    if not cand:
        return None
    a = pool.get_json(f"https://api.deezer.com/album/{cand[0]['id']}")
    if not a or a.get("error"):
        return None
    tracks = [{"title": t["title"], "seconds": t.get("duration")} for t in (a.get("tracks") or {}).get("data", [])]
    return {
        "id": a["id"],
        "title": a["title"],
        "label": a.get("label"),
        "tracks": a.get("nb_tracks"),
        "seconds": a.get("duration"),
        "genres": [g["name"] for g in (a.get("genres") or {}).get("data", [])],
        "released": a.get("release_date"),
        "explicit": a.get("explicit_lyrics"),
        "record_type": a.get("record_type"),
        "track_list": tracks,
        "fans": a.get("fans"),
    }


# ---------------------------------------------------------------------------------------------------------- MusicBrainz tags (albums)
def musicbrainz(arg) -> dict | None:
    (mbid,) = arg
    d = pool.get_json(f"https://musicbrainz.org/ws/2/release-group/{mbid}?inc=genres+tags+ratings&fmt=json")
    if not d:
        return None
    return {
        "genres": [g["name"] for g in sorted(d.get("genres", []), key=lambda g: -g.get("count", 0))][:8],
        "tags": [t["name"] for t in sorted(d.get("tags", []), key=lambda t: -t.get("count", 0))][:10],
        "rating": (d.get("rating") or {}).get("value"),
        "type": d.get("primary-type"),
        "secondary": d.get("secondary-types"),
    }


# ---------------------------------------------------------------------------------------------------------- Open Library (books)
def openlibrary(arg) -> dict | None:
    olid, title, author = arg
    work = None
    if olid:
        work = pool.get_json(f"https://openlibrary.org/works/{olid}.json") if olid.startswith("OL") and olid.endswith("W") else None
    pages = None
    if not work:
        r = (
            pool.get_json(
                f"https://openlibrary.org/search.json?title={q(title)}&author={q(author or '')}&limit=3&fields=key,title,number_of_pages_median,subject"
            )
            or {}
        )
        cand = [d for d in r.get("docs", []) if normalise_title(d["title"]) == normalise_title(title)]
        if not cand:
            return None
        work = pool.get_json(f"https://openlibrary.org{cand[0]['key']}.json")
        pages = cand[0].get("number_of_pages_median")
    if not work:
        return None
    desc = work.get("description")
    desc = desc.get("value") if isinstance(desc, dict) else desc
    return {
        "key": work.get("key"),
        "description": desc,
        "subjects": (work.get("subjects") or [])[:25],
        "places": (work.get("subject_places") or [])[:6],
        "people": (work.get("subject_people") or [])[:8],
        "times": (work.get("subject_times") or [])[:4],
        "pages": pages,
        "first_published": work.get("first_publish_date"),
    }


JOBS = {
    "tvmaze": ("series", tvmaze, 0.55, lambda w: (w["ids"].get("imdb"), w["title"], w["year"])),
    "steam": ("game", steam, 1.0, lambda w: (w["ids"].get("steam"), w["title"], w["year"])),
    "deezer": ("album", deezer, 0.12, lambda w: (w["credit"], w["title"], w["year"])),
    "musicbrainz": ("album", musicbrainz, 1.1, lambda w: (w["ids"].get("musicbrainz"),)),
    "openlibrary": ("book", openlibrary, 0.6, lambda w: (w["ids"].get("openlibrary"), w["title"], w["credit"])),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", choices=sorted(JOBS))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    medium, fn, gap, mk = JOBS[a.source]
    from mde.catalogue.seedfiles import read_seed

    credits = {
        w["slug"]: next((c[1] for c in w.get("credits", []) if c[0] in ("artist", "author", "director", "creator")), "") for w in read_seed()["works"]
    }
    titles = {w["slug"]: w["title"] for w in read_seed()["works"]}
    items = []
    for w in worklist():
        if w["medium"] != medium or (a.source == "musicbrainz" and not w["ids"].get("musicbrainz")):
            continue
        w = {**w, "title": titles[w["slug"]], "credit": credits.get(w["slug"], "")}
        items.append((w["slug"], mk(w)))
    pool.run(items[: a.limit] if a.limit else items, fn, TEXT / f"{a.source}.jsonl", workers=3, min_gap=gap)


if __name__ == "__main__":
    main()
