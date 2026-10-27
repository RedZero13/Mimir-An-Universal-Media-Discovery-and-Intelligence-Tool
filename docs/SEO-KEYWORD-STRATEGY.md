# Mimir SEO keyword strategy

## Implementation status (27 October 2026)

Search Console's first coverage findings and what was done about them are in [TERRATALES-INDEXING.md](TERRATALES-INDEXING.md).

**Done in the site build (`node demo/build.cjs --site DIR`)**
- Real, crawlable URLs with a title, description, canonical, one H1, breadcrumbs and an internal-link path from the home page:
  307 franchise and series pages (`/franchises/`, every medium in release order, time to finish, ItemList data), 245 tag pages
  (`/tags/`), 400 people pages (`/people/`), the Help centre with its 21 guides and FAQPage data (`/help/`), nine tool pages
  (`/tools/`), 50 days of the year (`/days/`), About, plus the existing work, medium, shelf and blog pages.
- Meta map applied: hub titles as in section 4, shelf titles led by a plain-language phrase (`phrase` in `shelves.json`), work
  titles "{Title} ({year}): similar {medium}, parents' guide" **only where a parents' guide has been assessed**, franchise
  titles "{IP} in order". Works with no summary stay `noindex`.
- Structured data: WebSite with SearchAction, Organization with sameAs (GitHub; add LinkedIn and YouTube when they exist),
  Movie/TVSeries/Book/VideoGame/MusicAlbum on work pages without ratings, ItemList on shelves, franchises, tags, people and days,
  BreadcrumbList everywhere, FAQPage on the Help centre.
- Sitemap index split by section (`sitemap-works-*.xml`, `franchises`, `tags`, `people`, `help`, `tools`, `days`, `shelves`,
  `blog`, `pages`), `robots.txt` allowing every crawler, `llms.txt` and `llms-full.txt`.
- Claims reviewed: see "Claims check" below.

**Not done yet**
- "Like X" blocks on work pages (cluster A), "Letterboxd/Goodreads/MyAnimeList alternative" pages (cluster F) and the blog plan
  (section 7): they need real content, and comparison pages need sources.
- Summaries for the 500 most-searched titles (about 6,800 works have none and stay `noindex`).
- Keyword demand has not been measured: no keyword tool was reachable. Check clusters in Google Keyword Planner and Search Console.
- sameAs for LinkedIn and YouTube, and a link from terratalesmedia.world with the anchor "Mimir, a media discovery guide".

**Claims check (what was changed and why)**
- "A parents' guide for each work" became "where one has been assessed": most imported works are not assessed, and "not assessed"
  must never read as safe. Titles promise a parents' guide only for assessed works.
- The Nepo Babies shelf blurb called follow-ons "so-so stories" that "coast on the family they came from". Its rule is a score
  threshold, so it now says exactly that. The Family Matinee and Cosy Corner taglines no longer say "safe".
- `docs/COMPETITIVE.md`: "Nobody else tracks...", "The others search by title or genre" and a stale "503 works" were softened or
  corrected, and a note says other products are described by their public features and may be out of date.
- Kept: the "AI-assisted readings awaiting editorial review" disclosure, no ratings or reviews invented in structured data, and no
  claim of being the best or only option.

## Search Console and Bing: what you do after the deploy
0. Site Kit on `terratalesmedia.world` already has a Search Console **domain property** (`sc-domain:terratalesmedia.world`). A domain property
   covers every subdomain, so `mimir.terratalesmedia.world` is probably already verified: open Search Console, pick that property and go to
   step 2. Otherwise:
1. In Google Search Console add the property `https://mimir.terratalesmedia.world/` (a URL-prefix property is simplest). Verify with
   the HTML tag method or the DNS record at your DNS host; GitHub Pages needs a file or meta tag, not a server setting.
2. Submit `https://mimir.terratalesmedia.world/sitemap.xml` (the index); Search Console then lists each section file.
3. Use URL Inspection, then Request indexing for the home page, `/films/`, `/franchises/`, `/tools/`, `/help/`, `/days/`, a few
   franchise pages (for example `/franchises/game-of-thrones/`) and the site's favicon source.
4. Add the site to Bing Webmaster Tools (import from Search Console) and submit the same sitemap.
5. Optional: IndexNow for Bing and others, once there is a way to ping on deploy.
6. After a week, open Performance to see real queries; check Indexing > Pages for "Crawled, currently not indexed" on thin pages.

---

Goal: be found on Google for **branded** searches (people who know Mimir) and **non-branded** searches (people who want something to watch, read, play or hear next).

**About the numbers.** No keyword-data tool was reachable from this session (the Ahrefs, Semrush and Similarweb connectors failed to connect), so demand is rated **High / Medium / Low** from how people search these categories, not from measured volumes. Section 9 says how to confirm each rating in free tools (Google Keyword Planner, Search Console) before spending effort on a cluster.

---

## 1. Where Mimir can and cannot win

| Competitor | Owns | Mimir's angle |
| --- | --- | --- |
| IMDb, Rotten Tomatoes, Letterboxd | Single title and film terms | Do not fight for "movies" or title-only queries |
| Goodreads, StoryGraph | Books | Cross-medium and parents' guide |
| JustWatch, Reelgood | "Where to watch" | Keep as a supporting feature, not a target |
| TasteDive, Trakt, MyAnimeList | Taste-based recommendations | Closest rivals: win on explained reasons and all media in one place |
| Common Sense Media | Parents' guides | Parents' guide for every medium, including games and music |

A new domain cannot rank for head terms. Mimir wins by being the best answer to **specific, long-tail questions**, at scale, using pages it can generate from its own catalogue: 7,500 works, 36 shelves, 372 tags, franchises, people, and about 50 days of the year.

What no competitor offers, and so what to build keywords around: **one catalogue across films, TV, books, games and music; reasons shown for every pick; a parents' guide for every medium; recommendations from a mood, a time limit or a favourite.**

---

## 2. Branded terms

**The problem:** "Mimir" is shared with the Norse figure Mímir, Grafana Mimir (a database), Mimir Health and other products. A search for "mimir" alone will not return Mimir for a long time.

**Targets**

| Query | Demand | Goal |
| --- | --- | --- |
| mimir terratales | Low (it is ours) | #1 with sitelinks |
| mimir media discovery / mimir recommendations | Low | #1 |
| mimir what to watch / mimir movie recommendations | Low | #1 |
| mimir terratalesmedia, mimir.terratalesmedia.world | Low | #1 |
| terratales media entertainment | Low | #1 (terratalesmedia.world) |

**Actions**
- Keep the name pattern identical everywhere: "Mimir" plus a descriptor, for example "Mimir, a media discovery guide". Always pair the word with "films, TV, books, games and music".
- Home page title: `Mimir · Find what to watch, read, play or listen to next`. Keep the Mimir-only titles you asked for.
- Home page structured data: `Organization` and `WebSite` with `sameAs` links to every owned profile (LinkedIn company page, GitHub, YouTube channel, Terratales). Already has the logo; add `sameAs` and `SearchAction`.
- Link Mimir from terratalesmedia.world with the anchor text "Mimir, a media discovery guide" (not just "Mimir").
- Claim and fill the profiles that Google reads for entity data: LinkedIn, YouTube, GitHub About, Crunchbase, Product Hunt.
- Submit the site in Google Search Console and Bing Webmaster Tools and use IndexNow so new pages are seen quickly.

---

## 3. Non-branded keyword clusters

Ranked by fit with what Mimir already has, then demand.

### A. "Like X" recommendations (largest opportunity, programmatic)
Patterns: *movies like {title}*, *shows like {title}*, *books like {title}*, *games like {title}*, *albums like {title}*, *what to read after {title}*, *if you liked {title}*.
Demand: **High** in total (millions of long-tail queries); each one is small.
Competition: Medium; many results are thin listicles.
Mimir asset: every work page already has "connected stories" and reasons. Cross-medium is the unique angle: *books like Dune movie*, *games like The Witcher books*, *anime like Death Note*.
Use on: work pages (H2 "Similar films and why", "More like this").

### B. Franchise guides and watch order (high demand, strong fit)
*James Bond movies in order*, *Marvel movies in order*, *Star Wars watch order*, *Harry Potter books vs movies*, *Lord of the Rings reading order*, *Middle-earth movies and shows in order*, *Game of Thrones and House of the Dragon order*, *Resident Evil games in order*, *Zelda games in order*, *Sherlock Holmes adaptations*.
Demand: **High**. Competition: Medium to High, but pages are mostly flat lists.
Mimir asset: IP pages with a row per medium and total time. The planned merge (Wizarding World, Middle-earth, Game of Thrones with House of the Dragon) makes these pages match the query exactly. Add "Watch order" and "Release order" sections with the time to finish.
Use on: IP pages, with titles such as `James Bond movies in order: all 25 films, books and games · Mimir`.

### C. Mood, theme and occasion lists
*feel good movies*, *comfort shows*, *cozy mystery books*, *slow burn thrillers*, *movies for a rainy day*, *scary movies that aren't too gory*, *short games to finish in a weekend*, *chill albums for studying*.
Demand: **High** for the head phrases, **Medium** for the specific ones. Competition: High on heads, Medium on specifics.
Mimir asset: 36 shelves, moods, themes and the mood mixer. Each shelf page should be titled for the phrase people use, not the playful shelf name alone (for example "Laugh Riot" becomes `Funniest comedy films, shows and books (Laugh Riot) · Mimir`).

### D. Parents' guide and age suitability
*{title} parents guide*, *is {title} suitable for kids*, *age rating for {title}*, *family friendly movies on Netflix*, *games safe for 10 year olds*, *books for 12 year olds with no violence*.
Demand: **Medium to High**. Competition: Medium (Common Sense Media dominates, but games, books and music are weaker).
Mimir asset: parents' guide on every work. Caution: works marked "Not assessed" must not rank for these queries; fill the guide first, then index (see section 6).
Use on: work pages (a "Parents' guide" section with its own heading), plus hubs like `Family-friendly films`.

### E. Decision tools
*what to watch tonight*, *what should I watch*, *random movie generator*, *movie picker*, *what should I read next*, *what game should I play*, *can't decide what to watch*.
Demand: **High**. Competition: Medium to High (many widgets), but tools with a clear result do well.
Mimir asset: Decide for me, Swipe, Spin and Craft. Give each a crawlable page with a plain-language intro and a short "how it works" (these are currently hash pages; see section 6).

### F. Alternatives and imports
*Letterboxd alternative*, *Goodreads alternative for all media*, *MyAnimeList alternative*, *IMDb alternative*, *track movies books and games in one place*, *import MyAnimeList list*, *import Goodreads library*.
Demand: **Medium**. Competition: Low to Medium. High-intent visitors.
Mimir asset: one library for every medium and imports. Needs honest comparison pages (`docs/COMPETITIVE.md` is the source); avoid claims you cannot support.

### G. Days of the year (seasonal, low competition)
*World Laughter Day movies*, *International Music Day playlist*, *World Book Day reading list*, *World Mental Health Day films*, *International Podcast Day*.
Demand: **Low to Medium**, spiky around the date. Competition: Low.
Mimir asset: 50 days with new and personal picks. Publish each day's page two to four weeks early so it is indexed in time.

### H. Regional and language (strong for the India base)
*best Hindi movies*, *Bollywood movies like {title}*, *Korean dramas like {title}*, *best Tamil thrillers*, *anime for beginners*, *Indian web series for family*, *Desi Delights*.
Demand: **High**. Competition: Medium to High, but regional long-tail is under-served.
Mimir asset: country and language filters, Desi Delights, Seoul Searching. Use the local spellings people type.

### I. Hidden gems and under-the-radar
*underrated movies*, *hidden gem games*, *lesser known books like {title}*, *best foreign films*.
Demand: **Medium**. Competition: Medium. Mimir has popularity tiers, so "Diamonds in the Rough" fits directly.

---

## 4. Meta tag map

Rules: title up to 60 characters, description up to 155; one distinct pair per page; titles end with `· Mimir` (as you asked); put the main phrase first; no keyword lists.

| Page | Title | Meta description |
| --- | --- | --- |
| Home | Mimir · Find what to watch, read, play or listen to next | Mimir is a free guide to films, TV, books, games and music. Tell it a mood, a favourite or how much time you have, and get picks with the reasons why. |
| /films/ | Film directory: browse 3,000+ films by mood and genre · Mimir | Browse films by genre, mood, country and year, with a parents' guide for each and links to where to watch. |
| /tv/ | TV series directory: shows by mood and genre · Mimir | Find a TV series by mood, genre or country, with how long it takes to finish and a parents' guide. |
| /books/ | Book and manga directory: find what to read next · Mimir | Browse books and manga by mood and theme, with reading time and a parents' guide for each. |
| /games/ | Game directory: games by mood and time to play · Mimir | Find a game that fits your time and taste, with a parents' guide and where to play. |
| /music/ | Albums by mood: find music for how you feel · Mimir | Albums sorted by feeling, with links to your music app. |
| /shelves/ | Shelves: hand-picked lists of films, shows, books and games · Mimir | 36 shelves, from comfort watches to hidden gems, across every medium. |
| Shelf | `{Plain-language shelf phrase}` (`{shelf name}`) · Mimir | `{N}` picks for `{phrase}`, across films, TV, books and games, each with the reason it fits. |
| Work | `{Title}` (`{year}`): similar `{medium}`, parents' guide · Mimir | What `{Title}` is like, who it suits, a parents' guide, and `{medium}` like it. |
| IP page | `{IP}` in order: films, shows, books and games · Mimir | Every `{IP}` film, show, book and game in one place, with watch order, release order and the time to finish all of it. |
| Day page | `{Day}`: what to watch, read and play · Mimir | Something new and picks for you for `{Day}` (`{date}`). |
| Help centre | Help centre · Mimir | Guides, FAQs and a walkthrough video for every part of Mimir. |
| Help article | `{Question phrased as people search it}` · Mimir | One-sentence answer, then what the page covers. |
| Blog post | `{Post title}` · Notes from the well · Mimir | Specific summary, 120 to 155 characters. |

**Meta keywords:** Google ignores the keywords tag. It is harmless but gives no ranking benefit; spend the effort on titles, headings and body copy instead.

---

## 5. On-page placement of keywords

- **H1** per page holds the main phrase; **H2s** carry the secondary phrases ("Similar films", "Parents' guide", "Watch order", "Where to watch").
- **First 100 words** state what the page is, with the medium and the main phrase, in plain language.
- **Internal links:** the home page's catalogue block, shelves, IP pages and work pages should link to each other with descriptive anchors ("books like Dune"), not "click here".
- **Images:** alt text with title and medium ("Poster of Arrival (2016)").
- **Structured data:** `Movie`, `TVSeries`, `Book`, `VideoGame`, `MusicAlbum` on work pages (no invented ratings); `ItemList` on shelves and IP pages; `BreadcrumbList` everywhere; `FAQPage` on the help centre and on IP pages; `WebSite` with `SearchAction` on the home page.
- **Languages and regions:** `lang="en"`; add `en-IN` hreflang only if you create India-specific pages.

---

## 6. Technical gaps that limit these keywords (fix first)

1. **Hash pages cannot rank.** Pages at `#help`, `#swipe`, `#craft`, `#decide`, `#days` and the franchise pages exist only in the browser. Search engines need real URLs. Generate static pages (as already done for works and shelves) for the help centre and its 20 guides, the tool pages, Days of the year and every IP page. This is the single biggest SEO task.
2. **Thin pages.** About 6,800 works have no summary, so they are `noindex`. They only start ranking when a summary is written. Fill summaries in order of search demand: the most famous titles first, then every title in a franchise or shelf, then the rest. Also add the fuller overviews on your roadmap.
3. **Parents' guide only where assessed.** Do not index parents' guide queries for "Not assessed" works.
4. **Page titles for shelves** currently use the shelf's playful name; add the plain-language phrase.
5. **Sitemap:** split into medium, shelf, IP, day, help and blog sitemaps with accurate `lastmod`; list them in `robots.txt`.
6. **Keep speed:** pages are already fast; do not add third-party scripts.

---

## 7. Content plan (blog: "Notes from the well")

Publish one to two posts per week for the first three months; each should target one cluster and link to the matching page.

1. *Marvel movies in order* and four other watch-order guides (cluster B)
2. *Cosy fantasy books for autumn* and similar seasonal mood lists (cluster C)
3. *Books to read after the Harry Potter series* and other "what next" guides (cluster A)
4. *Letterboxd, Goodreads and MyAnimeList in one place: how to move your lists* (cluster F)
5. *Family-friendly films by age* (cluster D)
6. *What to watch on {day}* posts, published a month ahead (cluster G)
7. *Hindi, Korean and Tamil picks* guides (cluster H)

---

## 8. Off-page and authority

- Press release and LinkedIn posts (already drafted in `docs/press/`); ask for a link to the live site, not the GitHub repository.
- Product Hunt, Hacker News (Show HN), relevant subreddits and Indie Hackers: share the tools, not just the site, and follow each community's self-promotion rules.
- Partner pages on terratalesmedia.world and the Akashic site, linking to Mimir with descriptive anchors.
- Listings on alternatives directories (AlternativeTo, SaaSHub).
- Do not buy links or trade links in bulk.

---

## 9. Measurement and validation

- **Verify demand:** put each cluster's head phrase into Google Keyword Planner (free with a Google Ads account) and check the "Search volume" column; keep clusters whose phrases show roughly 1,000 or more monthly searches in total.
- **Search Console:** once indexed, track impressions, clicks, average position and click-through rate for each cluster; the Performance report's "Queries" tab shows real keywords to adopt.
- **Branded checks:** search "mimir terratales" weekly and note the position and any sitelinks.
- **KPIs:** indexed pages (target 1,000 in 90 days), impressions per cluster, non-branded clicks, pages in the top 20.

## 10. Phases

**Days 0 to 30:** Search Console and Bing set up; static pages for help, tools, days and IP pages; new meta templates; `sameAs`, `SearchAction`, `FAQPage` and `BreadcrumbList` data; sitemap split.
**Days 30 to 90:** summaries for the 500 most-searched titles and every title in a franchise or shelf; watch-order content on every IP page; first 10 to 15 blog posts; comparison pages; keyword validation with real data.
**Days 90 to 180:** programmatic "like X" blocks on all summarised work pages; regional clusters; refresh the content that Search Console shows on positions 8 to 20.

## 11. Risks

- A naming clash on "Mimir"; always use the descriptor.
- Thin-page penalties: keep the `noindex` rule until a page has a summary.
- Overclaiming: "AI-assisted readings awaiting editorial review" must stay visible on classified pages.
- Using someone else's artwork or ratings in structured data; only mark up data Mimir is allowed to publish.
