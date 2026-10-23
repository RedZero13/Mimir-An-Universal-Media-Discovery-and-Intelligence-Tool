# Mimir roadmap

Where Mimir goes after the beta. The aim stays the same: one place to discover and keep track of every kind of
story, with the reasons for every pick and a source for every fact. [COMPETITIVE.md](COMPETITIVE.md) lists the
features this closes against MyAnimeList, MangaUpdates, IMDb, Letterboxd, Goodreads and Spotify.

Each item says why it matters, what "done" means, and what it depends on. Horizons are sequenced, not dated:
**Now** is in progress or next up, **Next** follows once Now is stable, **Later** needs Next in place.

## Shipped in the beta

- 601 works across films, TV, books (including manga and manhwa), games and albums in 28 languages; 138-term taxonomy; parents' guide.
- Discovery in your own words, explained picks, cross-medium "like this", time-aware requests.
- Taste profile and "For you"; shelves, mood rings, sagas, rankings, people and tag pages.
- Where to watch / read / play / listen with your preferred service and region.
- Library: statuses, 1–10 scores, episode / page / hour progress (also on covers), dates, rewatches, notes,
  diary, lists shared by link, "Up next" in series, stats, import from MAL, IMDb, Letterboxd and Goodreads,
  JSON and CSV export.
- Open-data enrichment: Open Library (105 of 115 books), MusicBrainz (78 of 84 albums), Wikidata in progress.
- Journal per work; Decide for me; the social calendar (22 programmes: Spooktober, 12 Days of Christmas, Diwali,
  Pride Month, Noirvember …) with challenges you join and tick off.
- Accounts and community in the API, with the site wired to it: sign-up and sign-in, library sync, public
  reviews with likes and comments, follows and a feed, trending, published lists, challenge leaderboards,
  reports, private profiles and account deletion. Live once the API is hosted (DEPLOY.md).

## Now: harden the beta

| Item | Why | Done when |
| --- | --- | --- |
| Finish Wikidata enrichment | Years, runtimes, review scores and IDs for films, TV and games | All 503 works attempted; matches reviewed; conflicts listed |
| ~~Real covers only~~ | Shipped: only cover and poster images are shown as covers | |
| ~~Manga and anime as formats~~ | Shipped: manga, manhwa and manhua with chapters and volumes; chapter progress; Panels & Pages and Anime Essentials shelves | |
| Catalogue to 1,000 works | Imports report what's missing; testers will look for their favourites | Unmatched import titles and feedback triaged weekly into the seed |
| MAL / AniList / IMDb IDs on works | Title-and-year matching misses translations and remakes | Imports match by ID first, title second |
| Beta feedback loop | Know what's wrong before scaling | Weekly triage of emails and "report a problem"; fixes tracked in the repo |
| Accessibility pass | The site should work by keyboard and screen reader | WCAG 2.2 AA checks on home, work, library and search pages |

## Next: accounts, live data, the full app

| Item | Why | Depends on |
| --- | --- | --- |
| Host the community API | Accounts, sync, reviews and the feed are built; they need a server | Render blueprint in the repo; a hosting account |
| Email verification and password reset | Safe sign-ups and account recovery | An email-sending service |
| Moderation queue and community guidelines | Reports are stored; someone needs to act on them | Policy, a small admin view |
| Notifications | "Someone replied", "your friend finished …", "Spooktober starts tomorrow" | Hosted API; push or email |
| Reviews as a ranking signal | Let community scores and likes shape picks and trending | Enough reviews to be meaningful |
| Availability feed | "On Netflix in India now" instead of a search link | Licensed partner (JustWatch, Reelgood or similar) |
| Release calendar and alerts | New episode, volume, album or game for things on your list | Release data source; accounts for notifications |
| Install as an app (PWA) | Home-screen icon, offline library, faster repeat visits | None |
| Web app parity | The Next.js app in `web/` should match the static site's features | Hosted API |
| Licensed artwork | Real posters for films, TV and games | TMDB or IGDB agreement (see SOURCES.md) |
| Editorial review workflow | Turn AI-assisted tags and guides into reviewed ones, visibly | Accounts for editors |

## Later: community and reach

| Item | Why |
| --- | --- |
| Follow people, activity feed, collaborative lists | The social layer of Letterboxd and Goodreads |
| Community tag votes and corrections | Scale the catalogue's readings beyond the editorial team |
| More media: podcasts, comics and graphic novels, board games, theatre | "Every story", as the brand promises |
| Interface in more languages (Hindi, Tamil, Korean, Japanese …) | The catalogue is already multilingual; the interface should be too |
| Native apps (iOS, Android) | Notifications, widgets, share sheet |
| Public API and embeds | "Why this fits" cards for publishers and partners; a business line for Terratales |
| Year in review | A shareable summary of your year across every medium |

## How items move

An item moves to **Now** when what it depends on is in place and beta feedback says it matters. Each item gets an
issue with the "done when" written up front. Work ships behind the existing tests (`pytest` for the engine and
API, parity tests for the browser engine), and the site redeploys from `main`.
