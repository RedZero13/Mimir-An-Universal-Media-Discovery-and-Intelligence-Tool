-- 0005: accounts and community. Personal data is kept to what the features need: a username, a display name, an
-- email for sign-in, a password hash. Deleting an account deletes everything it wrote (ON DELETE CASCADE).

CREATE TABLE app_user (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    username        text NOT NULL CHECK (username ~ '^[a-z0-9_]{3,24}$'),
    email           text NOT NULL CHECK (length(email) <= 254),
    display_name    text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 60),
    bio             text NOT NULL DEFAULT '' CHECK (length(bio) <= 300),
    password_hash   text NOT NULL,
    is_private      boolean NOT NULL DEFAULT false,   -- private: reviews and activity visible to followers only
    share_activity  boolean NOT NULL DEFAULT true,    -- post "finished" / "started" to followers
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX app_user_username ON app_user (username);
CREATE UNIQUE INDEX app_user_email ON app_user (lower(email));

-- Bearer tokens: only a SHA-256 of each token is stored.
CREATE TABLE user_session (
    token_hash      text PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL
);
CREATE INDEX user_session_user ON user_session (user_id);

-- The private library (statuses, scores, progress, lists, journal, ratings) as the client keeps it, synced whole.
CREATE TABLE user_state (
    user_id         uuid PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
    data            jsonb NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE follow (
    follower_id     uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    followee_id     uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (follower_id, followee_id),
    CHECK (follower_id <> followee_id)
);
CREATE INDEX follow_followee ON follow (followee_id);

CREATE TABLE review (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    work_id         uuid NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    score           smallint CHECK (score BETWEEN 1 AND 10),
    body            text NOT NULL DEFAULT '' CHECK (length(body) <= 5000),
    spoiler         boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, work_id),
    CHECK (score IS NOT NULL OR length(body) > 0)
);
CREATE INDEX review_work ON review (work_id, created_at DESC);
CREATE INDEX review_recent ON review (created_at DESC);

CREATE TABLE review_like (
    review_id       uuid NOT NULL REFERENCES review(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (review_id, user_id)
);

CREATE TABLE review_comment (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id       uuid NOT NULL REFERENCES review(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX review_comment_review ON review_comment (review_id, created_at);

-- Lists a user chose to publish (private lists stay in user_state).
CREATE TABLE public_list (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    name            text NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    note            text NOT NULL DEFAULT '' CHECK (length(note) <= 200),
    slugs           text[] NOT NULL CHECK (cardinality(slugs) <= 500),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX public_list_user ON public_list (user_id);

-- Social calendar challenges (Spooktober, 12 Days of Christmas …), per year. Slugs come from catalogue/calendar.json.
CREATE TABLE challenge_member (
    challenge_slug  text NOT NULL CHECK (challenge_slug ~ '^[a-z0-9-]{2,60}$'),
    year            smallint NOT NULL CHECK (year BETWEEN 2020 AND 2100),
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    done            smallint[] NOT NULL DEFAULT '{}',   -- day numbers completed
    joined_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (challenge_slug, year, user_id)
);

-- The feed. Rows are written by the endpoints that cause them; ref points at a review, list or challenge.
CREATE TABLE activity (
    id              bigserial PRIMARY KEY,
    user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('review', 'finished', 'started', 'list', 'joined_challenge')),
    work_id         uuid REFERENCES work(id) ON DELETE CASCADE,
    ref             text,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX activity_user ON activity (user_id, created_at DESC);
CREATE INDEX activity_recent ON activity (created_at DESC);

CREATE TABLE report (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_id     uuid REFERENCES app_user(id) ON DELETE SET NULL,
    target_kind     text NOT NULL CHECK (target_kind IN ('review', 'comment', 'user', 'list')),
    target_id       text NOT NULL CHECK (length(target_id) <= 100),
    reason          text NOT NULL CHECK (length(reason) BETWEEN 1 AND 500),
    created_at      timestamptz NOT NULL DEFAULT now(),
    resolved        boolean NOT NULL DEFAULT false
);
