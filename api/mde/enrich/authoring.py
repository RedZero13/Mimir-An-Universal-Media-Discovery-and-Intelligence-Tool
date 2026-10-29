# ruff: noqa: E501
"""The hand-written layer: original summaries and full tag sets for the best-known imported works, to the pilot's standard.

    python -m mde.enrich.authoring next 30        print the next 30 works to write up (best known first), with the facts to ground them
    python -m mde.enrich.authoring check          validate every file in authored/ (terms exist and fit the medium, summaries are original length)
    python -m mde.enrich.authoring stats          how many works are covered

authored/NNN.jsonl holds one JSON object per line: {"slug", "summary", "terms": {"theme:grief-loss": 0.9, ...}}. `apply` merges these into the seed:
the summary fills an empty or stub summary, and the terms replace the machine-inferred non-genre terms (genre terms are kept and extended).
Summaries are written fresh from knowledge of the work, in the pilot's voice: one or two sentences, premise without spoilers, no copied wording.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mde.enrich import pool, tagger
from mde.enrich.worklist import MDE, provenance, seed_files, worklist

AUTHORED = Path(__file__).resolve().parent / "authored"
STUB = ("More details are not in the catalogue yet", " series. Directed by", " film directed by", " film by ", "Starring ", "television series.")


def authored() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(AUTHORED.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["slug"]] = r
    return out


def is_stub(summary: str | None) -> bool:
    return not summary or any(s in summary for s in STUB) or len(summary.split()) < 12


def priority(ev, w: dict) -> tuple:
    d = ev.dig.get(w["qid"]) or {}
    has_text = w["qid"] in ev.wp
    return (0 if has_text else 1, -(d.get("sitelinks") or 0), provenance().get(w["slug"], {}).get("rank") or 9999, w["slug"])


def next_batch(n: int) -> list[str]:
    from mde.enrich.apply import Sources

    ev = Sources()
    done = authored()
    seeds = {}
    for f in seed_files():
        for w in json.loads(f.read_text())["works"]:
            seeds[w["slug"]] = w
    todo = [w for w in worklist() if w["slug"] not in done]
    todo.sort(key=lambda w: priority(ev, w))
    lines = []
    for w in todo[:n]:
        s = seeds[w["slug"]]
        d = ev.dig.get(w["qid"]) or {}
        wp = ev.wp.get(w["qid"]) or {}
        credits = "; ".join(f"{c[0]}: {c[1]}" for c in s.get("credits", [])[:6])
        genres = ", ".join(k.split(":", 1)[1] for k in s.get("terms", {}) if k.startswith("genre:"))
        extra = []
        tv = ev.by["tvmaze"].get(w["slug"]) or {}
        st = ev.by["steam"].get(w["slug"]) or {}
        ol = ev.by["openlibrary"].get(w["slug"]) or {}
        if tv.get("summary"):
            extra.append("tvmaze: " + tv["summary"][:260])
        if st.get("description"):
            extra.append("steam: " + st["description"][:260])
        if ol.get("subjects"):
            extra.append("subjects: " + ", ".join(ol["subjects"][:10]))
        lines.append(
            f"{w['slug']} | {s['title']} ({s.get('year')}) {s['medium']} | {credits} | genres: {genres}\n    {(wp.get('extract') or d.get('description') or '')[:420]}"
            + ("".join("\n    " + e for e in extra))
        )
    return lines


def check() -> int:
    tax = tagger.taxonomy()
    seeds = {}
    for f in seed_files():
        for w in json.loads(f.read_text())["works"]:
            seeds[w["slug"]] = w
    bad = 0
    seen: set[str] = set()
    for f in sorted(AUTHORED.glob("*.jsonl")):
        for i, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except ValueError as e:
                print(f"{f.name}:{i} not JSON: {e}")
                bad += 1
                continue
            slug = r.get("slug")
            w = seeds.get(slug)
            if not w:
                print(f"{f.name}:{i} unknown work {slug}")
                bad += 1
                continue
            if slug in seen:
                print(f"{f.name}:{i} duplicate {slug}")
                bad += 1
            seen.add(slug)
            n = len((r.get("summary") or "").split())
            if not 8 <= n <= 45:
                print(f"{f.name}:{i} {slug}: summary has {n} words")
                bad += 1
            for k, v in (r.get("terms") or {}).items():
                if k not in tax or k.startswith("advisory:"):
                    print(f"{f.name}:{i} {slug}: unknown or disallowed term {k}")
                    bad += 1
                elif not (tagger.applies(k, w["medium"])):
                    print(f"{f.name}:{i} {slug}: {k} does not apply to {w['medium']}")
                    bad += 1
                elif not isinstance(v, (int, float)) or not 0 < v <= 1:
                    print(f"{f.name}:{i} {slug}: bad strength for {k}")
                    bad += 1
            if len([k for k in (r.get("terms") or {}) if not k.startswith("genre:")]) < 6:
                print(f"{f.name}:{i} {slug}: fewer than 6 non-genre terms")
                bad += 1
    print(f"{len(seen)} works checked, {bad} problems")
    return bad


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "next":
        print("\n".join(next_batch(int(sys.argv[2]) if len(sys.argv) > 2 else 25)))
    elif cmd == "check":
        sys.exit(1 if check() else 0)
    else:
        a = authored()
        print(f"{len(a)} works authored of {len(worklist())}")


if __name__ == "__main__":
    main()
    _ = (pool, MDE)
