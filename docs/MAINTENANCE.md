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

## Adding YouTube channels
```
cd api
python -m mde.ingest.youtube_channels @handle1 @handle2 --out channels.json
```
reads each channel's public page and RSS feed: channel id, name, joined year, the creator's own description, and the newest
videos with id, title, publish date and views. A handle that does not resolve is reported and left out. Write the summary and
tags by hand into a seed file (see `api/mde/seed/youtube-more.json`), add each channel and video to
`api/mde/data/enrichment/youtube.json` with its ids and thumbnail, and run `pytest tests/test_youtube_data.py`. Leave
`advisories` out unless the content has been assessed: the site then shows "not assessed". Never write a video id from memory.

## Files for crawlers and answer engines
`node demo/build.cjs --site DIR` writes `sitemap.xml` (an index) with `sitemap-pages.xml` and one `sitemap-works-<type>.xml`
per medium, `robots.txt`, `llms.txt` and `llms-full.txt` (code in `demo/discovery.cjs`). robots.txt allows every crawler,
search and AI assistants alike. To opt out of model training only, change the training crawlers listed in `ALLOWED` in
that file to `Disallow: /`. After deploying, submit `https://mimir.terratalesmedia.world/sitemap.xml` in Google Search Console
and Bing Webmaster Tools.

## Keeping the catalogue current (2025 onwards)
`python -m mde.ingest.recent` asks Wikidata (SPARQL, CC0) for the most widely covered works released since 1 January 2025, up to
140 films, 90 series and 70 each of games, albums and books per year, and writes `api/mde/seed/recent.json`. Ranking is by the
number of Wikipedia editions covering a work. Titles, years, credits, countries, genres and runtimes are Wikidata's; the summary is
Wikidata's one-line description plus credits; no parents' guide, mood or theme is claimed, so audit warnings W011 and W012 list
these works until they are assessed. Titles that are only an everyday word are skipped (`COLLIDES`). Needs
`query.wikidata.org` and `www.wikidata.org` on the network allowlist. Re-run it every few months and review the diff; works
already in the catalogue are never duplicated. Books for 2026 returned nothing on the last run (the ranked query timed out):
re-run to retry. The first run added 650 works (102 + 118 films, 90 + 90 series, 53 + 39 games, 70 + 70 albums, 19 books).
