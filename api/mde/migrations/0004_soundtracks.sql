-- 0004: soundtracks link an album to the film, series or game it was written for.
INSERT INTO relationship_type (slug, label, inverse, is_symmetric, factual) VALUES
    ('soundtrack_of', 'is the soundtrack of', 'has the soundtrack', false, true);
