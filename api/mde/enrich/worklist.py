"""The works to enrich: everything imported from Wikidata (seed/reference-*.json) and the 2025-26 batch (seed/recent.json)."""

from __future__ import annotations

import glob
import json
import urllib.parse
from functools import lru_cache
from pathlib import Path

MDE = Path(__file__).resolve().parent.parent
SEED = MDE / "seed"
DATA = MDE / "data"
FACTS = DATA / "work-facts"  # derived facts, committed
TEXT = DATA / "work-text"  # third-party text used only as tagger input, not committed


def seed_files() -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(SEED / "reference-*.json"))) + [SEED / "recent.json"]


@lru_cache(maxsize=1)
def provenance() -> dict[str, dict]:
    return json.loads((MDE / "catalogue" / "reference-provenance.json").read_text())["works"]


def worklist() -> list[dict]:
    """[{slug, medium, year, qid, wikipedia (title or None), ids}] for every work to enrich."""
    prov = provenance()
    out = []
    for f in seed_files():
        for w in json.loads(f.read_text())["works"]:
            p = prov.get(w["slug"]) or {}
            qid = p.get("qid") or (w.get("attributes") or {}).get("wikidata")
            if not qid:
                continue
            url = p.get("wikipedia") or ""
            title = urllib.parse.unquote(url.rsplit("/wiki/", 1)[1]) if "/wiki/" in url else None
            out.append(
                {
                    "slug": w["slug"],
                    "medium": w["medium"],
                    "year": w.get("year"),
                    "qid": qid,
                    "wikipedia": title,
                    "ids": p.get("ids") or {},
                    "seed_file": f.name,
                }
            )
    return out
