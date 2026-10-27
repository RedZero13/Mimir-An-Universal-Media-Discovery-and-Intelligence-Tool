# Maintaining the catalogue

`python -m mde audit` checks everything the site is built from and writes a workbook for manual review.

```
cd api
python -m mde audit                       # data checks, writes audit-out/mimir-audit.xlsx and findings.md
node ../demo/build.cjs --site /tmp/site   # optional: build the site first,
python -m mde audit --site /tmp/site      # then also check pages, links, titles and the sitemap
python -m mde audit --only W003,B002      # selected rules; --fail-on warning for a strict run
```

The exit code is 1 when an error-level finding remains, so CI and `tests/test_audit.py` fail on new errors.

## The workbook
Sheets: Summary, Findings, Rules, Works (one row per work with its tags, credits, cover, gaps and finding count), Tags,
People, Franchises, Shelves, Days, YouTube, Audiobooks, Blog, and Pages (with `--site`). Every sheet has filters and a frozen
header. Without `openpyxl` the same sheets are written as CSV files in `audit-out/mimir-audit/`. The workbook is generated;
do not commit it.

## Rules
`api/mde/audit/rules.json` lists every rule (id, severity, scope, title, hint) and its parameters such as the earliest
plausible year or banned public strings. W = works, T = taxonomy, S = shelves, C = consistency across files, B = branding
and stale text, P = built pages. To add a rule, add its entry to `rules.json` and a `@check("ID")` function in
`api/mde/audit/engine.py`; the engine refuses a rule with no check.

## Accepting a finding on purpose
Add `{"rule": "W003", "key": "<the key the finding shows>", "reason": "why"}` to `accepted` in `api/mde/audit/baseline.json`.
Warnings and notes are expected to shrink over time as classification and summaries are filled in; errors must be zero.
