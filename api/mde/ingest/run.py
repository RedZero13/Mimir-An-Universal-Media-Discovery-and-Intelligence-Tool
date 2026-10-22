"""Runs connectors over the seed catalogue and writes one enrichment file per source.

    python -m mde ingest                      # all sources (TMDB only if a key is configured)
    python -m mde ingest --source wikidata    # one source
    python -m mde ingest --offline            # rebuild from the HTTP cache only

Output: mde/data/enrichment/<source>.json, committed and reviewed like code. Each file lists, per work, what
was matched and why, the normalised facts, and any disagreement with the seed ("conflicts"), so an editor
can accept or reject them. Unmatched works are listed with their candidates.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from mde.catalogue.seedfiles import read_seed
from mde.ingest import commons, links, tmdb
from mde.ingest.http import Client, FetchError
from mde.ingest.musicbrainz import LICENCE as MB_LICENCE
from mde.ingest.musicbrainz import MusicBrainz
from mde.ingest.openlibrary import LICENCE as OL_LICENCE
from mde.ingest.openlibrary import OpenLibrary
from mde.ingest.wikidata import LICENCE as WD_LICENCE
from mde.ingest.wikidata import Wikidata

OUT_DIR = Path(__file__).parent.parent / "data" / "enrichment"
SOURCES = ("wikidata", "openlibrary", "musicbrainz", "tmdb")


def _seed() -> list[dict]:
    return read_seed()["works"]


def _conflicts(work: dict, facts: dict) -> list[dict]:
    seed = {"release_year": work.get("year"), "runtime_minutes": work.get("runtime_minutes")}
    out = []
    for field, val in facts.items():
        if field in seed and seed[field] is not None and val is not None and seed[field] != val:
            tolerance = 2 if field == "runtime_minutes" else 0
            if abs(seed[field] - val) > tolerance:
                out.append({"field": field, "seed": seed[field], "source": val})
    return out


class SourceUnavailable(Exception):
    pass


def _write(source: str, licence: str, works: dict, extra: dict | None = None) -> Path:
    if works and all(str(r.get("reason", "")).startswith("fetch failed") for r in works.values()):
        # Never replace a good file with one where every lookup failed (e.g. the host is blocked).
        raise SourceUnavailable(f"{source}: every request failed; first error: {next(iter(works.values()))['reason']}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{source}.json"
    body = {"source": source, "licence": licence, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "unmatched": sorted(s for s, r in works.items() if not r.get("match")), "works": works, **(extra or {})}
    path.write_text(json.dumps(body, indent=1, ensure_ascii=False, sort_keys=False) + "\n")
    return path


def run_wikidata(client: Client, seed: list[dict]) -> dict:
    wd = Wikidata(client)
    works: dict[str, dict] = {}
    for w in seed:
        try:
            rec = wd.enrich(w)
        except FetchError as e:
            rec = {"match": None, "reason": f"fetch failed: {e}"}
        if rec.get("match"):
            rec["conflicts"] = _conflicts(w, rec["facts"])
            for img in rec.get("images", []):
                try:
                    info = commons.image_info(client, img["commons_file"])
                except FetchError:
                    info = None
                if info:
                    img.update(info)
            rec["images"] = [i for i in rec.get("images", []) if i.get("url")]
        works[w["slug"]] = rec
        print(f"  wikidata {w['slug']}: {(rec.get('match') or {}).get('qid') or rec.get('reason')}")
    # Resolve item links to catalogue works.
    by_qid = {r["match"]["qid"]: s for s, r in works.items() if r.get("match")}
    for rec in works.values():
        if rec.get("match"):
            for key in ("follows", "followed_by", "based_on"):
                rec[key] = [{"qid": q, "slug": by_qid.get(q)} for q in rec.get(key, [])]
    for w in seed:
        rec = works[w["slug"]]
        rec["links"] = links.links_for(w, rec.get("ids", {}) if rec.get("match") else {}, rec.get("wikipedia"))
    return works


def run_per_medium(client: Client, seed: list[dict], medium: str, connector) -> dict:
    works = {}
    for w in seed:
        if w["medium"] != medium:
            continue
        try:
            rec = connector.enrich(w)
        except FetchError as e:
            rec = {"match": None, "reason": f"fetch failed: {e}"}
        if rec.get("match"):
            rec["conflicts"] = _conflicts(w, rec.get("facts", {}))
        works[w["slug"]] = rec
        print(f"  {medium} {w['slug']}: {'matched' if rec.get('match') else rec.get('reason')}")
    return works


def run(sources: tuple[str, ...] = SOURCES, offline: bool = False) -> dict[str, Path]:
    client = Client(offline=offline)
    seed = _seed()
    written = {}
    if "wikidata" in sources:
        written["wikidata"] = _write("wikidata", WD_LICENCE, run_wikidata(client, seed))
    if "openlibrary" in sources:
        written["openlibrary"] = _write("openlibrary", OL_LICENCE, run_per_medium(client, seed, "book", OpenLibrary(client)))
    if "musicbrainz" in sources:
        written["musicbrainz"] = _write("musicbrainz", MB_LICENCE, run_per_medium(client, seed, "album", MusicBrainz(client)))
    if "tmdb" in sources and tmdb.configured():
        wd = json.loads((OUT_DIR / "wikidata.json").read_text())["works"] if (OUT_DIR / "wikidata.json").exists() else {}
        t = tmdb.TMDB(client)
        works = {}
        for w in seed:
            if w["medium"] == "film":
                try:
                    works[w["slug"]] = t.enrich(w, (wd.get(w["slug"]) or {}).get("ids", {}))
                except FetchError as e:
                    works[w["slug"]] = {"match": None, "reason": f"fetch failed: {e}"}
        written["tmdb"] = _write("tmdb", "TMDB API terms; attribution required", works, {"attribution": tmdb.ATTRIBUTION})
    return written
