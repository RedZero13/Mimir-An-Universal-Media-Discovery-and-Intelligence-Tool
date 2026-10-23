# The 35 future features: a phased roadmap

This document catalogues the 35 proposed features (numbered 1–35; there is no 21) and sorts them by how
feasible they are, what they cost against what they return, and how much they set Mimir apart. Related
features are bundled where they share data or code, so each bundle is built once.

**Scoring.** *Effort* is S (days, front end over data Mimir already holds), M (weeks, new data or API work) or
L (months, new data pipelines, editorial work or licences). *Return* is how many visitors it helps and how
often. *Edge* is how far it sets Mimir apart from IMDb, Letterboxd, Goodreads, MyAnimeList and streaming
services.

## Where each feature stands

| # | Feature | Status | Effort | Return | Edge | Bundle |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Experience DNA | **Shipped (phase 1)**: a fingerprint on every work page | M to deepen | High | High | A. Experience DNA |
| 2 | Mood and situation explorer | **Shipped (phase 1)**: mood mixer, several moods at once in Decide for me | S to add situations | High | High | A |
| 3 | Cross-medium discovery | Shipped: "…in other media" on every work and in Ask | — | High | High | A |
| 4 | Hidden gems mode | **Shipped now**: "Hidden gems" control on For you; Diamonds in the Rough shelf | — | Medium | Medium | B. Taste suite |
| 5 | Why you'll like this | **Shipped (phase 1)**: a "Why?" drill-down on every For you pick | — | High | High | A |
| 6 | Discovery by creative DNA | **Shipped (phase 1)**: keep or drop qualities from any work's DNA | — | Medium | High | A |
| 7 | Media relationship graph | Partial: relationships listed on work pages | M | Medium | High | E. Graph |
| 8 | Universe and continuity navigator | Partial: sagas in order with total time | M (needs canon and timeline data) | Medium | Medium | E |
| 9 | Themes, tropes and narrative mechanics | Partial: tag pages for every term | M (trope vocabulary) | Medium | High | E |
| 10 | Cultural and historical context | Not started | L (editorial) | Medium | High | F. Atlas |
| 11 | Intelligent comparison pages | **Shipped now**: compare any two works side by side | — | Medium | Medium | A |
| 12 | Evidence and confidence explorer | Partial: strength, basis and confidence for each tag and reason (phase 1); a catalogue-wide explorer is still to come | M | Low to medium | High | A |
| 13 | Taste profile | **Shipped (phase 1)**: an editable profile (more, less, never) | — | High | Medium | B |
| 14 | Taste evolution | **Shipped (phase 1)**: how your taste has changed, by year or quarter | — | Medium | Medium | B |
| 15 | Negative preference learning | **Shipped (phase 1)**: "You lean away from", plus "never" for any quality or guide item | — | High | Medium | B |
| 16 | Contextual profiles | **Shipped (phase 1)**: four built-in contexts, and your own saved ones | — | Medium | High | B |
| 17 | Recommendation controls | **Shipped**: popularity, length, variety and familiarity (more of what I know, or stretch me) | — | High | Medium | B |
| 18 | Taste overlap between two users | Not started | M (accounts) | Medium | Medium | C. Together |
| 19 | Time-aware planner | Shipped: Decide for me, By time you have | — | High | Medium | D. Time |
| 20 | Personal media itinerary | **Shipped now**: Plan my time (evening, weekend, week, month) | — | Medium | High | D |
| 22 | Group decision mode | **Shipped now**: Pick together, with avoid lists and the compromise spelled out | — | High | High | C |
| 23 | Backlog intelligence | **Shipped**: backlog first in Plan my time, quick finishes, already started, and the next work in each unfinished series | — | High | Medium | D |
| 24 | Curated discovery trails | Partial: shelves and calendar programmes | M | Medium | Medium | G. Community |
| 25 | Community taste maps | Not started | L (needs users) | Low early | Medium | G |
| 26 | Review perspective filters | Not started | M | Medium | Medium | G |
| 27 | Spoiler-controlled discussions | Partial: watch-along comments stay hidden until you reach them | M | Medium | High | G |
| 28 | Creator and critic portfolios | Not started | M | Medium | Medium | G |
| 29 | Public collection pages | Partial: lists shared by link; published lists in the API | S to M | Medium | Low | G |
| 30 | Community taxonomy proposals | Not started | L (moderation) | Low early | High | G |
| 31 | The Mimir Knowledge Atlas | Not started | L | Medium | Very high | F |
| 32 | Research mode | Not started | L | Low (niche) | Very high | F |
| 33 | Visual and audio similarity search | Not started | L (licensed assets only) | Medium | High | H |
| 34 | Creative influence explorer | Not started | L (influence data) | Medium | High | E |
| 35 | Ask across the catalogue | Not started | L | Medium | Very high | F |

## The bundles

- **A. Experience DNA** (1, 2, 3, 5, 6, 11, 12). One per-work profile drives everything: show it as a fingerprint
  on each work, let people keep or drop qualities ("keep the world-building, no romance"), combine moods
  ("melancholic but comforting"), and open each reason into its evidence. Compare pages already read from it.
- **B. Taste suite** (4, 13, 14, 15, 16, 17). One editable taste profile: what you lean towards and away from,
  how it has changed (from diary dates), saved contexts such as "winding down" or "learning", and the controls
  that steer picks.
- **C. Together** (18, 22). Pick together works today in one browser; taste overlap between two accounts follows
  accounts going live.
- **D. Time** (19, 20, 23). Decide for me, Plan my time and the backlog view share one ranking.
- **E. Graph** (7, 8, 9, 34). Relationships, continuity, tropes and influences as one navigable graph.
- **F. Atlas and research** (10, 31, 32, 35). Sourced context and questions across the whole catalogue.
- **G. Community** (24–30). Trails, perspectives, spoiler-safe discussion, portfolios, collections, taxonomy
  proposals. Most need hosted accounts and moderation (API work already in `api/`).
- **H. Similarity search** (33). Only with licensed images and audio.

## Phases

### Shipped in this release (quick wins)

Compare pages (11), recommendation controls with hidden gems (4, 17), Plan my time with backlog first (20, 23),
and Pick together (22). All run in the browser over data Mimir already holds.

### Phase 1: lowest-hanging fruit, high return (shipped)

Front-end work over existing tags and library data. All six are live:

1. Experience DNA fingerprint on every work page, and "keep this, drop that" from it (1, 6).
2. Mood combinations in Ask and on Decide for me (2).
3. Editable taste profile with what you avoid, and saved contexts (13, 15, 16).
4. Taste over time from your diary (14).
5. "Why" drill-down: each reason opens to its tag, strength, basis and source (5, 12).
6. Novelty and familiarity controls; "unfinished series" in the backlog (17, 23).

### Phase 2: needs accounts, the hosted API or editorial work

Taste overlap (18), curated trails (24), review perspectives (26), spoiler-safe reviews and threads (27),
creator and critic pages (28), public collection pages (29), the continuity navigator with canon and timelines
(8), the trope explorer (9) and the relationship graph (7).

### Phase 3: the differentiators that put Mimir on the map

The Knowledge Atlas (31), ask across the catalogue (35), research mode (32), cultural and historical context
(10), the influence explorer (34), community taxonomy proposals (30), community taste maps (25) and licensed
visual and audio similarity (33). These need sourced data at scale, editorial review and, for 33, licences.

## Best value for effort

Highest return for the least investment, in order: Experience DNA fingerprint (A), the editable taste profile
(B), mood combinations (2), and the "why" drill-down (5, 12). Each reuses the tags every work already carries.

The features most likely to set Mimir apart are Experience DNA (1), Pick together (22), the Atlas with sourced
answers (31, 35) and the graph (7, 34). No mainstream service combines these across every medium.
