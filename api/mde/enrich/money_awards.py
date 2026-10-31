# ruff: noqa: E501
"""Budgets and awards from Wikidata (CC0) for every work with a Wikidata item, through the query service in batches.

    python -m mde.enrich.money_awards          fetch into data/work-facts/money-awards.jsonl (resumable), then write them into data/enrichment/wikidata.json

Budget is Wikidata's "cost" (P2130, what most film items use) or "budget" (P2769). Awards are "award received" (P166) and
"nominated for" (P1411), each with its year where the item records one. Only names and years are kept; nothing is fetched from
the award pages themselves.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from mde.enrich.apply import CURRENCY
from mde.enrich.worklist import FACTS, MDE

OUT = FACTS / "money-awards.jsonl"
ENRICHMENT = MDE / "data" / "enrichment" / "wikidata.json"
ENDPOINT = "https://query.wikidata.org/sparql"
UA = "MimirCatalogue/0.1 (https://mimir.terratalesmedia.world; hello@terratalesmedia.world)"

MONEY = """SELECT ?item ?prop ?amount ?unit WHERE {
  VALUES ?item { %s }
  VALUES ?prop { "cost" "budget" }
  { ?item p:P2130/psv:P2130 [ wikibase:quantityAmount ?amount; wikibase:quantityUnit ?unit ] . BIND("cost" AS ?p2) }
  UNION { ?item p:P2769/psv:P2769 [ wikibase:quantityAmount ?amount; wikibase:quantityUnit ?unit ] . BIND("budget" AS ?p2) }
  FILTER(?prop = ?p2)
}"""
AWARDS = """SELECT ?item ?kind ?award ?awardLabel ?year WHERE {
  VALUES ?item { %s }
  { ?item p:P166 ?st . ?st ps:P166 ?award . BIND("won" AS ?kind) } UNION { ?item p:P1411 ?st . ?st ps:P1411 ?award . BIND("nominated" AS ?kind) }
  OPTIONAL { ?st pq:P585 ?t . BIND(YEAR(?t) AS ?year) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}"""


def sparql(query: str, tries: int = 5) -> list[dict]:
    data = urllib.parse.urlencode({"query": query}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(ENDPOINT, data=data, headers={"Accept": "application/sparql-results+json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)["results"]["bindings"]
        except Exception as e:  # noqa: BLE001 - the service throttles and times out under load; back off and retry
            wait = 10 * (i + 1)
            print(f"  retry in {wait}s: {e}")
            time.sleep(wait)
    raise RuntimeError("query service unavailable")


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def fetch(qids: list[str], batch: int = 150) -> None:
    done = set()
    if OUT.exists():
        done = {json.loads(line)["qid"] for line in OUT.open()}
    todo = [q for q in qids if q not in done]
    print(f"{len(todo)} of {len(qids)} items to fetch")
    with OUT.open("a") as f:
        for i in range(0, len(todo), batch):
            chunk = todo[i : i + batch]
            values = " ".join(f"wd:{q}" for q in chunk)
            rec = {q: {"qid": q, "budget": [], "won": [], "nominated": []} for q in chunk}
            for b in sparql(MONEY % values):
                cur = CURRENCY.get(qid(b["unit"]["value"]))
                amt = float(b["amount"]["value"])
                if cur and amt > 0:
                    rec[qid(b["item"]["value"])]["budget"].append({"amount": amt, "currency": cur, "from": b["prop"]["value"]})
            for b in sparql(AWARDS % values):
                name = b.get("awardLabel", {}).get("value", "")
                if not name or name.startswith("Q") and name[1:].isdigit():
                    continue
                row = {"name": name, "year": int(b["year"]["value"]) if b.get("year") else None}
                lst = rec[qid(b["item"]["value"])][b["kind"]["value"]]
                if row not in lst:
                    lst.append(row)
            for r in rec.values():
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  {min(i + batch, len(todo))}/{len(todo)}")
            time.sleep(1.5)


def newest_first(a: dict) -> tuple:
    return (-(a["year"] or 0), a["name"])


def write() -> dict:
    wd = json.loads(ENRICHMENT.read_text())
    got = {}
    for line in OUT.open():
        r = json.loads(line)
        got[r["qid"]] = r
    stats = {"budget": 0, "awards": 0}
    for rec in wd["works"].values():
        r = got.get((rec.get("match") or {}).get("qid"))
        if not r:
            continue
        # One budget per currency: "cost" first (what film items use), then "budget"; the largest figure where several are listed.
        best: dict[str, dict] = {}
        for b in sorted(r["budget"], key=lambda b: (b["from"] != "cost", -b["amount"])):
            best.setdefault(b["currency"], {"amount": b["amount"], "currency": b["currency"]})
        if best:
            rec["budget"] = list(best.values())
            stats["budget"] += 1
        else:
            rec.pop("budget", None)
        won = sorted(r["won"], key=newest_first)[:40]
        won_names = {a["name"] for a in won}
        nom = sorted([a for a in r["nominated"] if a["name"] not in won_names], key=newest_first)[:40]
        if won or nom:
            rec["awards"] = {"won": won, "nominated": nom}
            stats["awards"] += 1
        else:
            rec.pop("awards", None)
    ENRICHMENT.write_text(json.dumps(wd, ensure_ascii=False, indent=1) + "\n")
    return stats


def main() -> None:
    wd = json.loads(ENRICHMENT.read_text())
    qids = sorted({q for rec in wd["works"].values() if (q := (rec.get("match") or {}).get("qid"))})
    fetch(qids)
    print(write())


if __name__ == "__main__":
    main()
