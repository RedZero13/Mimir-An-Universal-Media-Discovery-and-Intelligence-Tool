# Catalogue expansion

The catalogue grew from 681 hand-classified works to about 7,500 by importing notable works from Wikidata (CC0).
Imported works arrive with facts only (title, year, creators, country, language, length where Wikidata has it,
and genres mapped onto Mimir's taxonomy), so they appear in browse, search, hubs, shelves and work pages straight
away. Everything Mimir reads beyond genre is filled in batches.

## What was imported

| Medium | Imported | Left out |
| --- | --- | --- |
| Films | 2,972 | no English Wikipedia article (275), already in the catalogue (226), not a single work (21), adult (4) |
| TV series | 1,346 | already in the catalogue (67), no article (51), not a single show (31) |
| Books | 555 | no article (1,560), reference works and anthologies (191), no year (92) |
| Games | 1,193 | no article (221), already in the catalogue (59), adult (11) |
| Albums | 765 | not a studio album (113), no article (77) |

Rules: one English Wikipedia article and a year are required; encyclopedias, compilations, live and soundtrack
albums, episodes, film series and adult titles are skipped; anything already in the catalogue is kept as it was.
Popularity tiers come from Wikidata's link counts (top 5% of each medium widely known, then 30%, 70%, the rest).

## What is missing, and where it is recorded

`api/mde/catalogue/gaps.json` lists, for every imported work, what it still lacks; its totals show the size of each
gap. `api/mde/catalogue/reference-provenance.json` keeps each work's Wikidata item, short description, Wikipedia
article and external ids for the batches to work from. Neither file is sent to the site.

| Gap | Works |
| --- | --- |
| Summary | all imported |
| Moods, themes, pacing, style (beyond genre) | all imported |
| Parents' guide | all imported (shown as "Not assessed") |
| Playtime | all games |
| Countries | 972 |
| Length | 890 films and albums |
| Episode count / episode length | 812 / 558 series |
| Creators | 625 |
| Page count | 522 books |
| Language | 492 |
| Genre | 283 |

Until a work has a summary, its static page is marked `noindex` and left out of the sitemap, so search engines
never see a thin page.

## Batches

Each batch fills a slice of works, most widely known first, and removes what it fills from `gaps.json`.

1. **Classification and summary.** Moods, themes, pacing, complexity, storytelling, world and style, plus a
   one- or two-sentence, spoiler-free summary. This is what lets a work answer Ask, For you, Experience DNA and the
   mood mixer.
2. **Parents' guide.** Violence, language, sexual content, frightening scenes, substances and sensitive topics,
   each with a level and a short note.
3. **Fuller overviews.** Work pages currently carry one or two sentences. A richer overview, two or three short
   spoiler-free paragraphs (premise, what it is like to watch, read, play or hear, and why people come back to it),
   for every work, starting with the most visited. This applies to the original 681 works too.
4. **Facts from sources.** Playtime, episode counts and lengths, page counts and missing creators, from open data
   (Wikidata, Open Library, MusicBrainz) where it exists.

Everything written in batches 1–3 is an AI-assisted reading, labelled as such on the site, awaiting editorial review.

## Franchises and cast

Works carry franchise groups (James Bond, Middle-earth, the Marvel Cinematic Universe, the DC Extended Universe,
the Wizarding World and the rest) alongside their series, from Wikidata's "part of the series" and "media franchise"
statements plus a curated list of umbrella franchises. Films and series list their lead cast, in billing order
where Wikidata records it. Both live in `api/mde/seed/people-and-franchises.json`, an overlay on works defined in
any seed file.

## Performance

Holding about 7,500 works in the browser costs more start-up time than 681. The engine now caches cards and slug
look-ups and computes sort keys once; the page reads tags straight from the catalogue's records rather than
building full pages. The next step, if mobile start-up needs it, is to load imported works after the first paint.
