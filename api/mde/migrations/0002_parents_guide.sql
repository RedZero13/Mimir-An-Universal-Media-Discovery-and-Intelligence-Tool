-- 0002: parents' guide support.
-- classification.evidence already holds a non-spoiler note; spoiler detail is kept separately so it can be
-- hidden by default.
ALTER TABLE classification ADD COLUMN spoiler_evidence text;

-- Official age ratings (MPA, BBFC, ESRB, PEGI, …), one per system per work.
CREATE TABLE content_rating (
    work_id     uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    system      text NOT NULL,
    rating      text NOT NULL,
    reason      text,
    source_id   smallint NOT NULL REFERENCES source(id),
    PRIMARY KEY (work_id, system)
);
