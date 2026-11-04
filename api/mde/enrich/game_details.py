# ruff: noqa: E501
"""Developers, publishers, platforms, game modes and engines for every game, from Wikidata (CC0), through the query service in batches.

    python -m mde.enrich.game_details          fetch into data/work-facts/game-details.jsonl (resumable), then write them into data/enrichment/wikidata.json

Each game record gets `game: {developers, publishers, platforms, modes, engines}` (names only, in Wikidata's order). The site shows them in a
"Game details" panel and the comparison tool can line them up.
"""

from __future__ import annotations

import json
import time

from mde.enrich.money_awards import ENRICHMENT, qid, sparql
from mde.enrich.worklist import FACTS

OUT = FACTS / "game-details.jsonl"
PROPS = {"P178": "developers", "P123": "publishers", "P400": "platforms", "P404": "modes", "P408": "engines"}
QUERY = """SELECT ?item ?prop ?val ?valLabel WHERE {
  VALUES ?item { %s }
  VALUES ?prop { %s }
  ?item ?p ?val . FILTER(?p = ?prop)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def fetch(qids: list[str], batch: int = 120) -> None:
    done = set()
    if OUT.exists():
        done = {json.loads(line)["qid"] for line in OUT.open()}
    todo = [q for q in qids if q not in done]
    print(f"{len(todo)} of {len(qids)} games to fetch")
    props = " ".join(f"wdt:{p}" for p in PROPS)
    with OUT.open("a") as f:
        for i in range(0, len(todo), batch):
            chunk = todo[i : i + batch]
            rec = {q: {"qid": q, **{v: [] for v in PROPS.values()}} for q in chunk}
            for b in sparql(QUERY % (" ".join(f"wd:{q}" for q in chunk), props)):
                name = b.get("valLabel", {}).get("value", "")
                if not name or (name.startswith("Q") and name[1:].isdigit()):
                    continue
                lst = rec[qid(b["item"]["value"])][PROPS[b["prop"]["value"].rsplit("/", 1)[-1]]]
                if name not in lst:
                    lst.append(name)
            for r in rec.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(i + batch, len(todo))}/{len(todo)}")
            time.sleep(1.5)


def write() -> int:
    wd = json.loads(ENRICHMENT.read_text())
    got = {}
    for line in OUT.open():
        r = json.loads(line)
        got[r["qid"]] = r
    n = 0
    for rec in wd["works"].values():
        r = got.get((rec.get("match") or {}).get("qid"))
        if not r:
            continue
        game = {k: r[k][:8] for k in PROPS.values() if r[k]}
        if game:
            rec["game"] = game
            n += 1
        else:
            rec.pop("game", None)
    ENRICHMENT.write_text(json.dumps(wd, ensure_ascii=False, indent=1) + "\n")
    return n


def main() -> None:
    from mde.enrich.worklist import worklist

    games = {w["qid"] for w in worklist() if w["medium"] == "game"}
    fetch(sorted(q for q in games if q))
    print({"games with details": write()})


if __name__ == "__main__":
    main()
