# ruff: noqa: E501
"""Writes the enrichment records the app already reads for the imported works: ids, review scores, box office, outbound links and page counts.

    python -m mde.enrich.enrichment            writes data/enrichment/wikidata.json (new works only) and openlibrary.json (page counts)

Records use the same shape as the pilot's, so score sorting, "reactions" and "where to watch or listen" links, box office and page-based
reading time work for these works with no change to the app. Existing records are never replaced.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from mde.enrich import pool
from mde.enrich.apply import CURRENCY, PUBLISHERS, Sources
from mde.enrich.worklist import MDE, TEXT, worklist
from mde.ingest.links import links_for
from mde.ingest.wikidata import parse_score

ENRICHMENT = MDE / "data" / "enrichment"
SCOPES = {"Q13780930": "worldwide", "Q30": "United States", "Q49": "North America", "Q2017699": "US & Canada"}


def score_rows(reviews: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for r in reviews:
        parsed = parse_score(r["v"])
        pub = PUBLISHERS.get(r["by"])
        if not parsed or not pub:
            continue
        value, scale = parsed
        metric = {
            ("Rotten Tomatoes", 100.0): "Tomatometer score",
            ("Rotten Tomatoes", 10.0): "Rotten Tomatoes average of rated reviews",
            ("Metacritic", 100.0): "Metascore",
            ("IMDb", 10.0): "IMDb rating",
        }.get((pub, scale), "score")
        row = {
            "publisher": pub,
            "metric": metric,
            "value": value,
            "scale_max": scale,
            "votes": int(float(r["n"])) if r.get("n") else None,
            "as_of": r.get("t"),
        }
        k = (pub, metric)
        if k not in best or (row["as_of"] or "") > (best[k]["as_of"] or ""):
            best[k] = row
    return sorted(best.values(), key=lambda s: (s["publisher"], s["metric"]))


def box_rows(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        cur, scope = CURRENCY.get(r.get("u")), SCOPES.get(r.get("place") or "")
        if cur and scope and r["v"] > 0:
            out.append({"scope": scope, "amount": r["v"], "currency": cur})
    return out


def main() -> None:
    ev = Sources()
    seeds: dict[str, dict] = {}
    from mde.enrich.worklist import seed_files

    for f in seed_files():
        for w in json.loads(f.read_text())["works"]:
            seeds[w["slug"]] = w
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    wd_path, ol_path = ENRICHMENT / "wikidata.json", ENRICHMENT / "openlibrary.json"
    wd, ol = json.loads(wd_path.read_text()), json.loads(ol_path.read_text())
    added = {"wikidata": 0, "scores": 0, "box_office": 0, "pages": 0}
    for item in worklist():
        slug, qid = item["slug"], item["qid"]
        d = ev.dig.get(qid)
        w = seeds.get(slug)
        if not d or not w:
            continue
        ids = dict(d.get("ids") or {})
        ids.pop("website", None)
        if d.get("musicbrainz_rg"):
            ids["musicbrainz_release_group"] = d["musicbrainz_rg"]
        wikipedia = (
            f"https://en.wikipedia.org/wiki/{(d.get('enwiki') or item['wikipedia'] or '').replace(' ', '_')}"
            if (d.get("enwiki") or item["wikipedia"])
            else None
        )
        if slug not in wd["works"]:
            scores, box = score_rows(d.get("reviews") or []), box_rows(d.get("box_office") or [])
            rec = {
                "match": {"qid": qid, "confidence": 1.0, "reason": "Wikidata item recorded when the work was imported"},
                "facts": {},
                "ids": ids,
                "scores": scores,
                "box_office": box,
                "series": [],
                "follows": [],
                "followed_by": [],
                "based_on": [],
                "images": [],
                "wikipedia": wikipedia,
                "conflicts": [],
                "links": links_for({**w}, ids, wikipedia),
            }
            wd["works"][slug] = rec
            added["wikidata"] += 1
            added["scores"] += bool(scores)
            added["box_office"] += bool(box)
        if w["medium"] == "book" and slug not in ol["works"]:
            o = ev.by["openlibrary"].get(slug) or {}
            pages = o.get("pages") or d.get("pages")
            if pages and 20 <= pages <= 5000:
                key = (o.get("key") or "").rsplit("/", 1)[-1]
                ol["works"][slug] = {
                    "match": {
                        "key": o.get("key") or f"/works/{item['ids'].get('openlibrary', '')}",
                        "reason": "Open Library work id recorded with the Wikidata item",
                    },
                    "key": o.get("key"),
                    "facts": {"page_count": int(pages)},
                    "ids": {"openlibrary": key} if key else {},
                    "images": [],
                    "links": [],
                }
                added["pages"] += 1
    wd["generated_at"] = now
    wd_path.write_text(json.dumps(wd, ensure_ascii=False, indent=1) + "\n")
    ol_path.write_text(json.dumps(ol, ensure_ascii=False, indent=1) + "\n")
    print(added)
    _ = (pool, TEXT)


if __name__ == "__main__":
    main()
