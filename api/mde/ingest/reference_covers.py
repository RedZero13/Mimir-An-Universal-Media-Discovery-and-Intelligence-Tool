"""Covers for the works imported from Wikidata (seed/reference-*.json).

Books: the Open Library work id Wikidata records (P648, kept in catalogue/reference-provenance.json) names the work;
Open Library lists its cover ids. Albums: the MusicBrainz release-group id (P436) names the album; the Cover Art Archive
says whether it holds a front cover. Only covers that exist are recorded, in the same shape the matched catalogue uses,
so the page shows a real cover where there is one and a generated one otherwise. Cover rights stay with their owners
and are shown for identification, as for every other cover.

    python -m mde.ingest.reference_covers [--limit N] [--only books|albums]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mde.ingest.http import Client, FetchError

HERE = Path(__file__).parent.parent
ENRICH = HERE / "data" / "enrichment"
OL_LICENCE = "Cover via Open Library, shown for identification; rights remain with the publisher"
CAA_LICENCE = "Cover via the Cover Art Archive, shown for identification; rights remain with the owners"


def _slugs(seed_file: str) -> set[str]:
    return {w["slug"] for w in json.loads((HERE / "seed" / seed_file).read_text())["works"]}


def _load(name: str) -> dict:
    return json.loads((ENRICH / f"{name}.json").read_text())


def _save(name: str, data: dict) -> None:
    (ENRICH / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def book_cover(client: Client, olid: str) -> str | None:
    work = client.get_json(f"https://openlibrary.org/works/{olid}.json")
    ids = [c for c in (work.get("covers") or []) if isinstance(c, int) and c > 0]
    return f"https://covers.openlibrary.org/b/id/{ids[0]}-L.jpg" if ids else None


def album_cover(client: Client, mbid: str) -> str | None:
    listing = client.get_json(f"https://coverartarchive.org/release-group/{mbid}")
    return f"https://coverartarchive.org/release-group/{mbid}/front-500" if any(i.get("front") for i in listing.get("images", [])) else None


def _tiers(seed_file: str) -> dict[str, int]:
    return {w["slug"]: w.get("popularity_tier") or 5 for w in json.loads((HERE / "seed" / seed_file).read_text())["works"]}


def run(only: str | None, limit: int | None, trust_albums: int = 0) -> dict[str, int]:
    prov = json.loads((HERE / "catalogue" / "reference-provenance.json").read_text())["works"]
    client = Client()
    counts = {"books": 0, "albums": 0, "checked": 0}
    if only in (None, "books"):
        data = _load("openlibrary")
        for slug in sorted(_slugs("reference-books.json")):
            olid = (prov.get(slug, {}).get("ids") or {}).get("openlibrary")
            if not olid or (data["works"].get(slug) or {}).get("images"):
                continue
            if limit is not None and counts["checked"] >= limit:
                break
            counts["checked"] += 1
            try:
                url = book_cover(client, olid)
            except FetchError:
                continue
            if url:
                rec = data["works"].setdefault(slug, {
                    "match": {"key": f"/works/{olid}", "reason": "Open Library work id from Wikidata"},
                    "key": f"/works/{olid}", "url": f"https://openlibrary.org/works/{olid}", "facts": {}, "scores": [], "conflicts": []})
                rec["images"] = [{"kind": "cover", "url": url, "licence": OL_LICENCE, "attribution": "Open Library"}]
                counts["books"] += 1
        _save("openlibrary", data)
    if only in (None, "albums"):
        data = _load("musicbrainz")
        tiers = _tiers("reference-albums.json")
        for slug in sorted(_slugs("reference-albums.json")):
            mbid = (prov.get(slug, {}).get("ids") or {}).get("musicbrainz")
            if not mbid or (data["works"].get(slug) or {}).get("images"):
                continue
            if limit is not None and counts["checked"] >= limit:
                break
            counts["checked"] += 1
            try:
                url = album_cover(client, mbid)
            except FetchError:
                # The listing redirects to archive.org; where that host can't be reached, widely known albums (tier
                # `trust_albums` or better) are recorded unchecked. The page falls back to a generated cover if one 404s.
                url = f"https://coverartarchive.org/release-group/{mbid}/front-500" if trust_albums and tiers.get(slug, 5) <= trust_albums else None
            if url:
                rec = data["works"].setdefault(slug, {
                    "match": {"mbid": mbid, "reason": "MusicBrainz release group from Wikidata"},
                    "url": f"https://musicbrainz.org/release-group/{mbid}", "facts": {}, "tracks": [], "conflicts": []})
                rec["images"] = [{"kind": "cover", "url": url, "licence": CAA_LICENCE, "attribution": "Cover Art Archive / MusicBrainz"}]
                counts["albums"] += 1
        _save("musicbrainz", data)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["books", "albums"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--trust-albums", type=int, default=0, metavar="TIER", help="record unchecked covers for albums of this tier or better")
    a = ap.parse_args()
    print(run(a.only, a.limit, a.trust_albums))
