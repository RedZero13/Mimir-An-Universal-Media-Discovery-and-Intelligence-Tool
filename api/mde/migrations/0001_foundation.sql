-- 0001: catalogue foundation.
-- Additive-only from here on: later migrations add tables/columns, they do not rewrite these.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- sources
-- The source permission register. Every imported fact points at a row here.
CREATE TABLE source (
    id              smallserial PRIMARY KEY,
    slug            text NOT NULL UNIQUE,
    name            text NOT NULL,
    kind            text NOT NULL CHECK (kind IN ('official_api', 'licensed_dataset', 'open_dataset',
                                                  'editorial', 'ai_assisted', 'community', 'user')),
    licence         text,
    commercial_use  text NOT NULL DEFAULT 'unknown' CHECK (commercial_use IN ('yes', 'no', 'restricted', 'unknown')),
    may_store       text NOT NULL DEFAULT 'unknown' CHECK (may_store IN ('yes', 'no', 'restricted', 'unknown')),
    may_display     text NOT NULL DEFAULT 'unknown' CHECK (may_display IN ('yes', 'no', 'restricted', 'unknown')),
    ai_use          text NOT NULL DEFAULT 'unknown' CHECK (ai_use IN ('yes', 'no', 'restricted', 'unknown')),
    attribution     text,
    max_cache_days  integer,
    notes           text
);

-- ---------------------------------------------------------------- media types
-- A lookup table rather than an enum, so new media need an INSERT, not a type migration.
CREATE TABLE medium (
    slug        text PRIMARY KEY,
    label       text NOT NULL,
    family      text NOT NULL CHECK (family IN ('screen', 'written', 'interactive', 'audio', 'online', 'other'))
);

INSERT INTO medium (slug, label, family) VALUES
    ('film', 'Film', 'screen'),
    ('series', 'Series', 'screen'),
    ('episode', 'Episode', 'screen'),
    ('book', 'Book', 'written'),
    ('comic', 'Comic / graphic novel', 'written'),
    ('game', 'Video game', 'interactive'),
    ('album', 'Album', 'audio'),
    ('track', 'Track', 'audio'),
    ('podcast', 'Podcast', 'audio'),
    ('online_video', 'Online video', 'online'),
    ('channel', 'Online channel', 'online');

-- ---------------------------------------------------------------- works
-- A work is the abstract creation. Editions/releases/versions are separate (see 'manifestation').
CREATE TABLE work (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                text NOT NULL UNIQUE,
    medium              text NOT NULL REFERENCES medium(slug),
    title               text NOT NULL,
    original_title      text,
    original_language   text,              -- ISO 639-1
    countries           text[] NOT NULL DEFAULT '{}',   -- ISO 3166-1 alpha-2
    release_year        smallint,
    release_date        date,
    summary             text,              -- non-spoiler
    summary_spoiler     text,              -- may contain spoilers; never shown by default
    -- Typed, cross-medium length measures. NULL means unknown, never zero.
    runtime_minutes     integer CHECK (runtime_minutes > 0),          -- film/episode/album
    page_count          integer CHECK (page_count > 0),               -- book (edition-dependent; prefer manifestation)
    playtime_hours      numeric(6,1) CHECK (playtime_hours > 0),      -- game, main path
    length_is_estimate  boolean NOT NULL DEFAULT false,
    -- 1 = household name … 4 = little known. Editorial estimate used only for novelty ranking.
    popularity_tier     smallint CHECK (popularity_tier BETWEEN 1 AND 4),
    -- Uncommon, medium-specific properties only. Anything queried routinely gets a column.
    attributes          jsonb NOT NULL DEFAULT '{}',
    status              text NOT NULL DEFAULT 'released' CHECK (status IN ('announced', 'released', 'cancelled')),
    advisories_assessed boolean NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    search              tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(original_title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(summary, '')), 'B')
    ) STORED
);
CREATE INDEX work_medium_idx ON work (medium);
CREATE INDEX work_search_idx ON work USING gin (search);

CREATE TABLE work_title (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    title       text NOT NULL,
    language    text,
    kind        text NOT NULL DEFAULT 'alternative' CHECK (kind IN ('alternative', 'original', 'transliteration', 'working')),
    PRIMARY KEY (work_id, title)
);
CREATE INDEX work_title_lower_idx ON work_title (lower(title));

CREATE TABLE manifestation (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    kind        text NOT NULL,    -- edition, cut, remaster, platform release, pressing …
    label       text NOT NULL,
    released    date,
    attributes  jsonb NOT NULL DEFAULT '{}'
);

CREATE TABLE external_id (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    source_id   smallint NOT NULL REFERENCES source(id),
    value       text NOT NULL,
    PRIMARY KEY (source_id, value)
);

-- ---------------------------------------------------------------- people & organisations
CREATE TABLE person (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug    text NOT NULL UNIQUE,
    name    text NOT NULL
);

CREATE TABLE organisation (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug    text NOT NULL UNIQUE,
    name    text NOT NULL
);

CREATE TABLE credit (
    id              bigserial PRIMARY KEY,
    work_id         uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    person_id       uuid REFERENCES person(id),
    organisation_id uuid REFERENCES organisation(id),
    role            text NOT NULL,   -- director, author, developer, artist, cinematographer, publisher …
    ordinal         smallint NOT NULL DEFAULT 0,
    source_id       smallint NOT NULL REFERENCES source(id),
    CHECK ((person_id IS NULL) <> (organisation_id IS NULL))
);
CREATE UNIQUE INDEX credit_unique_idx ON credit (work_id, role, coalesce(person_id, organisation_id));

-- ---------------------------------------------------------------- taxonomy
CREATE TABLE taxonomy_dimension (
    slug        text PRIMARY KEY,
    label       text NOT NULL,
    description text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('categorical', 'graded', 'intensity'))
);

CREATE TABLE taxonomy_term (
    id                  serial PRIMARY KEY,
    dimension           text NOT NULL REFERENCES taxonomy_dimension(slug),
    slug                text NOT NULL,
    label               text NOT NULL,
    definition          text NOT NULL,
    applies_to          text[] NOT NULL DEFAULT '{*}',
    synonyms            text[] NOT NULL DEFAULT '{}',
    version_introduced  text NOT NULL,
    deprecated          boolean NOT NULL DEFAULT false,
    UNIQUE (dimension, slug)
);

-- A classification is a claim about a work, with its origin and confidence kept alongside.
CREATE TABLE classification (
    id                  bigserial PRIMARY KEY,
    work_id             uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    term_id             integer NOT NULL REFERENCES taxonomy_term(id),
    strength            real NOT NULL CHECK (strength BETWEEN 0 AND 1),    -- how strongly the term applies
    confidence          real NOT NULL CHECK (confidence BETWEEN 0 AND 1),  -- how sure we are of that
    origin              text NOT NULL CHECK (origin IN ('source', 'editorial', 'ai_assisted', 'community', 'derived')),
    is_interpretation   boolean NOT NULL DEFAULT true,
    is_spoiler          boolean NOT NULL DEFAULT false,
    evidence            text,
    source_id           smallint NOT NULL REFERENCES source(id),
    review_status       text NOT NULL DEFAULT 'unreviewed' CHECK (review_status IN ('unreviewed', 'reviewed', 'disputed', 'rejected')),
    taxonomy_version    text NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (work_id, term_id, origin)
);
CREATE INDEX classification_term_idx ON classification (term_id, strength);

-- ---------------------------------------------------------------- relationships
CREATE TABLE relationship_type (
    slug        text PRIMARY KEY,
    label       text NOT NULL,       -- reads "A <label> B"
    inverse     text NOT NULL,       -- reads "B <inverse> A"
    is_symmetric boolean NOT NULL DEFAULT false,
    factual     boolean NOT NULL     -- true: verifiable fact (adaptation); false: interpretation (kinship)
);

INSERT INTO relationship_type (slug, label, inverse, is_symmetric, factual) VALUES
    ('adaptation_of', 'is an adaptation of', 'was adapted as', false, true),
    ('sequel_of', 'is a sequel to', 'is followed by', false, true),
    ('remake_of', 'is a remake of', 'was remade as', false, true),
    ('same_universe', 'shares a fictional universe with', 'shares a fictional universe with', true, true),
    ('same_creator', 'shares a creator with', 'shares a creator with', true, true),
    ('influenced_by', 'was influenced by', 'influenced', false, false),
    ('thematic_kin', 'explores similar questions to', 'explores similar questions to', true, false),
    ('similar_experience', 'offers a similar experience to', 'offers a similar experience to', true, false),
    ('contrasting_take', 'offers a contrasting take on the themes of', 'offers a contrasting take on the themes of', true, false);

CREATE TABLE relationship (
    id              bigserial PRIMARY KEY,
    from_work_id    uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    to_work_id      uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    type            text NOT NULL REFERENCES relationship_type(slug),
    note            text,             -- what specifically connects them
    confidence      real NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    origin          text NOT NULL CHECK (origin IN ('source', 'editorial', 'ai_assisted', 'community', 'derived')),
    is_spoiler      boolean NOT NULL DEFAULT false,
    source_id       smallint NOT NULL REFERENCES source(id),
    review_status   text NOT NULL DEFAULT 'unreviewed' CHECK (review_status IN ('unreviewed', 'reviewed', 'disputed', 'rejected')),
    CHECK (from_work_id <> to_work_id),
    UNIQUE (from_work_id, to_work_id, type)
);

-- ---------------------------------------------------------------- provenance
-- Field-level provenance for scalar facts on works (runtime, year, …), including conflicting values.
CREATE TABLE field_provenance (
    id          bigserial PRIMARY KEY,
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    field       text NOT NULL,
    value       jsonb NOT NULL,
    source_id   smallint NOT NULL REFERENCES source(id),
    is_selected boolean NOT NULL DEFAULT true,   -- the value currently shown on the work
    observed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (work_id, field, source_id)
);

CREATE TABLE import_run (
    id          bigserial PRIMARY KEY,
    source_id   smallint NOT NULL REFERENCES source(id),
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    stats       jsonb NOT NULL DEFAULT '{}',
    errors      jsonb NOT NULL DEFAULT '[]'
);

-- ---------------------------------------------------------------- discovery events & feedback
-- Anonymous by design: no user identity until accounts exist.
CREATE TABLE discovery_event (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query       text NOT NULL,
    intent      jsonb NOT NULL,
    results     jsonb NOT NULL,        -- [{slug, rank, score}]
    ranker      text NOT NULL,         -- ranker version, for comparing changes
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    id          bigserial PRIMARY KEY,
    event_id    uuid REFERENCES discovery_event(id) ON DELETE SET NULL,
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('relevant', 'irrelevant', 'too_long', 'wrong_mood',
                                              'already_experienced', 'not_what_i_meant', 'will_try')),
    note        text CHECK (length(note) <= 1000),
    created_at  timestamptz NOT NULL DEFAULT now()
);
