"""Accounts and community: sign-up and sign-in, a synced private library, reviews with likes and comments,
follows, an activity feed, trending works, public lists, calendar challenges and reports.

Passwords are hashed with scrypt; sessions are random bearer tokens of which only a SHA-256 is stored. Clients send
`Authorization: Bearer <token>`. Nothing here is required for the catalogue or discovery endpoints.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from mde import db

router = APIRouter(prefix="/api")

SESSION_DAYS = 90
STATE_MAX_BYTES = 2_000_000
USERNAME = re.compile(r"^[a-z0-9_]{3,24}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RESERVED = {"admin", "mimir", "terratales", "support", "moderator", "staff", "api", "me", "null", "undefined"}
CALENDAR = Path(__file__).parent / "catalogue" / "calendar.json"


# ---------------------------------------------------------------- passwords and tokens
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(base64.b64decode(digest)))
        return hmac.compare_digest(got, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_session(conn, user_id) -> str:
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO user_session (token_hash, user_id, expires_at) VALUES (%s, %s, %s)",
                 (_token_hash(token), user_id, datetime.now(UTC) + timedelta(days=SESSION_DAYS)))
    return token


# A small in-process limiter for sign-up and sign-in attempts per client address. Enough for one instance; a shared
# store (or the hosting platform's limiter) replaces it when the API runs on several.
_attempts: dict[str, deque] = defaultdict(deque)


def _limit(request: Request, bucket: str, per_minute: int = 10) -> None:
    key = f"{bucket}:{request.client.host if request.client else '?'}"
    now = time.monotonic()
    q = _attempts[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= per_minute:
        raise HTTPException(429, "too many attempts; wait a minute and try again")
    q.append(now)


def _user_from_header(authorization: str | None) -> dict | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    with db.connect() as conn:
        return conn.execute(
            "SELECT u.* FROM user_session s JOIN app_user u ON u.id = s.user_id WHERE s.token_hash = %s AND s.expires_at > now()",
            (_token_hash(authorization[7:].strip()),)).fetchone()


def optional_user(authorization: Annotated[str | None, Header()] = None) -> dict | None:
    return _user_from_header(authorization)


def current_user(authorization: Annotated[str | None, Header()] = None) -> dict:
    user = _user_from_header(authorization)
    if user is None:
        raise HTTPException(401, "sign in required")
    return user


User = Annotated[dict, Depends(current_user)]
MaybeUser = Annotated[dict | None, Depends(optional_user)]


def public_user(u: dict) -> dict:
    return {"username": u["username"], "display_name": u["display_name"]}


def _me(u: dict) -> dict:
    return {**public_user(u), "email": u["email"], "bio": u["bio"], "is_private": u["is_private"],
            "share_activity": u["share_activity"], "created_at": u["created_at"].isoformat()}


def _work_id(conn, slug: str):
    row = conn.execute("SELECT id FROM work WHERE slug = %s", (slug,)).fetchone()
    if row is None:
        raise HTTPException(404, "work not found")
    return row["id"]


def _user_by_name(conn, username: str) -> dict:
    row = conn.execute("SELECT * FROM app_user WHERE username = %s", (username.lower(),)).fetchone()
    if row is None:
        raise HTTPException(404, "user not found")
    return row


def _can_see(conn, viewer: dict | None, owner: dict) -> bool:
    """Private accounts show their reviews and activity to followers (and themselves) only."""
    if not owner["is_private"] or (viewer and viewer["id"] == owner["id"]):
        return True
    return bool(viewer and conn.execute("SELECT 1 FROM follow WHERE follower_id = %s AND followee_id = %s",
                                        (viewer["id"], owner["id"])).fetchone())


VISIBLE = "(NOT u.is_private OR u.id = %(viewer)s OR EXISTS (SELECT 1 FROM follow f WHERE f.follower_id = %(viewer)s AND f.followee_id = u.id))"


# ---------------------------------------------------------------- accounts
class SignupIn(BaseModel):
    username: str = Field(min_length=3, max_length=24)
    display_name: str = Field(min_length=1, max_length=60)
    email: str = Field(max_length=254)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    login: str = Field(min_length=1, max_length=254, description="username or email")
    password: str = Field(min_length=1, max_length=200)


@router.post("/auth/signup", status_code=201)
def signup(body: SignupIn, request: Request) -> dict:
    _limit(request, "signup", 5)
    username = body.username.strip().lower()
    if not USERNAME.match(username) or username in RESERVED:
        raise HTTPException(422, "usernames are 3–24 lowercase letters, numbers or underscores")
    if not EMAIL.match(body.email.strip()):
        raise HTTPException(422, "that email address doesn't look right")
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM app_user WHERE username = %s", (username,)).fetchone():
            raise HTTPException(409, "that username is taken")
        if conn.execute("SELECT 1 FROM app_user WHERE lower(email) = lower(%s)", (body.email.strip(),)).fetchone():
            raise HTTPException(409, "an account already uses that email")
        user = conn.execute(
            "INSERT INTO app_user (username, email, display_name, password_hash) VALUES (%s, %s, %s, %s) RETURNING *",
            (username, body.email.strip(), body.display_name.strip(), hash_password(body.password))).fetchone()
        token = _new_session(conn, user["id"])
        conn.commit()
    return {"token": token, "user": _me(user)}


@router.post("/auth/login")
def login(body: LoginIn, request: Request) -> dict:
    _limit(request, "login", 10)
    with db.connect() as conn:
        user = conn.execute("SELECT * FROM app_user WHERE username = lower(%s) OR lower(email) = lower(%s)",
                            (body.login.strip(), body.login.strip())).fetchone()
        if user is None or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(401, "wrong username or password")
        token = _new_session(conn, user["id"])
        conn.execute("DELETE FROM user_session WHERE user_id = %s AND expires_at < now()", (user["id"],))
        conn.commit()
    return {"token": token, "user": _me(user)}


@router.post("/auth/logout")
def logout(user: User, authorization: Annotated[str | None, Header()] = None) -> dict:
    with db.connect() as conn:
        conn.execute("DELETE FROM user_session WHERE token_hash = %s", (_token_hash(authorization[7:].strip()),))
        conn.commit()
    return {"ok": True}


@router.get("/me")
def me(user: User) -> dict:
    return _me(user)


class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    bio: str | None = Field(default=None, max_length=300)
    is_private: bool | None = None
    share_activity: bool | None = None


@router.patch("/me")
def update_me(body: ProfileIn, user: User) -> dict:
    fields = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump().items() if v is not None}
    if fields:
        sets = ", ".join(f"{k} = %({k})s" for k in fields)
        with db.connect() as conn:
            user = conn.execute(f"UPDATE app_user SET {sets} WHERE id = %(id)s RETURNING *", {**fields, "id": user["id"]}).fetchone()
            conn.commit()
    return _me(user)


class DeleteIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)


@router.post("/me/delete")
def delete_me(body: DeleteIn, user: User) -> dict:
    """Deletes the account and everything it wrote: reviews, comments, likes, lists, follows, activity, library."""
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "wrong password")
    with db.connect() as conn:
        conn.execute("DELETE FROM app_user WHERE id = %s", (user["id"],))
        conn.commit()
    return {"ok": True}


# ---------------------------------------------------------------- the private library, synced
@router.get("/me/state")
def get_state(user: User) -> dict:
    with db.connect() as conn:
        row = conn.execute("SELECT data, updated_at FROM user_state WHERE user_id = %s", (user["id"],)).fetchone()
    return {"data": row["data"] if row else None, "updated_at": row["updated_at"].isoformat() if row else None}


@router.put("/me/state")
async def put_state(request: Request, user: User) -> dict:
    raw = await request.body()
    if len(raw) > STATE_MAX_BYTES:
        raise HTTPException(413, "library too large to sync")
    try:
        data = json.loads(raw)
    except ValueError:
        raise HTTPException(422, "expected JSON") from None
    if not isinstance(data, dict):
        raise HTTPException(422, "expected a JSON object")
    with db.connect() as conn:
        row = conn.execute(
            "INSERT INTO user_state (user_id, data) VALUES (%s, %s) ON CONFLICT (user_id) DO UPDATE "
            "SET data = EXCLUDED.data, updated_at = now() RETURNING updated_at", (user["id"], json.dumps(data))).fetchone()
        conn.commit()
    return {"updated_at": row["updated_at"].isoformat()}


# ---------------------------------------------------------------- follows and profiles
@router.post("/users/{username}/follow")
def follow(username: str, user: User) -> dict:
    with db.connect() as conn:
        target = _user_by_name(conn, username)
        if target["id"] == user["id"]:
            raise HTTPException(422, "you can't follow yourself")
        conn.execute("INSERT INTO follow (follower_id, followee_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user["id"], target["id"]))
        conn.commit()
    return {"following": True}


@router.delete("/users/{username}/follow")
def unfollow(username: str, user: User) -> dict:
    with db.connect() as conn:
        target = _user_by_name(conn, username)
        conn.execute("DELETE FROM follow WHERE follower_id = %s AND followee_id = %s", (user["id"], target["id"]))
        conn.commit()
    return {"following": False}


@router.get("/users/{username}")
def profile(username: str, viewer: MaybeUser) -> dict:
    with db.connect() as conn:
        u = _user_by_name(conn, username)
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM follow WHERE followee_id = %(id)s) AS followers, "
            "(SELECT count(*) FROM follow WHERE follower_id = %(id)s) AS following_count, "
            "(SELECT count(*) FROM review WHERE user_id = %(id)s) AS reviews", {"id": u["id"]}).fetchone()
        following = bool(viewer and conn.execute("SELECT 1 FROM follow WHERE follower_id = %s AND followee_id = %s",
                                                 (viewer["id"], u["id"])).fetchone())
        visible = _can_see(conn, viewer, u)
        out = {**public_user(u), "bio": u["bio"], "is_private": u["is_private"], "joined": u["created_at"].date().isoformat(),
               **counts, "following": following, "is_me": bool(viewer and viewer["id"] == u["id"]), "visible": visible,
               "reviews_recent": [], "lists": [], "activity": []}
        if visible:
            out["reviews_recent"] = _reviews(conn, viewer, "r.user_id = %(owner)s", {"owner": u["id"]}, 20)
            out["lists"] = [_list_out(r, u) for r in conn.execute(
                "SELECT * FROM public_list WHERE user_id = %s ORDER BY updated_at DESC", (u["id"],)).fetchall()]
            out["activity"] = _activity(conn, viewer, "a.user_id = %(owner)s", {"owner": u["id"]}, 30)
    return out


# ---------------------------------------------------------------- reviews, likes, comments
class ReviewIn(BaseModel):
    score: int | None = Field(default=None, ge=1, le=10)
    body: str = Field(default="", max_length=5000)
    spoiler: bool = False


def _reviews(conn, viewer: dict | None, where: str, params: dict, limit: int) -> list[dict]:
    rows = conn.execute(
        f"SELECT r.*, w.slug AS work_slug, w.title AS work_title, w.medium, u.username, u.display_name, "
        f"(SELECT count(*) FROM review_like l WHERE l.review_id = r.id) AS likes, "
        f"(SELECT count(*) FROM review_comment c WHERE c.review_id = r.id) AS comments, "
        f"EXISTS (SELECT 1 FROM review_like l WHERE l.review_id = r.id AND l.user_id = %(viewer)s) AS liked "
        f"FROM review r JOIN app_user u ON u.id = r.user_id JOIN work w ON w.id = r.work_id "
        f"WHERE {where} AND {VISIBLE} ORDER BY r.created_at DESC LIMIT %(limit)s",
        {**params, "viewer": viewer["id"] if viewer else None, "limit": limit}).fetchall()
    return [{"id": str(r["id"]), "work": {"slug": r["work_slug"], "title": r["work_title"], "medium": r["medium"]},
             "user": {"username": r["username"], "display_name": r["display_name"]}, "score": r["score"], "body": r["body"],
             "spoiler": r["spoiler"], "likes": r["likes"], "comments": r["comments"], "liked": r["liked"],
             "mine": bool(viewer and viewer["username"] == r["username"]),
             "created_at": r["created_at"].isoformat(), "edited": r["updated_at"] > r["created_at"] + timedelta(seconds=5)}
            for r in rows]


@router.get("/works/{slug}/reviews")
def work_reviews(slug: str, viewer: MaybeUser, limit: int = Query(50, ge=1, le=200)) -> dict:
    with db.connect() as conn:
        wid = _work_id(conn, slug)
        reviews = _reviews(conn, viewer, "r.work_id = %(wid)s", {"wid": wid}, limit)
        agg = conn.execute("SELECT count(*) AS n, round(avg(score)::numeric, 1) AS mean, count(score) AS scored "
                           "FROM review WHERE work_id = %s", (wid,)).fetchone()
    return {"reviews": reviews, "count": agg["n"], "mean_score": float(agg["mean"]) if agg["mean"] is not None else None,
            "scored": agg["scored"]}


@router.put("/works/{slug}/review")
def put_review(slug: str, body: ReviewIn, user: User) -> dict:
    if body.score is None and not body.body.strip():
        raise HTTPException(422, "give a score, some words, or both")
    with db.connect() as conn:
        wid = _work_id(conn, slug)
        row = conn.execute(
            "INSERT INTO review (user_id, work_id, score, body, spoiler) VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (user_id, work_id) DO UPDATE SET score = EXCLUDED.score, body = EXCLUDED.body, "
            "spoiler = EXCLUDED.spoiler, updated_at = now() RETURNING id, (xmax = 0) AS created",
            (user["id"], wid, body.score, body.body.strip(), body.spoiler)).fetchone()
        if row["created"]:
            conn.execute("INSERT INTO activity (user_id, kind, work_id, ref) VALUES (%s, 'review', %s, %s)", (user["id"], wid, str(row["id"])))
        conn.commit()
    return {"id": str(row["id"]), "created": row["created"]}


@router.delete("/works/{slug}/review")
def delete_review(slug: str, user: User) -> dict:
    with db.connect() as conn:
        wid = _work_id(conn, slug)
        conn.execute("DELETE FROM activity WHERE user_id = %s AND kind = 'review' AND work_id = %s", (user["id"], wid))
        conn.execute("DELETE FROM review WHERE user_id = %s AND work_id = %s", (user["id"], wid))
        conn.commit()
    return {"ok": True}


def _visible_review(conn, review_id: str, viewer: dict | None) -> dict:
    try:
        row = conn.execute("SELECT r.id, u.* FROM review r JOIN app_user u ON u.id = r.user_id WHERE r.id = %s", (review_id,)).fetchone()
    except Exception:   # malformed uuid
        conn.rollback()
        row = None
    if row is None or not _can_see(conn, viewer, row):
        raise HTTPException(404, "review not found")
    return row


@router.post("/reviews/{review_id}/like")
def like(review_id: str, user: User) -> dict:
    with db.connect() as conn:
        _visible_review(conn, review_id, user)
        conn.execute("INSERT INTO review_like (review_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", (review_id, user["id"]))
        conn.commit()
    return {"liked": True}


@router.delete("/reviews/{review_id}/like")
def unlike(review_id: str, user: User) -> dict:
    with db.connect() as conn:
        _visible_review(conn, review_id, user)
        conn.execute("DELETE FROM review_like WHERE review_id = %s AND user_id = %s", (review_id, user["id"]))
        conn.commit()
    return {"liked": False}


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


@router.get("/reviews/{review_id}/comments")
def comments(review_id: str, viewer: MaybeUser) -> list[dict]:
    with db.connect() as conn:
        _visible_review(conn, review_id, viewer)
        rows = conn.execute("SELECT c.*, u.username, u.display_name FROM review_comment c JOIN app_user u ON u.id = c.user_id "
                            "WHERE c.review_id = %s ORDER BY c.created_at", (review_id,)).fetchall()
    return [{"id": str(r["id"]), "user": {"username": r["username"], "display_name": r["display_name"]}, "body": r["body"],
             "created_at": r["created_at"].isoformat(), "mine": bool(viewer and viewer["username"] == r["username"])} for r in rows]


@router.post("/reviews/{review_id}/comments", status_code=201)
def add_comment(review_id: str, body: CommentIn, user: User) -> dict:
    if not body.body.strip():
        raise HTTPException(422, "a comment needs some words")
    with db.connect() as conn:
        _visible_review(conn, review_id, user)
        row = conn.execute("INSERT INTO review_comment (review_id, user_id, body) VALUES (%s, %s, %s) RETURNING id",
                           (review_id, user["id"], body.body.strip())).fetchone()
        conn.commit()
    return {"id": str(row["id"])}


@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: str, user: User) -> dict:
    with db.connect() as conn:
        try:
            n = conn.execute("DELETE FROM review_comment WHERE id = %s AND user_id = %s", (comment_id, user["id"])).rowcount
        except Exception:
            conn.rollback()
            n = 0
        conn.commit()
    if not n:
        raise HTTPException(404, "comment not found")
    return {"ok": True}


# ---------------------------------------------------------------- activity, feed, community
class ActivityIn(BaseModel):
    kind: Literal["finished", "started"]
    work_slug: str = Field(max_length=200)


def _activity(conn, viewer: dict | None, where: str, params: dict, limit: int, before: int | None = None) -> list[dict]:
    rows = conn.execute(
        f"SELECT a.id, a.kind, a.ref, a.created_at, u.username, u.display_name, w.slug, w.title, w.medium, "
        f"r.score AS review_score, left(r.body, 280) AS review_excerpt, r.spoiler AS review_spoiler "
        f"FROM activity a JOIN app_user u ON u.id = a.user_id LEFT JOIN work w ON w.id = a.work_id "
        f"LEFT JOIN review r ON a.kind = 'review' AND r.id::text = a.ref "
        f"WHERE {where} AND {VISIBLE} AND (%(before)s::bigint IS NULL OR a.id < %(before)s) "
        f"ORDER BY a.id DESC LIMIT %(limit)s",
        {**params, "viewer": viewer["id"] if viewer else None, "limit": limit, "before": before}).fetchall()
    return [{"id": r["id"], "kind": r["kind"], "ref": r["ref"], "at": r["created_at"].isoformat(),
             "user": {"username": r["username"], "display_name": r["display_name"]},
             "work": {"slug": r["slug"], "title": r["title"], "medium": r["medium"]} if r["slug"] else None,
             "review": ({"score": r["review_score"], "excerpt": r["review_excerpt"], "spoiler": r["review_spoiler"]}
                        if r["kind"] == "review" else None)}
            for r in rows]


@router.post("/activity", status_code=201)
def post_activity(body: ActivityIn, user: User) -> dict:
    if not user["share_activity"]:
        return {"shared": False}
    with db.connect() as conn:
        wid = _work_id(conn, body.work_slug)
        # One "started" / "finished" per work per day is plenty for a feed.
        dup = conn.execute("SELECT 1 FROM activity WHERE user_id = %s AND kind = %s AND work_id = %s AND created_at > now() - interval '1 day'",
                           (user["id"], body.kind, wid)).fetchone()
        if not dup:
            conn.execute("INSERT INTO activity (user_id, kind, work_id) VALUES (%s, %s, %s)", (user["id"], body.kind, wid))
            conn.commit()
    return {"shared": True}


@router.get("/feed")
def feed(user: User, before: int | None = Query(default=None, ge=1)) -> list[dict]:
    """You and the people you follow, newest first."""
    with db.connect() as conn:
        return _activity(conn, user, "(a.user_id = %(me)s OR a.user_id IN (SELECT followee_id FROM follow WHERE follower_id = %(me)s))",
                         {"me": user["id"]}, 50, before)


@router.get("/community")
def community(viewer: MaybeUser, days: int = Query(14, ge=1, le=90)) -> dict:
    """What everyone is reviewing, finishing and joining: the shared front page."""
    with db.connect() as conn:
        since = {"since": datetime.now(UTC) - timedelta(days=days)}
        trending = conn.execute(
            "SELECT w.slug, w.title, w.medium, count(*) AS n, round(avg(r.score)::numeric, 1) AS mean "
            "FROM activity a JOIN work w ON w.id = a.work_id LEFT JOIN review r ON a.kind = 'review' AND r.id::text = a.ref "
            "WHERE a.created_at >= %(since)s GROUP BY w.slug, w.title, w.medium ORDER BY n DESC, w.title LIMIT 12", since).fetchall()
        challenges = conn.execute("SELECT challenge_slug, year, count(*) AS members FROM challenge_member GROUP BY 1, 2").fetchall()
        members = conn.execute("SELECT count(*) AS n FROM app_user").fetchone()["n"]
        return {"trending": [{"slug": t["slug"], "title": t["title"], "medium": t["medium"], "activity": t["n"],
                              "mean_score": float(t["mean"]) if t["mean"] is not None else None} for t in trending],
                "reviews": _reviews(conn, viewer, "true", {}, 20),
                "activity": _activity(conn, viewer, "true", {}, 30),
                "challenges": [{"slug": c["challenge_slug"], "year": c["year"], "members": c["members"]} for c in challenges],
                "members": members}


# ---------------------------------------------------------------- public lists
class ListIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=200)
    slugs: list[str] = Field(max_length=500)


def _list_out(r: dict, owner: dict) -> dict:
    return {"id": str(r["id"]), "name": r["name"], "note": r["note"], "slugs": r["slugs"], "user": public_user(owner),
            "updated_at": r["updated_at"].isoformat()}


@router.post("/lists", status_code=201)
def publish_list(body: ListIn, user: User) -> dict:
    with db.connect() as conn:
        known = {r["slug"] for r in conn.execute("SELECT slug FROM work WHERE slug = ANY(%s)", (body.slugs,)).fetchall()}
        slugs = [s for s in dict.fromkeys(body.slugs) if s in known]
        row = conn.execute("INSERT INTO public_list (user_id, name, note, slugs) VALUES (%s, %s, %s, %s) RETURNING *",
                           (user["id"], body.name.strip(), body.note.strip(), slugs)).fetchone()
        conn.execute("INSERT INTO activity (user_id, kind, ref) VALUES (%s, 'list', %s)", (user["id"], str(row["id"])))
        conn.commit()
    return _list_out(row, user)


@router.get("/lists/{list_id}")
def get_list(list_id: str, viewer: MaybeUser) -> dict:
    with db.connect() as conn:
        try:
            row = conn.execute("SELECT * FROM public_list WHERE id = %s", (list_id,)).fetchone()
        except Exception:
            conn.rollback()
            row = None
        owner = row and conn.execute("SELECT * FROM app_user WHERE id = %s", (row["user_id"],)).fetchone()
        if row is None or not _can_see(conn, viewer, owner):
            raise HTTPException(404, "list not found")
    return _list_out(row, owner)


@router.delete("/lists/{list_id}")
def delete_list(list_id: str, user: User) -> dict:
    with db.connect() as conn:
        try:
            n = conn.execute("DELETE FROM public_list WHERE id = %s AND user_id = %s", (list_id, user["id"])).rowcount
        except Exception:
            conn.rollback()
            n = 0
        if n:
            conn.execute("DELETE FROM activity WHERE kind = 'list' AND ref = %s", (list_id,))
        conn.commit()
    if not n:
        raise HTTPException(404, "list not found")
    return {"ok": True}


# ---------------------------------------------------------------- calendar challenges
def challenge_slugs() -> set[str]:
    return {p["slug"] for p in json.loads(CALENDAR.read_text())["programmes"]}


class ProgressIn(BaseModel):
    done: list[int] = Field(max_length=366)


def _check_challenge(slug: str, year: int) -> None:
    if slug not in challenge_slugs():
        raise HTTPException(404, "challenge not found")
    if not 2020 <= year <= 2100:
        raise HTTPException(422, "year out of range")


@router.get("/challenges/{slug}/{year}")
def challenge(slug: str, year: int, viewer: MaybeUser) -> dict:
    _check_challenge(slug, year)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT u.username, u.display_name, cardinality(m.done) AS done, m.done AS days FROM challenge_member m "
            f"JOIN app_user u ON u.id = m.user_id WHERE m.challenge_slug = %(slug)s AND m.year = %(year)s AND {VISIBLE} "
            "ORDER BY done DESC, m.joined_at LIMIT 50", {"slug": slug, "year": year, "viewer": viewer["id"] if viewer else None}).fetchall()
        total = conn.execute("SELECT count(*) AS n FROM challenge_member WHERE challenge_slug = %s AND year = %s", (slug, year)).fetchone()["n"]
    me = next((r for r in rows if viewer and r["username"] == viewer["username"]), None)
    return {"slug": slug, "year": year, "members": total,
            "leaders": [{"user": {"username": r["username"], "display_name": r["display_name"]}, "done": r["done"]} for r in rows[:20]],
            "joined": me is not None, "my_days": list(me["days"]) if me else []}


@router.post("/challenges/{slug}/{year}/join")
def join_challenge(slug: str, year: int, user: User) -> dict:
    _check_challenge(slug, year)
    with db.connect() as conn:
        new = conn.execute("INSERT INTO challenge_member (challenge_slug, year, user_id) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                           (slug, year, user["id"])).rowcount
        if new and user["share_activity"]:
            conn.execute("INSERT INTO activity (user_id, kind, ref) VALUES (%s, 'joined_challenge', %s)", (user["id"], f"{slug}/{year}"))
        conn.commit()
    return {"joined": True}


@router.delete("/challenges/{slug}/{year}/join")
def leave_challenge(slug: str, year: int, user: User) -> dict:
    _check_challenge(slug, year)
    with db.connect() as conn:
        conn.execute("DELETE FROM challenge_member WHERE challenge_slug = %s AND year = %s AND user_id = %s", (slug, year, user["id"]))
        conn.execute("DELETE FROM activity WHERE user_id = %s AND kind = 'joined_challenge' AND ref = %s", (user["id"], f"{slug}/{year}"))
        conn.commit()
    return {"joined": False}


@router.put("/challenges/{slug}/{year}/progress")
def challenge_progress(slug: str, year: int, body: ProgressIn, user: User) -> dict:
    _check_challenge(slug, year)
    days = sorted({d for d in body.done if 1 <= d <= 366})
    with db.connect() as conn:
        n = conn.execute("UPDATE challenge_member SET done = %s WHERE challenge_slug = %s AND year = %s AND user_id = %s",
                         (days, slug, year, user["id"])).rowcount
        conn.commit()
    if not n:
        raise HTTPException(404, "join the challenge first")
    return {"done": days}


# ---------------------------------------------------------------- reports
class ReportIn(BaseModel):
    target_kind: Literal["review", "comment", "user", "list"]
    target_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)


@router.post("/reports", status_code=201)
def report(body: ReportIn, user: User) -> dict:
    with db.connect() as conn:
        conn.execute("INSERT INTO report (reporter_id, target_kind, target_id, reason) VALUES (%s, %s, %s, %s)",
                     (user["id"], body.target_kind, body.target_id, body.reason.strip()))
        conn.commit()
    return {"ok": True}
