"""CLI: python -m mde {migrate,seed,setup,discover,ingest,benchmark,audit}"""

from __future__ import annotations

import argparse
import json
import sys

from mde import db
from mde.catalogue.load import ValidationFailed, load_seed
from mde.migrate import migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mde")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply pending database migrations")
    sub.add_parser("seed", help="import the pilot catalogue (idempotent)")
    sub.add_parser("setup", help="migrate + seed")
    d = sub.add_parser("discover", help="run a discovery query and print the results")
    d.add_argument("query")
    d.add_argument("--json", action="store_true")
    i = sub.add_parser("ingest", help="fetch open data for seed works into mde/data/enrichment/")
    i.add_argument("--source", action="append", choices=["wikidata", "openlibrary", "musicbrainz", "tmdb"])
    i.add_argument("--offline", action="store_true", help="use only the local HTTP cache")
    b = sub.add_parser("benchmark", help="run the discovery benchmark")
    b.add_argument("--json", action="store_true")
    sub.add_parser("audit", help="run the catalogue audit and write the verification workbook (see docs/MAINTENANCE.md)", add_help=False)
    args, rest = parser.parse_known_args(argv)

    if args.cmd == "audit":
        from mde.audit.__main__ import main as audit_main
        return audit_main(rest)
    if rest:
        parser.error(f"unrecognised arguments: {' '.join(rest)}")

    if args.cmd == "ingest":
        from mde.ingest.run import SOURCES, SourceUnavailable, run
        try:
            for source, path in run(tuple(args.source or SOURCES), offline=args.offline).items():
                print(f"{source}: wrote {path}")
        except SourceUnavailable as e:
            print(f"not written: {e}", file=sys.stderr)
            return 2
        return 0

    with db.connect() as conn:
        if args.cmd in ("migrate", "setup"):
            applied = migrate(conn)
            print(f"migrations applied: {applied or 'none pending'}")
        if args.cmd in ("seed", "setup"):
            try:
                stats = load_seed(conn)
            except ValidationFailed as e:
                print(e, file=sys.stderr)
                return 1
            print(f"seed: {stats.works_inserted} inserted, {stats.works_updated} updated, "
                  f"{stats.works_unchanged} unchanged, {stats.classifications} classifications, "
                  f"{stats.relationships} relationships")
            for w in stats.warnings:
                print(f"warning: {w}", file=sys.stderr)
        if args.cmd == "discover":
            from mde.discovery.engine import discover
            resp = discover(conn, args.query, log=False).to_dict()
            if args.json:
                print(json.dumps(resp, indent=2, default=str))
            else:
                for note in resp["interpretation"]["notes"]:
                    print(f"  · {note}")
                for i, r in enumerate(resp["results"], 1):
                    print(f"{i}. {r['title']} ({r['medium']}, {r['year']}) score={r['score']:.3f}")
                    print(f"   {r['headline']}")
                    for c in r["caveats"]:
                        print(f"   ! {c}")
        if args.cmd == "benchmark":
            from benchmark.run import print_report, run_benchmark
            report = run_benchmark(conn)
            print(json.dumps(report, indent=2) if args.json else print_report(report))
            return 0 if report["summary"]["failed"] == 0 else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
