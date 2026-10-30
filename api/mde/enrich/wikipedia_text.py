"""Wikipedia lead text (REST summary) per work, used only as input to the tagger; never committed and never shown on the site.

    python -m mde.enrich.wikipedia_text        fetch what is missing (resumable); writes data/work-text/wikipedia.jsonl

The text is CC BY-SA, so it is read to understand a work (what it is about, how it feels) and not republished: the seed receives
tags and facts, and each work page links to the article it came from.
"""

from __future__ import annotations

import argparse
import urllib.parse

from mde.enrich import pool
from mde.enrich.worklist import TEXT, provenance, worklist

SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/{}?redirect=true"
OUT = TEXT / "wikipedia.jsonl"


def fetch(arg: tuple[str, str]) -> dict | None:
    title, qid = arg
    d = pool.get_json(SUMMARY.format(urllib.parse.quote(title.replace(" ", "_"), safe="()_,'!:-")), timeout=30)
    if not d or d.get("type") == "disambiguation":
        return None
    return {
        "title": d.get("title"),
        "description": d.get("description"),
        "extract": d.get("extract"),
        "wikibase_item": d.get("wikibase_item"),
        "match": d.get("wikibase_item") == qid,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    prov = provenance()
    ws = [w for w in worklist() if w["wikipedia"]]
    ws.sort(key=lambda w: (prov.get(w["slug"], {}).get("rank") or 0, w["slug"]))  # the best-known first: if the run is cut short, those are done
    items = [(w["qid"], (w["wikipedia"], w["qid"])) for w in ws]
    pool.run(items[: a.limit] if a.limit else items, fetch, OUT, workers=3, min_gap=0.3)


if __name__ == "__main__":
    main()
