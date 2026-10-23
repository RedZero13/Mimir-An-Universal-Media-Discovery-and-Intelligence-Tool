-- 0006: watch-alongs. Someone plans to watch a work (now, at a time, or whenever), everyone watches on their own
-- screen, and comments are pinned to how far into the work they were written, so they surface at the same moment
-- for everyone who watches along later.

CREATE TABLE watch_along (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    work_id         uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    starts_at       timestamptz,                       -- NULL: watch whenever you like
    note            text NOT NULL DEFAULT '' CHECK (length(note) <= 300),
    is_open         boolean NOT NULL DEFAULT true,     -- closed watch-alongs keep their comments but leave the listings
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX watch_along_open ON watch_along (is_open, created_at DESC);
CREATE INDEX watch_along_work ON watch_along (work_id);

CREATE TABLE watch_along_comment (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_along_id  uuid NOT NULL REFERENCES watch_along(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    at_seconds      integer NOT NULL CHECK (at_seconds BETWEEN 0 AND 172800),
    body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 1000),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX watch_along_comment_time ON watch_along_comment (watch_along_id, at_seconds);
