"""python -m mde.audit: see mde/audit/__init__.py."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mde.audit.engine import SEVERITIES, Finding, load_baseline, load_context, markdown_report, run_audit, write_workbook


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mde audit", description="Run the catalogue audit and write the verification workbook.")
    ap.add_argument("--out", type=Path, default=Path("audit-out"), help="where to write the workbook and report (default: audit-out)")
    ap.add_argument("--site", type=Path, help="a built site (node demo/build.cjs --site DIR) to check pages, links and the sitemap")
    ap.add_argument("--only", help="comma-separated rule ids")
    ap.add_argument("--baseline", type=Path, help="accepted findings (default: mde/audit/baseline.json)")
    ap.add_argument("--fail-on", choices=["error", "warning"], default="error", help="exit 1 if a finding of this severity or worse remains")
    ap.add_argument("--fix-hints", action="store_true", help="print each rule's hint in the report")
    ap.add_argument("--no-workbook", action="store_true")
    a = ap.parse_args(argv)
    ctx = load_context(a.site)
    ctx, findings = run_audit(ctx, set(a.only.split(",")) if a.only else None, load_baseline(a.baseline))
    a.out.mkdir(parents=True, exist_ok=True)
    report = markdown_report(findings, a.fix_hints)
    (a.out / "findings.md").write_text(report)
    if not a.no_workbook:
        print("workbook:", write_workbook(ctx, findings, a.out))
    print(report if len(report) < 6000 else report[:6000] + "\n…(see findings.md)")
    worst = min((SEVERITIES[f.severity] for f in findings), default=9)
    return 1 if worst <= SEVERITIES[a.fail_on] else 0


def run(findings: list[Finding]) -> int:   # pragma: no cover - convenience for tests
    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
