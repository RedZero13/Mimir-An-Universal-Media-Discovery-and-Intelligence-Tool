"""Merging open-source enrichment (mde/data/enrichment/*.json) into catalogue profiles.

Pure and shared: the PostgreSQL importer, the in-memory catalogue and (via demo/engine.cjs) the public site
all apply the same rules.

- Facts (year, runtime, page count) from a source replace the unverified seed value. The seed value is kept in
  `fact_sources` so the work page can show the disagreement.
- Everything else (images, scores, box office, series, IDs, links, tracks) is added with its source.
- Seed attributes `series` / `series_position` become editorial series groups.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from mde.catalogue.model import GroupRef, Image, Score, WorkProfile, slugify

ENRICHMENT_DIR = Path(__file__).parent.parent / "data" / "enrichment"
SOURCE_ORDER = ("wikidata", "openlibrary", "musicbrainz", "tmdb", "publisher")   # later sources win for images of the same kind
IMAGE_PREFERENCE = {"poster": 0, "cover": 1, "still": 2, "logo": 3}


UNNAMED = re.compile(r"^Q\d+$")


def load_enrichment(directory: Path = ENRICHMENT_DIR) -> dict[str, dict]:
    out = {}
    for name in SOURCE_ORDER:
        path = directory / f"{name}.json"
        if path.exists():
            out[name] = json.loads(path.read_text())
    return out


LINK_ORDER = ("listen:spotify", "listen:youtube-music", "watch:justwatch", "buy:steam", "buy:amazon", "info:publisher", "reactions:letterboxd",
              "reactions:rotten-tomatoes", "reactions:metacritic", "reactions:goodreads", "reactions:storygraph",
              "reactions:reddit", "reactions:youtube", "info:imdb", "info:openlibrary", "info:musicbrainz", "info:wikipedia")


def _rank(order: tuple, item: str) -> int:
    return order.index(item) if item in order else len(order)


def _set_fact(w: WorkProfile, field: str, value, source: str) -> None:
    attr = {"release_year": "year"}.get(field, field)
    current = getattr(w, attr)
    if field in w.fact_sources:                      # a later source overrides an earlier one; keep the seed value
        w.fact_sources[field] = {"source": source, "seed": w.fact_sources[field]["seed"]}
    elif current != value:
        w.fact_sources[field] = {"source": source, "seed": current}
    setattr(w, attr, value)


def editorial_groups(w: WorkProfile) -> list[GroupRef]:
    series = w.attributes.get("series")
    if not series:
        return []
    pos = w.attributes.get("series_position")
    return [GroupRef(slugify(series), series, "series", str(pos) if pos is not None else None, "editorial")]


def normalise_order(w: WorkProfile) -> None:
    """Deterministic ordering so every backend renders identical pages."""
    src = lambda s: _rank(("editorial",) + SOURCE_ORDER, s)  # noqa: E731
    w.images.sort(key=lambda i: (IMAGE_PREFERENCE.get(i.kind, 9), src(i.source)))
    w.scores.sort(key=lambda sc: (src(sc.source), sc.publisher, sc.metric))
    w.box_office.sort(key=lambda b: (src(b["source"]), -b["amount"]))
    w.groups.sort(key=lambda g: (src(g.source), g.slug))
    w.links.sort(key=lambda link: (_rank(LINK_ORDER, link["kind"]), link["kind"]))


def apply(works: list[WorkProfile], enrichment: dict[str, dict]) -> list[WorkProfile]:
    by_slug = {w.slug: w for w in works}
    for w in works:
        w.groups.extend(editorial_groups(w))
    for source in SOURCE_ORDER:
        data = enrichment.get(source)
        if not data:
            continue
        for slug, rec in data.get("works", {}).items():
            w = by_slug.get(slug)
            if w is None or not rec.get("match"):
                if w is not None and rec.get("links"):
                    w.links = [dict(link) for link in rec["links"]]
                continue
            for field, value in rec.get("facts", {}).items():
                if field in ("release_year", "runtime_minutes", "page_count") and value is not None:
                    _set_fact(w, field, value, source)
            for img in rec.get("images", []):
                if img.get("url"):
                    w.images = [i for i in w.images if not (i.kind == img["kind"] and i.source == source)]
                    w.images.append(Image(img["kind"], img["url"], source, img.get("licence", "see source"), img.get("attribution")))
            for sc in rec.get("scores", []):
                if UNNAMED.match(sc["publisher"]):   # a publisher Wikidata couldn't name: a score nobody can weigh
                    continue
                w.scores.append(Score(sc["publisher"], sc["metric"], float(sc["value"]), float(sc["scale_max"]),
                                      sc.get("votes"), sc.get("as_of"), source))
            w.box_office.extend({**b, "source": source} for b in rec.get("box_office", []))
            for g in rec.get("series", []):
                gslug = slugify(g["name"])
                if not any(x.slug == gslug for x in w.groups):
                    w.groups.append(GroupRef(gslug, g["name"], "series", g.get("position"), source))
            w.ids.update(rec.get("ids", {}))
            if rec.get("links"):
                w.links = [dict(link) for link in rec["links"]]
            if rec.get("tracks"):
                w.tracks = [dict(t) for t in rec["tracks"]]
            if source == "openlibrary" and rec.get("key"):
                w.ids.setdefault("openlibrary", rec["key"].rsplit("/", 1)[-1])
            if source == "musicbrainz" and rec["match"].get("mbid"):
                w.ids.setdefault("musicbrainz_release_group", rec["match"]["mbid"])
    for w in works:
        normalise_order(w)
    return works


def primary_image(w: WorkProfile) -> Image | None:
    return w.images[0] if w.images else None
