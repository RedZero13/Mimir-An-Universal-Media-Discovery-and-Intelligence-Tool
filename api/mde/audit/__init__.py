"""Catalogue audit: a rule engine over everything the site is built from, and a workbook for checking it by hand.

    python -m mde audit [--out DIR] [--site DIR] [--only RULE,...] [--fail-on error|warning] [--fix-hints]

The JSON and seed files stay the source of truth; the workbook is a read-only view of them (see docs/MAINTENANCE.md).
"""

from mde.audit.engine import Finding, load_rules, run_audit

__all__ = ["Finding", "load_rules", "run_audit"]
