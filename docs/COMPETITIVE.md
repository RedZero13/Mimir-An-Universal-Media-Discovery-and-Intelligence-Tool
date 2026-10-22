# Where Mimir stands: points of parity and points of difference

Mimir is meant to replace a stack of single-medium apps (MyAnimeList for anime, MangaUpdates for manga, IMDb or
Letterboxd for film and TV, Goodreads for books, Spotify for music discovery) with one place that tracks
everything and explains what to pick next. This page lists what each of those does that people rely on, whether
Mimir matches it yet, and what Mimir offers that none of them do.

Status: **Yes** shipped in the beta · **Partly** a first version, with the gap noted · **Not yet** planned.

## Points of parity

### MyAnimeList

| Feature people rely on | Mimir |
| --- | --- |
| Personal list with Watching / Completed / On hold / Dropped / Plan to watch | **Yes**, for every medium (Library) |
| Episode progress with a +1 button | **Yes**, episodes for TV, pages for books, hours for games |
| 1–10 score with labels (Masterpiece … Appalling) | **Yes**, same scale and words |
| Start and finish dates, rewatch count | **Yes** |
| Profile stats: counts per status, mean score, score distribution, time spent | **Yes** (Stats), plus themes, eras and languages |
| Import / export (MAL XML) | **Yes**, reads MAL XML; exports JSON backup and CSV |
| Recommendations | **Yes**, taste profile from ratings and scores, with the reason for each pick |
| Top rankings, genres, studios, people | **Yes** (Top lists, tags, people & studios) |
| Seasonal charts, airing schedules, episode release dates | **Not yet**: needs a live data source |
| Public profiles, friends, forums, clubs | **Partly**: accounts, profiles, follows, a feed and reviews with comments are built; they go live when the API is hosted. No forums or clubs yet |

### MangaUpdates

| Feature | Mimir |
| --- | --- |
| Reading list with statuses and chapter progress | **Partly**: statuses and progress work for books; manga is not yet its own medium with chapters and volumes |
| Release tracking (new chapters, scanlation groups) | **Not yet**: needs a release feed; licensing rules out scanlation listings |
| Series relations (sequels, spin-offs, adaptations) | **Yes**: series order, families, "adapted from / as" across media |
| "What's next" for series you read | **Yes**: Up next shows the next instalment after the furthest you've finished |

### IMDb

| Feature | Mimir |
| --- | --- |
| Watchlist | **Yes**: Planned status, plus custom lists |
| Your ratings (1–10) and rating history | **Yes**, with import of an IMDb ratings or watchlist CSV |
| Cast and crew pages | **Yes**: people & studios with their works across media |
| Parents' guide | **Yes**, six categories, and "not assessed" kept separate from "none" |
| Ratings from critics and audiences, box office | **Yes** where Wikidata records them, with source and date |
| Where to watch | **Yes**, with your preferred service and region (links open a search; availability isn't claimed) |
| User reviews and a community score | **Yes** (with an account) |
| Trailers, photos, trivia, goofs | **Not yet** (licensing) |

### Letterboxd and Goodreads

| Feature | Mimir |
| --- | --- |
| Diary of what you finished, by date | **Yes** (Library → Diary) |
| Reviews / notes per work | **Yes**: private journal entries as you go, and public reviews with likes and comments (with an account) |
| Custom lists, shareable | **Yes**: lists across media, shared by link, saved with one click |
| Year-in-review stats | **Yes**: last 12 months, eras, languages, themes |
| Import from Letterboxd and Goodreads | **Yes** (CSV exports) |
| Social feed, following, likes | **Yes** (with an account): follow people, a feed of what they review, start and finish, likes and comments |

### Spotify (for discovery, not playback)

| Feature | Mimir |
| --- | --- |
| Mood and activity playlists | **Yes**: Mood rings, plus albums and tracks by feeling |
| Open in your music app | **Yes**: Spotify, Apple Music, Amazon Music, YouTube Music and others, by preference |
| Playback, personal listening history | **Not yet / out of scope**: Mimir links out; its terms don't allow using Spotify data to train or feed ML |

## Points of difference

1. **One library for everything.** Films, TV, books, games and music in one list, one diary, one set of stats.
   Nobody else tracks a novel, its film and the game it inspired side by side.
2. **Discovery by feeling, in your own words.** "Something comforting after a difficult day, no violence, under
   two hours" works across all media. The others search by title or genre.
3. **Every pick is explained.** Mimir says which of your words matched which qualities, and marks recorded facts
   apart from editorial readings. Recommendations say which work you rated they come from and what they share.
4. **Cross-medium "like this".** "Something like Blade Runner but in a different medium" gives a novel, a game
   and an album, with the shared themes and moods.
5. **Time-aware.** Every work has a time investment (one sitting, an evening or two, a weekend, a long haul).
   Ask for "a series I can finish in a weekend", or filter your own list with "I have … an evening".
6. **Taste you can see.** Stats show the themes and moods you gravitate to, from a defined vocabulary, and they
   steer recommendations. Scores and quick ratings both feed the profile.
7. **An honest parents' guide** in six categories that never treats "not assessed" as safe.
8. **Provenance on every fact.** Each page says which source supplied a year, runtime, score or cover, and where
   a source disagreed with the editorial record.
9. **Private by default.** Library, lists and ratings stay in the browser; nothing is collected silently.
   Backups are a file you own.
10. **Less browsing, more watching.** "Decide for me" turns three taps into one pick with its reasons, and
    learns from "not this". The social calendar gives a pick a day for seasons and festivals people already
    celebrate: Spooktober, 12 Days of Christmas, Diwali, Lunar New Year, Pride, Noirvember.
11. **A journal as you go**, not just a review at the end: dated entries, feelings, where you were up to.
12. **Bring your history.** One import for MAL, IMDb, Letterboxd and Goodreads, so switching costs minutes.

## Next, to close the remaining gaps

1. **Host the community API** (built and tested: accounts, sync, reviews, follows, feed, challenges). Then email
   verification, password reset, moderation tools and notifications.
2. **Manga and anime as first-class formats**: chapters and volumes, seasons and cours, MAL and AniList IDs for
   exact matching on import.
3. **Release and availability feeds** from licensed partners (JustWatch-style availability, airing and
   publication calendars) for "new episode / new volume" alerts on your list.
4. **Catalogue scale**: the beta has 503 works. Import reports already list titles Mimir doesn't have; they feed
   the next catalogue additions.
5. **Licensed artwork** for films, TV and games (generated covers stand in today).
