# Search Console findings and fixes (27 October 2026)

Source: five Coverage drill-down exports for the domain property `terratalesmedia.world` (which covers the main site and
`mimir.terratalesmedia.world`), exported 27 October 2026, with data to 23 October.

| Issue | Pages | What they are | Verdict | Action |
|---|---|---|---|---|
| Page with redirect | 3 | `http://` and `www.` versions of the home page | Correct: they redirect to `https://terratalesmedia.world/` | None. Google lists redirects as "not indexed" by design |
| Not found (404) | 3 | Old `?page_id=` addresses. 123 and 124 now 301 to the privacy and terms pages; `?page_id=4` is a deleted page | Harmless; Google drops them | None. Optionally Validate Fix after the next crawl |
| Duplicate, Google chose a different canonical | 9 | WordPress **attachment pages**: one automatic page per uploaded image, for example `/terratales-media-entertainment-6a2ee4dfc0765/` (the media library holds 28 files) | A real, fixable problem: thin duplicate pages competing with the real ones | **Fixed by the Terratales Indexing Fixes plugin** (below) |
| Crawled, currently not indexed | 133 | 121 Mimir work pages and 6 shelf pages; the Terratales privacy and terms pages; the feed; two more attachment pages | Mixed: see below | Plugin for attachments and the feed; richer Mimir pages; time |
| Excluded by `noindex` | 7 | Mimir work pages with no summary yet | Intended: pages without a summary stay out of search until they have one | None |

The Terratales site itself is healthy: all 18 published pages return 200, carry no `noindex`, have a canonical link, a unique title and
description and one H1, and are in `sitemap-1.xml`. Nothing on it blocks indexing.

## What "crawled, currently not indexed" means for the Mimir pages
Google fetched them and chose not to index them yet. It is common for a new domain that suddenly publishes hundreds of similar pages
(the count rose from 5 to 133 on 20 October, the day the catalogue pages went live). It is a judgement about value, not an error,
and no setting forces it. What helps, in order:
1. **More unique content per page.** Work pages now also carry a parents' guide section (the assessed levels, or a plain "not
   assessed" notice) and "more like this" lists, one set from the same medium and one from other media, with the qualities they
   share. These are unique to each work and link the catalogue together.
2. **Internal links.** Work pages link to their franchise page; franchise, tag, tool, day and help pages link back; the home page's
   crawl block links every section.
3. **Links from outside.** Link to Mimir from `terratalesmedia.world` and from profiles (LinkedIn, GitHub, YouTube) with the
   descriptive anchor "Mimir, a media discovery guide". Google weighs a new site by who points to it.
4. **Patience, and do not resubmit in bulk.** Request indexing only for key pages (home, `/films/`, `/franchises/`, `/tools/`,
   `/help/`, a few franchise pages). Indexing of the rest follows as the site earns trust, usually over weeks.

The privacy and terms pages being "crawled, not indexed" is normal: Google often skips boilerplate legal pages. No action.

## The Terratales Indexing Fixes plugin (`wordpress/terratales-indexing/`)
One file, no settings, no database. Install it the same way as Mimir Vault (`docs/ACCOUNTS.md`): build with
`python3 wordpress/build.py`, then upload `wordpress/dist/terratales-indexing.zip` (Plugins, Add New, Upload Plugin), or paste
`terratales-indexing-snippet.php` into Code Snippets. It:
- **Redirects attachment pages** (301) to the image file itself, which removes the 9 duplicates and the 2 attachment pages in
  "crawled, not indexed" once Google recrawls them.
- **Marks feeds `noindex`** (`X-Robots-Tag`), so `/feed/` stops being listed.
- **Adds a canonical link to the home page**, which had none, and **Organization and WebSite data** whose `@id`
  (`https://terratalesmedia.world/#org`) is the one the Mimir pages already reference, so Google can connect the two sites.

After installing: in Search Console open each issue above and press **Validate fix**. Check
`https://terratalesmedia.world/terratales-media-entertainment-6a2ee4dfc0765/` redirects to the image.

## The sitemap
Nothing is missing. Jetpack writes `sitemap.xml` (an index) and `sitemap-1.xml` with all 18 published pages and refreshes them when
you publish; attachment pages are correctly not in it. Leave it as it is, and make sure `https://terratalesmedia.world/sitemap.xml`
is submitted under Sitemaps. The `news-sitemap.xml` Jetpack adds lists only the home page and is meant for news publishers; it is
harmless. The four draft pages (Home, Test, The Akashic Records, and one with unrelated text) stay out until published; delete the
unused ones in WordPress if you do not want them. Mimir's own sitemaps (`https://mimir.terratalesmedia.world/sitemap.xml`, an
index split by section) are rebuilt on every deploy. The domain property means one Search Console login covers both.

## Structured data (schema.org) on every page

**Mimir** (built by `demo/build.cjs`): every static page carries one JSON-LD graph, tied to the Mimir `WebSite` and to the Terratales `Organization` (`https://terratalesmedia.world/#org`).

| Pages | Types |
| --- | --- |
| Work pages | `ItemPage` + the work's own type (`Movie`, `TVSeries`, `Book`, `VideoGame`, `MusicAlbum`, `VideoObject`, `CreativeWorkSeries`) + `BreadcrumbList` |
| Category hubs (`/films/` …) | `CollectionPage` with an `ItemList` + `BreadcrumbList` |
| Shelves, franchises, tags, people, days, help categories, indexes | `CollectionPage` (+ `ItemList`) + `BreadcrumbList` |
| Help guides, legal pages | `WebPage` + `BreadcrumbList` (legal pages carry `dateModified`) |
| Tools | `WebPage` + `WebApplication` (free) + `BreadcrumbList`; help index also `FAQPage` |
| About | `AboutPage` + `BreadcrumbList` |
| Blog | `Blog` index; posts `BlogPosting` + `BreadcrumbList` |
| Home | `WebSite` (with search action), `WebApplication`, `Organization` |
| 404 | none (noindex) |

Audit rule **P006** fails the build's page audit if an indexable page has invalid JSON-LD, no WebPage-family node, or (below the home page) no `BreadcrumbList`.

**terratalesmedia.world** (the *Terratales Indexing Fixes* plugin, 0.2.0): the home page gets `Organization`, `WebSite` and `WebPage`; every other page, post or realm page gets a WebPage-family node (About → `AboutPage`, Contact → `ContactPage`, Realms/Projects/Press → `CollectionPage`, posts → `Article`, the rest `WebPage`), a `BreadcrumbList`, and the six realm pages (Cinema, Music & Sound, OTT & Streaming, Events & Celebrity Management, Anime & Manga, Publishing) also a `Service` provided by the organization. Names and descriptions come only from each page's own title and excerpt; nothing is invented. Check a page with Google's Rich Results Test or the Schema Markup Validator after installing the new zip.
