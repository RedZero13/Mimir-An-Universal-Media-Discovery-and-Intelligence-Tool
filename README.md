# Universal Media Discovery

Describe what you want to experience: a mood, an idea, a favourite work, a time limit. Get a few well-chosen films,
books, games or albums back, each with the reasons it fits.

This is the first vertical slice. A user writes a request in plain language. The system interprets it into
inspectable constraints and preferences, ranks a classified catalogue against them, and explains every result
from recorded evidence. Facts are labelled separately from interpretations.

- **Project assessment, architecture, data model, roadmap:** [`docs/ASSESSMENT.md`](docs/ASSESSMENT.md)
- **Taxonomy and classification specification:** [`docs/TAXONOMY.md`](docs/TAXONOMY.md)
- **Data sources and licensing register:** [`docs/SOURCES.md`](docs/SOURCES.md)

## Layout

```
api/                    Python 3.11+, FastAPI, PostgreSQL (modular monolith)
  mde/migrations/       SQL migrations, applied in order, additive only
  mde/taxonomy/         Controlled taxonomy (taxonomy.json) + loader/validator
  mde/seed/             Pilot catalogue (56 works)
  mde/catalogue/        Import (load.py) and read-side queries (repository.py)
  mde/discovery/        intent.py → rank.py → explain.py, orchestrated by engine.py
  mde/app.py            HTTP API
  benchmark/            Discovery benchmark (queries.json) and runner
  tests/                Unit tests + integration tests against a throwaway database
web/                    Next.js 15 + TypeScript (server components; no client-side API calls)
```

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
cd api && ruff check . && pytest -q          # 36 tests; DB tests skip if PostgreSQL is unreachable
cd web && npm run typecheck && npm run build
```

CI (`.github/workflows/ci.yml`) runs the same checks against a PostgreSQL 16 service.

## API

| Method | Path | |
| --- | --- | --- |
| GET | `/api/discover?q=…&limit=8` | Interpretation, ranked results with reasons, caveats and score breakdowns, and the exclusion counts. Logs an anonymous discovery event |
| GET | `/api/works/{slug}` | Work page data: credits, classifications with origin/confidence/review status, relationships, provenance, sources |
| GET | `/api/taxonomy` | The controlled vocabulary |
| POST | `/api/feedback` | `{event_id, work_slug, kind}` where kind is one of `relevant`, `irrelevant`, `too_long`, `wrong_mood`, `already_experienced`, `not_what_i_meant`, `will_try` |
| GET | `/api/health` | |

## Known limitations

- **Pilot data is unverified.** Years, runtimes and credits were compiled from general knowledge and have not
  been checked against primary sources. Every classification is an AI-assisted interpretation awaiting editorial
  review. The UI and the API say so on every item.
- **The catalogue is small (56 works)**, and the benchmark was written alongside the system by the same author.
  It catches regressions, but it doesn't prove relevance. Independent judgements from real users are the next step.
- The intent parser is rule-based. It covers the phrasing in the benchmark and tests, and will miss phrasings
  outside its lexicon. An LLM-backed parser can implement the same `IntentParser` interface.
- Ranking happens in memory over the whole catalogue. That is fine for hundreds of works; retrieval needs to move
  into SQL/pgvector before tens of thousands.
- Feedback is stored but not yet used to adjust ranking.
- No accounts, availability data, reviews, or online video in the catalogue yet. The schema has room for them.
