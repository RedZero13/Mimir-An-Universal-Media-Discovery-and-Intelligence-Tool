# Project assessment

_October 2026. Covers the state of the repository, the MVP architecture, and what to build next._

## 1. Starting point and what exists now

**Starting point.** This repository held only a one-line README. (`RedZero13/RedZero`, the other repository in
the workspace, is the unrelated TrueTap Android keyboard and was left untouched.) There was no prior architecture
to respect, so the foundation below was established from the directive.

**What exists now (this branch):**

| Area | State | Verified by |
| --- | --- | --- |
| Schema (migration `0001`) | Works, media lookup, manifestations, titles, external IDs, people, organisations, credits, taxonomy, classifications, typed relationships, field provenance, source register, import runs, discovery events, feedback | Applied to a fresh PostgreSQL 16 DB in tests; re-applying is a no-op |
| Taxonomy v0.1.0 | 9 dimensions, 91 terms with definitions, media applicability and parser synonyms. Ambiguous synonyms are rejected at load time | Unit tests |
| Pilot catalogue | 56 works: 22 films, 15 books, 11 games, 8 albums; 871 classifications; 18 relationships | Validated before every import; duplicate detector |
| Importer | Validates first, all-or-nothing, idempotent; source-scoped replacement of credits and classifications | Integration tests (re-import changes nothing; invalid import writes nothing) |
| Discovery | Rule-based intent parser, transparent ranker, template explanations, diversity re-rank, event logging | 36 tests; 20-query benchmark |
| API | FastAPI: discover, work, taxonomy, feedback, health | Integration tests via TestClient |
| Catalogue | Browse with filters and facets, tag pages, people pages, work pages with a parents' guide (taxonomy v0.2.0, migration `0002`) | Unit and integration tests; JS/Python parity tests |
| Web | Next.js 15: discovery page (interpretation, results, reasons, caveats, score breakdown, feedback), work page | Typecheck, production build, and a headless Chromium run (desktop and 375 px; feedback round-trip; 404 for unknown work) |

**Gaps (deliberate, for later phases):** no external data integrations, no editorial review tool, no
semantic/vector retrieval, no LLM parser, feedback not yet used in ranking, no accounts, no availability,
reviews or online-video records, and no deployment.

**Risks to flag now:**

1. **Data provenance of the pilot.** Pilot facts were compiled from general knowledge rather than a licensed
   source, so they must be verified before any public launch. Classifications are AI-assisted. Both are
   labelled throughout, but they are not yet trustworthy enough to publish as authoritative.
2. **Benchmark independence.** The same author wrote the benchmark and the system, so 20/20 is a regression
   floor, not evidence of quality. Real users must judge results (see §6).
3. **Licensing determines the shape of the catalogue.** The sources the brief names (IMDb, Goodreads) are
   largely closed to commercial reuse (§5). The strategy has to be built around open data, licensed data and
   in-house classification.
4. **Parser coverage.** Rule-based parsing is transparent and testable, but brittle outside its lexicon. It is
   the first component likely to need an LLM, behind the existing interface.

## 2. MVP architecture

A modular monolith with four layers that only depend downward:

```
web (Next.js, server components)
   │  HTTP (server-side only; API URL never reaches the browser)
api (FastAPI) ── app.py: validation + serialisation only
   ├── discovery/   intent.py ─► rank.py ─► explain.py   (engine.py orchestrates, logs events)
   ├── catalogue/   load.py (write path, validated, idempotent) · repository.py (read path)
   ├── taxonomy/    taxonomy.json (versioned vocabulary) + loader/validator
   └── migrations/  plain SQL, additive
PostgreSQL 16 (full-text search now; pgvector when semantic retrieval earns its place)
```

Key decisions:

- **Ingestion is separated from querying.** Only `load.py` writes catalogue data, and the read path never
  mutates it.
- **Classification is separated from ranking.** The ranker consumes `(term, strength, confidence)` evidence and
  doesn't care where it came from. Editorial, AI-assisted and source classifications coexist with their origin.
- **Model-agnostic seams.** `IntentParser` is a protocol: the rule-based parser is the baseline any LLM parser
  must beat on the benchmark. Ranking weights live in a `RankingWeights` dataclass, tuned against the
  benchmark, not edited in place.
- **Inspectability.** Every result carries its score breakdown, and every discovery event records the parsed
  intent, the ranked list and the ranker version, so changes can be compared on logged traffic.
- **Not introduced yet**, by design: a queue, a search cluster, a vector store, microservices, auth, or an LLM.
  Each has an entry condition in the roadmap.

## 3. Data model and migration plan

Migration `0001_foundation.sql` is the full first schema. The principles behind it:

- **Work vs manifestation.** A `work` is the abstract creation. Editions, cuts, remasters and platform releases
  are `manifestation` rows, so a novel and its film are two works linked by `adaptation_of`.
- **Typed common fields plus extension points.** Cross-medium measures that get queried (runtime, page count,
  playtime) are typed columns, and NULL means unknown. Rare medium-specific data goes in `attributes` jsonb.
  Media types are a lookup table, so adding a medium is an `INSERT`.
- **Claims, not facts.** `classification` rows carry strength, confidence, origin, interpretation flag, spoiler
  flag, review status, source and taxonomy version. Unique per (work, term, origin), so editorial and AI claims
  coexist.
- **Missing ≠ absent.** For content advisories, an assessed work gets explicit 0-strength rows. An unassessed work
  has none, and the UI says "not assessed" rather than implying it is safe.
- **Relationships are typed** (`relationship_type`: label, inverse, symmetric, factual). Factual links
  (adaptation, sequel) are distinguished from interpretive ones (thematic kinship, contrasting take) in the
  data and the UI.
- **Provenance.** `source` is the permission register (commercial use, storage, display, AI-use rights).
  `field_provenance` records each source's value for each scalar field, which allows conflicting values and a
  selected value. `import_run` logs each import.
- **Discovery analytics are anonymous**: `discovery_event` (query, parsed intent, ranked list, ranker version)
  and `feedback`.

**Next migrations (additive):**
`0002` editorial review (`classification_review`, reviewer, decision, note) and spoiler fields on reviews ·
`0003` external-source records (`source_record` raw payloads with retrieval time and licence), merge history
(`work_merge`) · `0004` availability (`offer`: platform, region, model, observed_at, expires_at) ·
`0005` `work_embedding` (pgvector), introduced once §7 step 6 shows it helps · later: accounts, collections,
community reviews.

## 4. Taxonomy and classification

See [`TAXONOMY.md`](TAXONOMY.md) for the full specification. In summary: nine independent dimensions (genre,
theme, mood, pacing, complexity, narrative, world, style, advisory). Each term has a definition, applicability by
medium, and synonyms used for parsing. Classifications are graded 0–1 rather than binary, so a work can be
"comforting 0.8" and "melancholic 0.6" at once. Confidence is stored separately from strength. The taxonomy is
versioned, and terms are deprecated rather than deleted.

## 5. First catalogue and data-source strategy

**Pilot (built):** 56 works chosen to exercise the benchmark. They include cross-medium adaptation pairs
(Arrival / Story of Your Life, Solaris ×2, Stalker / Roadside Picnic, Blade Runner / Do Androids Dream,
Annihilation ×2), a sequel, mainstream and obscure works on similar themes, and works at both ends of each
content advisory.

**Next catalogue (proposed): 300–500 works**, chosen by the benchmark rather than by popularity: about
40% film, 25% books, 20% games, 15% music, deliberately including non-English, independent and older works. Each
must have verified facts and editor-reviewed classifications before launch. That is roughly 15–25 minutes of
editorial time per work with AI-drafted classifications, which is feasible for one founder plus one or two
part-time editors over several weeks.

**Source strategy, by risk** (details and status in [`SOURCES.md`](SOURCES.md)):

| Use | Recommended | Avoid / needs a licence |
| --- | --- | --- |
| Identity, dates, credits, cross-IDs | **Wikidata** (CC0) as the backbone; **MusicBrainz** core data (CC0) for music; **Open Library** for books (verify terms) | IMDb datasets are personal/non-commercial only; commercial use needs a paid licence. Goodreads closed its public API to new developers in 2020, and scraping it breaches its terms |
| Film/TV metadata and images | **TMDB** API: attribution required, and a commercial agreement is needed for commercial use. Confirm its current AI/ML-use terms before storing data for model use | Scraping IMDb, Letterboxd or Rotten Tomatoes |
| Games | **Wikidata**, plus IGDB or RAWG after a terms review (commercial terms unclear) | Steam store scraping |
| Music audio features/streams | **MusicBrainz**; Spotify only for outbound links/embeds. Its developer terms restrict using its content to train or feed ML models (verify) | Using Spotify data in recommendation models |
| Online video | **YouTube Data API** (quota, caching limits, attribution) for authorised embeds and links. Refresh or delete cached data per its terms | Downloading or re-hosting videos |
| Synopses | **Write our own** (as the pilot does). Wikipedia text is CC BY-SA (share-alike), so don't copy it into proprietary fields | Copying publisher or retailer blurbs |
| Sales, charts, box office | Later, through a licensed provider (e.g. Luminate or Circana); expensive | Scraped chart data |
| Availability | Later, through a partnership (e.g. JustWatch or Reelgood) or direct deals | Scraping streaming catalogues |

The defensible asset is our own: the taxonomy, reviewed classifications, verified relationships and feedback
data. External sources supply identity and facts, and are kept as reconcilable evidence with field-level
provenance.

**Licensing risks to resolve before integrating anything:** each provider's commercial-use terms, attribution
requirements, caching limits, AI/ML restrictions and termination obligations. Record these in `source` before the
first import from that provider. The terms of service above are summarised from general knowledge as of 2026 and
**must be re-checked against current terms**. They are not legal advice.

## 6. Discovery benchmark

[`api/benchmark/queries.json`](../api/benchmark/queries.json) has 20 queries across 14 categories:
natural-language, mood, cross-medium, relationship, keyword, style, structured, situational, theme, exclusion,
novelty, parser traps, honesty, and education. Each has a statement of what good results look like, hard
checks, and graded relevance for P@5 and hit@3.

Notable cases:

- The directive's own example (length as a preference, careful violence handling, a lean towards lesser-known
  works).
- `not too slow sci-fi with time loops`: negation must scope to "slow" only.
- `I'd like a romantic film`: "like" is a verb, not a reference.
- `an uplifting journey of self-discovery`: must not resolve to the game *Journey* or the album *Discovery*.
- `a K-pop album about football`: must return nothing rather than pad the list.
- `melancholic music with no violence`: unassessed albums must carry a caveat, not a claim of safety.

Current result: **20/20 checks pass; mean P@5 0.72; hit@3 1.0.** The low-P@5 queries are mostly ones where the
pilot has only one or two truly relevant works, so the rest of the list is honest filler. Two real defects were
found and fixed by the first run: "thought-provoking" was mapped to the wrong term, and out-of-catalogue
queries were padded with every album.

**Before trusting these numbers:** have 5–10 target users write their own queries and grade the top 5 blind.
Compare against a genre-filter baseline on the same catalogue, and against a basic-metadata-only ranker
(genre + year + runtime) to test whether the deeper taxonomy helps (§13 of the directive).

## 7. Roadmap

Each step has a testable exit criterion. Steps 1–4 make the slice trustworthy; 5–8 make it better.

1. **Ship the slice for testing.** Deploy the API and web app (a managed Postgres plus two small services), with
   backups, error reporting and logging. *Exit:* a public URL; and event and feedback rows arrive.
2. **Editorial review tool.** Queue of unreviewed classifications by work; accept/adjust/reject; the review status
   flows into the UI labels. *Exit:* all pilot classifications reviewed; reviewed share shown in `/api/health`.
3. **Verified facts via Wikidata.** An importer that matches works to Wikidata QIDs, stores
   `external_id` and `field_provenance`, and flags disagreements with the seed. *Exit:* each pilot work has a QID,
   or is flagged as unmatched; conflicts are listed, not overwritten.
4. **User-judged benchmark.** Recruit testers, collect graded judgements, and add a baseline ranker for comparison.
   *Exit:* P@5 from independent judges, plus a baseline comparison, both recorded.
5. **Grow to 300–500 works** using AI-drafted plus editor-reviewed classifications, guided by the queries that
   fail. *Exit:* catalogue coverage of benchmark queries ≥ 90%.
6. **LLM intent parser behind `IntentParser`**, with structured output validated against the taxonomy and a
   rule-based fallback. *Exit:* beats the rule parser on a held-out query set without regressing parser-trap
   cases; cost per query recorded.
7. **Semantic retrieval (pgvector)** for free-text that misses the lexicon. *Exit:* measurable P@5 gain on
   keyword-category queries over full-text search.
8. **Feedback loop.** Use "wrong mood", "too long" and "not what I meant" to tune weights and find classification
   errors. *Exit:* weekly report of feedback by term, and one weight change justified by data.

Later, gated on step 4 showing value: accounts and saved lists, availability, YouTube reviews and reactions via
authorised embeds, community reviews with spoiler separation, and creator pages.

## 8. The first vertical slice (implemented)

**Experience:** a user types what they want, sees how it was understood, gets up to eight results with reasons
labelled by basis (catalogue vs interpretation), sees caveats for anything uncertain or unmet, can open a work
page that answers the directive's work-page questions, and can leave one-tap feedback.

**Acceptance criteria and status:**

| # | Criterion | Status |
| --- | --- | --- |
| 1 | A natural-language query returns ranked results without needing an account | ✅ |
| 2 | The interpretation (medium, wants, avoids, limits, notes) is shown to the user | ✅ |
| 3 | Hard constraints exclude; soft preferences only penalise, and the penalty is explained | ✅ unit tests |
| 4 | Unknown data is never treated as satisfying a constraint (unassessed advisories and unknown lengths carry caveats) | ✅ unit + benchmark |
| 5 | Every reason is derived from stored evidence and labelled catalogue or interpretation; no free-form generated text | ✅ |
| 6 | Requested qualities a result lacks are stated as caveats | ✅ |
| 7 | Cross-medium "like X" works, and uses factual relationships when present | ✅ benchmark |
| 8 | Queries with nothing relevant return nothing, with a message | ✅ benchmark |
| 9 | Work pages show classifications with strength and basis, advisories ("not assessed" when missing), relationships, credits and sources; spoilers hidden by default | ✅ |
| 10 | Feedback is recorded against the discovery event | ✅ integration + browser test |
| 11 | Re-running the import changes nothing; an invalid import writes nothing | ✅ integration tests |
| 12 | The benchmark runs in CI as a regression gate | ✅ (`test_benchmark_passes`) |
| 13 | Usable at phone width with no horizontal scrolling | ✅ checked at 375 px |
