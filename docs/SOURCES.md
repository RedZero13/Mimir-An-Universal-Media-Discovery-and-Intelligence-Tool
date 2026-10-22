# Data sources and licensing register

The database `source` table is the authoritative register for sources in use. This document tracks candidates
**before** integration. A provider moves into `source` only after its terms are reviewed and recorded.

> The terms summarised here reflect general knowledge as of late 2026 and must be re-checked against each
> provider's current terms before integration. They are not legal advice. When in doubt, the status is
> "unknown", which means do not store.

## In use

| Slug | Kind | Store | Display | Commercial | AI use | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `editorial-seed` | editorial | yes | yes | yes | yes | Pilot facts compiled from general knowledge. **Unverified**; must be checked against primary sources before launch |
| `ai-assisted-seed` | ai_assisted | yes | yes | yes | yes | Pilot classifications and interpretive relationships. **Unreviewed** |

The pilot synopses are original writing. No third-party text, images or scores are stored.

## Candidates

| Provider | Likely role | What we believe the terms are | Status |
| --- | --- | --- | --- |
| Wikidata | Identity backbone: QIDs, dates, credits, cross-identifiers | CC0 public domain | Recommended first integration |
| MusicBrainz | Music releases, artists, credits | Core data CC0; supplementary data CC BY-NC-SA | Recommended (core data only) |
| Open Library | Books, editions, ISBNs | Open data; confirm the licence of dumps and covers | Verify |
| Wikipedia | Background reading only | Text is CC BY-SA (share-alike); don't copy into proprietary fields | Link out only |
| TMDB | Film/TV metadata and images | Attribution required; commercial use needs an agreement; check caching and AI/ML clauses | Verify; likely needs a commercial agreement |
| IMDb | Film/TV metadata | Public datasets are for personal and non-commercial use; commercial use needs a paid licence | Not without a licence |
| Goodreads | Book ratings and reviews | No public API for new developers since 2020; scraping is prohibited | Do not use |
| IGDB / RAWG | Game metadata | Commercial terms unclear | Verify |
| YouTube Data API | Review and reaction videos, creator channels | Allowed within the API terms: quotas, attribution, limits on caching API data, official embeds only | Phase 2 candidate |
| Spotify Web API | Outbound links and embeds | Developer terms restrict using its content to train or feed ML models; check | Links/embeds only |
| Letterboxd, Rotten Tomatoes, Metacritic | Ratings, reviews | No open licence for reuse | Do not scrape; licence or omit |
| JustWatch / Reelgood | Streaming availability | Commercial partnership | Later |
| Luminate, Circana, box-office trackers | Sales, charts | Commercial licence, typically expensive | Later, if justified |

## Rules for integrating a provider

1. Record commercial use, storage, display, AI-use rights, attribution text and maximum cache age in `source`.
2. Keep raw payloads separate from canonical records (planned `source_record` table, migration `0003`). Record
   each scalar value in `field_provenance` against its source.
3. Treat imported values as evidence. Conflicts are recorded and surfaced, never silently overwritten.
4. Honour refresh and deletion obligations with a scheduled job per source. Removing a source must remove or
   orphan everything only it supplied.
5. Never present a provider's data as our own claim. Attribution is shown wherever its data is displayed.
