-- 0003: open-source enrichment: raw source records, images, scores, box office, series groups, links.

-- Raw payloads exactly as fetched, so every merged value can be traced and re-derived.
CREATE TABLE source_record (
    id          bigserial PRIMARY KEY,
    source_id   smallint NOT NULL REFERENCES source(id),
    external_id text NOT NULL,                 -- QID, Open Library key, MusicBrainz MBID …
    work_id     uuid REFERENCES work(id) ON DELETE SET NULL,
    payload     jsonb NOT NULL,
    fetched_at  timestamptz NOT NULL,
    UNIQUE (source_id, external_id)
);

-- Posters, covers and stills. Only metadata and a cache path are stored; the licence travels with the image.
CREATE TABLE work_image (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('poster', 'cover', 'still', 'logo')),
    url         text NOT NULL,
    source_id   smallint NOT NULL REFERENCES source(id),
    licence     text NOT NULL,                 -- e.g. 'CC BY-SA 4.0', 'cover thumbnail (identification only)'
    attribution text,
    width       integer,
    height      integer,
    PRIMARY KEY (work_id, kind, source_id)
);

-- Critic and audience scores as published by a source (never computed by us).
CREATE TABLE work_score (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    publisher   text NOT NULL,                 -- 'Rotten Tomatoes', 'Metacritic', 'Open Library readers' …
    metric      text NOT NULL,                 -- 'tomatometer', 'metascore', 'average rating' …
    value       numeric NOT NULL,
    scale_max   numeric NOT NULL,
    votes       integer,
    source_id   smallint NOT NULL REFERENCES source(id),   -- where we got it (e.g. Wikidata), not the publisher
    as_of       date,
    PRIMARY KEY (work_id, publisher, metric, source_id)
);

CREATE TABLE box_office (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    scope       text NOT NULL,                 -- 'worldwide', 'US & Canada' …
    amount      numeric NOT NULL,
    currency    text NOT NULL,
    source_id   smallint NOT NULL REFERENCES source(id),
    PRIMARY KEY (work_id, scope, source_id)
);

-- Series, franchises and collections, with an optional reading/viewing order.
CREATE TABLE work_group (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text NOT NULL UNIQUE,
    name        text NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('series', 'franchise', 'collection', 'universe')),
    source_id   smallint NOT NULL REFERENCES source(id)
);

CREATE TABLE work_group_member (
    group_id    uuid NOT NULL REFERENCES work_group(id) ON DELETE CASCADE,
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    position    numeric,                       -- 1, 2, 2.5 … NULL when order isn't meaningful
    PRIMARY KEY (group_id, work_id)
);

-- Outbound links: official pages, audience-reaction pages, listening links.
CREATE TABLE work_link (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    kind        text NOT NULL,                 -- 'reactions:letterboxd', 'listen:spotify', 'wikidata' …
    url         text NOT NULL,
    label       text NOT NULL,
    PRIMARY KEY (work_id, kind)
);

-- Music: tracks belong to albums; remixes point at what they remix.
INSERT INTO relationship_type (slug, label, inverse, is_symmetric, factual) VALUES
    ('track_of', 'is a track on', 'includes the track', false, true),
    ('remix_of', 'is a remix of', 'was remixed as', false, true),
    ('spin_off_of', 'is a spin-off of', 'spun off', false, true);
