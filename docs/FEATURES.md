# Mimir: features

Mimir is a free catalogue and discovery engine for films, TV series, books and manga, games, music and YouTube,
built by Terratales Media Entertainment. Live at [mimir.terratalesmedia.world](https://mimir.terratalesmedia.world/).

The catalogue holds 681 works: 240 films, 93 TV series, 146 books and manga, 70 games, 87 albums, 14 YouTube
channels and 31 videos, from 42 countries in 29 original languages, classified against a controlled vocabulary
of 372 terms (233 of them subgenres).

## Find something

- **Ask Mimir in your own words.** Describe a mood, an idea, a favourite, things to avoid or how long you have
  ("I want to die laughing watching a show", "a book like Outer Wilds", "under two hours, no violence"). Mimir
  shows how it read the request, then returns a few picks, each with the reasons it fits.
- **Every pick explains itself.** Reasons come from the catalogue and say whether each is a recorded fact or an
  editorial reading.
- **Cross-medium.** "Something like Blade Runner but in a different medium" works; so does any medium on its own.
- **Decide for me.** Three taps, one pick, with its reasons.
- **For you.** Rate a few works you know (loved, liked, disliked) and Mimir builds a taste profile in your browser
  and recommends from it, naming the work each pick resembles.
- **By the time you have.** Quick bite, one sitting, an evening or two, a weekend, a season, a long haul: from
  runtime, main-story playtime, or reading time from page count.
- **Search** titles, people and studios from the menu bar, scoped to a medium.

## Browse

- **Directories per medium** (films, TV, books, games, music, YouTube), each showing only that medium, with
  filters for tag, decade, language, country, length and parents' guide category.
- **36 shelves** with wordplay names and a stated rule: Diamonds in the Rough, Nepo Babies, Laugh Riot, Drama Mamas,
  Fright Club, Binge-Worthy, Seoul Searching, Desi Delights, Page Turners, Side Quests, World Builders and more.
  Each has an About panel with its description, its classification rule and its year span.
- **Subgenres for every genre** in every medium (slasher, folk horror, cosy mystery, soulslike, Sufi rock…), grouped
  under their parent on each shelf.
- **Industry filter** for film and TV: Hollywood, India, Japan, Korea, China, France, the UK and more.
- **Top rated** per medium, from a single 0–100 critics' average across the published scores Mimir holds.
- **Sagas and series:** franchise families in order, with total time; series numbers appear only on the series page.
- **Tag pages** and **people and studio pages** with recurring qualities.
- **Social calendar:** seasonal programmes with a pick for each day (Spooktober, Noirvember, Nonfiction November…).
- **Music:** mood rings and a remix rack.
- **YouTube:** creators worth following, what they make and their best-known videos, with video thumbnails as
  covers, grouped as comedy, food, gaming and horror, VFX and film, mysteries and music.
- **Audiobooks:** books grouped by listening time. 88 books show their real Audible recording (narrator, length,
  release year); public-domain books link their free LibriVox recording.
- **Food:** cooking competitions, food travel, food documentaries, taste tests and food dramas across film, TV, books
  and games.

## Every work page

- Facts with their source (Wikidata, Open Library, MusicBrainz, the publisher) and what the seed said where they differ.
- Tags by dimension (genre, theme, mood, pacing, complexity, narrative, world, style), with strength and basis.
- **Parents' guide** for every medium: official ratings plus per-category severity and notes, telling "none" apart
  from "not assessed".
- Connected stories: adaptations, sequels, spin-offs, the same universe.
- **Where to watch, listen, read or play** for your region (US, UK, India, Canada, Australia), with your preferred
  apps first.
- Pinned section tabs that follow you down the page.

## Your library

- Statuses, scores, progress (episodes, pages, hours for audiobooks, playtime) and a diary.
- **Lists:** playlists, reading lists, watch lists and bookmarks, each with a share link and social sharing.
- **Custom trackers** for any goal you set.
- **Activity rings** (watch, read, play, listen) with daily goals, and **about 60 badges** for milestones
  (1st, 5th, 10th, 50th…).
- **Journal**, **stats** and a **year in review**.
- **Import and export** your whole library as a file.
- Everything lives in your browser unless you sign in.

## Community

- Accounts with profiles, privacy settings and account deletion.
- Reviews with a community score, likes and comments; follow people and see their activity.
- Published lists and social-calendar challenges with leaders.
- **Watch-alongs:** start one on any film or series, leave comments at timestamps that stay hidden until others
  reach that moment, share the link, and see live watch-alongs in Community.
- Reports for reviews, comments, users and lists.

## Built to be fast, findable and honest

- The home page is about 120 KB and paints its headline with the first bytes; data and code load after it and are
  cached for repeat visits and offline use (installable as an app on Android, iOS, Mac and Windows).
- Plain pages for all 681 works, every medium and every shelf, with structured data and a sitemap, so search
  engines can index the catalogue.
- Light and dark modes, keyboard navigation, reduced-motion support and WCAG AA contrast.
- Labels everywhere say what is verified and what is an AI-assisted reading awaiting review.

## Under the hood

- Python (FastAPI, PostgreSQL) API and a Next.js web app; the public site runs the same discovery engine in the
  browser, kept identical to the Python by parity tests on every query.
- No LLM and no API keys: requests are parsed into inspectable constraints, ranked, and explained from evidence.
- Open data only, each source in a licensing register ([`SOURCES.md`](SOURCES.md)).
