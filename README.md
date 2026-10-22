<img src="brand/lockup-horizontal.svg" alt="Mimir, a Terratales venture" height="56">

# Mimir

**Drawn from the well of every story.** Mimir is a catalogue and discovery engine for films, TV series, books,
games and music, built as *A Terratales Venture* for [terratalesmedia.world](https://terratalesmedia.world/).
The beta catalogue holds 503 works from 28 original languages.

Describe what you want to experience: a mood, an idea, a favourite work, a time limit. Mimir returns a few
well-chosen picks, each with the reasons it fits.

Under the hood, a request in plain language is interpreted into inspectable constraints and preferences, a
classified catalogue is ranked against them, and every result is explained from recorded evidence. Facts are
labelled separately from interpretations.

It is also a browsable catalogue, in the spirit of IMDb: filter by medium, tag, decade, language, length and
parents'-guide category; open tag pages and people pages; and read full work pages with tags, credits,
connected works and a parents' guide that tells "none" apart from "not assessed".

- **Beta testers start here:** [`docs/BETA.md`](docs/BETA.md)
- **Brand guide (name, mark, colour, type, voice):** [`docs/BRAND.md`](docs/BRAND.md)
- **Putting it on terratalesmedia.world:** [`docs/DEPLOY.md`](docs/DEPLOY.md)
- **Project assessment, architecture, data model, roadmap:** [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md)
- **Taxonomy and classification specification:** [`docs/TAXONOMY.md`](docs/TAXONOMY.md)
- **Data sources and licensing register:** [`docs/SOURCES.md`](docs/SOURCES.md)

## Layout

```
api/                    Python 3.11+, FastAPI, PostgreSQL (modular monolith)
  mde/migrations/       SQL migrations, applied in order, additive only
  mde/taxonomy/         Controlled taxonomy (taxonomy.json) + loader/validator
  mde/seed/             Editorial seed: catalogue.json (the 56-work pilot) plus films, films-world, series,
                        books, games and albums (*.json), merged by catalogue/seedfiles.py
  mde/data/enrichment/  Open-data enrichment written by `python -m mde ingest` (Wikidata, Open Library, MusicBrainz)
  mde/ingest/           Connectors, matching rules and the HTTP cache
  mde/catalogue/        Import (load.py) and read-side queries (repository.py)
  mde/discovery/        intent.py → rank.py → explain.py, orchestrated by engine.py
  mde/app.py            HTTP API
  benchmark/            Discovery benchmark (queries.json) and runner
  tests/                Unit tests + integration tests against a throwaway database
web/                    Next.js 15 + TypeScript (server components; no client-side API calls)
brand/                  Mimir mark, lockups, icons and social card (see docs/BRAND.md)
demo/                   The public single-page site: a JavaScript port of the pure pipeline (engine.cjs),
                        kept identical to the Python by api/tests/test_demo_parity.py
```

## Public site

`node demo/build.cjs --site` writes `demo/dist/site/`, the deployable static site for
`mimir.terratalesmedia.world`, with a full `<head>`, icons, social card and CNAME. `.github/workflows/pages.yml`
publishes it on every push to `main` (setup in `docs/DEPLOY.md`). `node demo/build.cjs` alone writes a single
self-contained page that runs the discovery
pipeline (intent parsing, ranking, explanations) on the pilot catalogue with no server. Differences from the
full stack: keyword search is a simple word match instead of PostgreSQL full-text search, and feedback stays in
the viewer's browser. `pytest` runs the JavaScript and Python engines side by side on every benchmark query plus
about 40 edge cases, and fails if their output differs in any field.

## Running locally

Requirements: Python 3.11+, Node 22, PostgreSQL 16.

```bash
# 1. Database
createdb mde                       # or any database; set DATABASE_URL accordingly

# 2. API
cd api
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mde
python -m mde setup                # apply migrations + import the pilot catalogue (safe to re-run)
uvicorn mde.app:app --port 8000

# 3. Web (another terminal)
cd web
npm ci
API_URL=http://localhost:8000 npm run dev     # http://localhost:3000
```

Try it from the command line too:

```bash
python -m mde discover "a book like Outer Wilds"
python -m mde benchmark
```

### Environment variables

| Variable | Used by | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | api | `postgresql://postgres:postgres@localhost:5432/mde` | Catalogue database |
| `CORS_ORIGINS` | api | `http://localhost:3000` | Comma-separated browser origins (the web app calls the API server-side, so this only matters for direct browser use) |
| `API_URL` | web | `http://localhost:8000` | Where the web server reaches the API |
| `TEST_DATABASE_ADMIN_URL` | tests | `postgresql://postgres:postgres@localhost:5432/postgres` | Tests create and drop their own database through this connection |

No API keys are needed. The slice uses no external providers and no LLM.

## Checks

```bash
cd api && ruff check . && pytest -q          # DB tests skip without PostgreSQL, parity tests without Node
cd web && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks against a PostgreSQL 16 service.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/discover?q=…&limit=8` | Interpretation, ranked results with reasons, caveats and score breakdowns, and the exclusion counts. Logs an anonymous discovery event |
| GET | `/api/works?medium=&tag=&avoid=&decade=&language=&country=&max_minutes=&q=&sort=` | Browse: filtered, sorted work cards plus facet counts. `tag` and `avoid` take taxonomy keys and repeat; `avoid` keeps works assessed as none or mild |
| GET | `/api/works/{slug}` | Work page: facts, credits, tags by dimension, parents' guide (official ratings plus per-category severity and notes), connected works, provenance, sources |
| GET | `/api/tags`, `/api/tags/{dimension}/{slug}` | Tag index with counts; a tag's definition, its works (strongest first) and related tags |
| GET | `/api/people`, `/api/people/{slug}` | Everyone credited; a person's or studio's works, roles and recurring qualities |
| GET | `/api/works/{slug}/where?region=IN` | Where to watch, listen, read or play: a link per service for that region (search links unless the catalogue holds an exact ID) |
| GET | `/api/shelves`, `/api/shelves/{slug}` | Wordplay shelves (Laugh Riot, Drama Mamas, Nepo Babies, Desi Delights …) |
| GET | `/api/groups`, `/api/groups/{slug}` | Series and franchise families, in order, with total time |
| GET | `/api/music/moods`, `/api/music/remixes` | Mood rings and the remix rack |
| POST | `/api/recommend` | `{ratings: {slug: loved\|liked\|disliked}, limit, medium}` → taste profile and picks, each with the work it resembles and the qualities it shares |
| GET | `/api/taxonomy` | The controlled vocabulary |
| POST | `/api/feedback` | `{event_id, work_slug, kind}` where kind is one of `relevant`, `irrelevant`, `too_long`, `wrong_mood`, `already_experienced`, `not_what_i_meant`, `will_try` |
| GET | `/api/health` | |

## Known limitations

- **Facts are partly verified.** Where Wikidata, Open Library or MusicBrainz match a work, their year, length,
  page count, scores, box office, covers and track lists are used and the page says which source each came from
  (and what the seed said). Everything else was compiled from general knowledge and is unverified. Every tag,
  summary and parents' guide level is an AI-assisted reading awaiting editorial review; the UI says so.
- **Episode counts for running TV series** are as compiled and will drift; they are not yet fetched.
- **"Where to watch" links open each service's search.** Mimir cannot confirm a title is on a service in your
  region; that needs a licensed availability feed (e.g. a JustWatch partnership).
- **Posters for films, TV and games** need a TMDB or IGDB agreement; until then those works use generated covers.
  Book and album covers come from Open Library and the Cover Art Archive.
- The benchmark (20 queries) was written alongside the system. It catches regressions but doesn't prove
  relevance. The beta's job is to gather real judgements.
- The intent parser is rule-based. It covers the phrasing in the benchmark and tests and will miss some phrasings.
  An LLM-backed parser can implement the same `IntentParser` interface.
- Ranking, browse and recommendations run in memory over the whole catalogue: fine for thousands of works;
  retrieval needs to move into SQL/pgvector before tens of thousands.
- Ratings, shelves and feedback on the public site stay in the viewer's browser. There are no accounts yet.
