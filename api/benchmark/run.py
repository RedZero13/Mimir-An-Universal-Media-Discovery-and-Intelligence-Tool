"""Runs the discovery benchmark: hard checks per query, plus precision@5 and hit@3 against editorial judgements."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import psycopg

QUERIES_PATH = Path(__file__).parent / "queries.json"


def _check(name: str, arg, resp: dict, by_slug: dict) -> str | None:
    results = resp["results"]
    slugs = [r["slug"] for r in results]
    intent = resp["interpretation"]
    if name == "all_media":
        bad = [r["slug"] for r in results if r["medium"] not in arg]
        return f"wrong medium: {bad}" if bad else None
    if name == "must_not_media":
        bad = [r["slug"] for r in results if r["medium"] in arg]
        return f"excluded medium present: {bad}" if bad else None
    if name == "must_not_include":
        bad = [s for s in slugs if s in arg]
        return f"must not include: {bad}" if bad else None
    if name == "top_k_includes_any":
        return None if set(slugs[: arg["k"]]) & set(arg["slugs"]) else f"none of {arg['slugs']} in top {arg['k']}: {slugs[: arg['k']]}"
    if name == "top_k_includes_all":
        missing = set(arg["slugs"]) - set(slugs[: arg["k"]])
        return f"missing from top {arg['k']}: {sorted(missing)}" if missing else None
    if name == "min_results":
        return None if len(results) >= arg else f"{len(results)} results < {arg}"
    if name == "max_results":
        return None if len(results) <= arg else f"{len(results)} results > {arg}: {slugs}"
    if name == "all_languages":
        bad = [s for s in slugs if by_slug[s]["language"] not in arg]
        return f"wrong language: {bad}" if bad else None
    if name == "year_range":
        bad = [r["slug"] for r in results if not arg[0] <= r["year"] <= arg[1]]
        return f"outside years: {bad}" if bad else None
    if name == "max_minutes_hard":
        bad = [s for s in slugs if (by_slug[s]["minutes"] or 0) > arg]
        return f"over {arg} min: {bad}" if bad else None
    if name == "length_soft":
        length = intent.get("length")
        return None if length and not length["hard"] else "length should be a soft preference"
    if name == "first_has_relationship":
        return None if results and any(x["kind"] == "relationship" for x in results[0]["reasons"]) else "first result has no relationship reason"
    if name == "min_distinct_media_top3":
        n = len({r["medium"] for r in results[:3]})
        return None if n >= arg else f"only {n} media in top 3"
    if name == "intent_prefers":
        got = {p["term"] for p in intent["preferences"]}
        missing = set(arg) - got
        return f"parser missed preferences {sorted(missing)}" if missing else None
    if name == "intent_avoids":
        got = {a["term"] for a in intent["avoid"]}
        missing = set(arg) - got
        return f"parser missed avoidances {sorted(missing)}" if missing else None
    if name == "no_reference":
        return f"treated {intent['reference_phrase']!r} as a reference" if intent.get("reference_slug") else None
    if name == "unassessed_have_caveat":
        bad = [r["slug"] for r in results
               if arg not in by_slug[r["slug"]]["assessed"] and not any("Not yet assessed" in c for c in r["caveats"])]
        return f"missing 'not yet assessed' caveat: {bad}" if bad else None
    return f"unknown check {name!r}"


def run_benchmark(conn: psycopg.Connection, path: Path = QUERIES_PATH) -> dict:
    """Against PostgreSQL (full-text search, stored catalogue)."""
    from mde.discovery.engine import discover

    by_slug = {
        r["slug"]: {"language": r["original_language"],
                    "minutes": r["runtime_minutes"] or (float(r["playtime_hours"]) * 60 if r["playtime_hours"] else None),
                    "assessed": set(r["assessed"])}
        for r in conn.execute(
            "SELECT w.slug, w.original_language, w.runtime_minutes, w.playtime_hours, "
            "coalesce(array_agg(t.dimension || ':' || t.slug) FILTER (WHERE t.dimension = 'advisory'), '{}') AS assessed "
            "FROM work w LEFT JOIN classification c ON c.work_id = w.id LEFT JOIN taxonomy_term t ON t.id = c.term_id "
            "GROUP BY w.id").fetchall()
    }
    return evaluate(lambda q: discover(conn, q, limit=8, log=False).to_dict(), by_slug, path)


def run_benchmark_offline(path: Path = QUERIES_PATH) -> dict:
    """Against the in-memory catalogue the browser demo uses."""
    from mde.catalogue.memory import MemoryCatalogue

    cat = MemoryCatalogue.from_seed()
    by_slug = {w.slug: {"language": w.language, "minutes": w.length_minutes,
                        "assessed": {k for k in w.terms if k.startswith("advisory:")}} for w in cat.works}
    return evaluate(lambda q: cat.discover(q, limit=8).to_dict(), by_slug, path)


def evaluate(discover_fn: Callable[[str], dict], by_slug: dict, path: Path = QUERIES_PATH) -> dict:
    spec = json.loads(path.read_text())
    rows = []
    for q in spec["queries"]:
        resp = discover_fn(q["query"])
        slugs = [r["slug"] for r in resp["results"]]
        failures = [f"{name}: {msg}" for name, arg in q["checks"].items() if (msg := _check(name, arg, resp, by_slug))]
        relevant = set(q["relevant"])
        top5 = slugs[:5]
        precision = (len(set(top5) & relevant) / len(top5)) if top5 else (1.0 if not relevant else 0.0)
        hit3 = bool(set(slugs[:3]) & relevant) if relevant else not slugs
        rows.append({"id": q["id"], "category": q["category"], "query": q["query"], "results": slugs,
                     "precision_at_5": round(precision, 3), "hit_at_3": hit3, "failures": failures})
    n = len(rows)
    return {
        "summary": {
            "queries": n,
            "passed": sum(1 for r in rows if not r["failures"]),
            "failed": sum(1 for r in rows if r["failures"]),
            "mean_precision_at_5": round(sum(r["precision_at_5"] for r in rows) / n, 3),
            "hit_rate_at_3": round(sum(r["hit_at_3"] for r in rows) / n, 3),
        },
        "queries": rows,
    }


def print_report(report: dict) -> str:
    lines = []
    for r in report["queries"]:
        status = "PASS" if not r["failures"] else "FAIL"
        lines.append(f"[{status}] {r['id']:<32} P@5={r['precision_at_5']:.2f} hit@3={'y' if r['hit_at_3'] else 'n'}  "
                     f"{', '.join(r['results'][:5])}")
        for f in r["failures"]:
            lines.append(f"        - {f}")
    s = report["summary"]
    lines.append(f"\n{s['passed']}/{s['queries']} passed · mean P@5 {s['mean_precision_at_5']} · hit@3 {s['hit_rate_at_3']}")
    return "\n".join(lines)
