"""Accounts and community, end to end through the HTTP API against a real database."""

import uuid

import pytest
from fastapi.testclient import TestClient

from mde import community


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    community._attempts.clear()
    from mde.app import app
    return TestClient(app)


def signup(client, name=None, **extra):
    name = name or f"u{uuid.uuid4().hex[:8]}"
    r = client.post("/api/auth/signup", json={"username": name, "display_name": name.title(), "email": f"{name}@example.com",
                                              "password": "correct horse battery", **extra})
    assert r.status_code == 201, r.text
    return name, {"Authorization": f"Bearer {r.json()['token']}"}


def test_password_hashing_round_trip():
    h = community.hash_password("s3cret-pass")
    assert h.startswith("scrypt$") and "s3cret" not in h
    assert community.verify_password("s3cret-pass", h)
    assert not community.verify_password("wrong", h)
    assert not community.verify_password("x", "not-a-hash")


def test_signup_login_logout_and_validation(client):
    name, auth = signup(client)
    assert client.get("/api/me", headers=auth).json()["username"] == name
    assert client.post("/api/auth/signup", json={"username": name, "display_name": "x", "email": "other@example.com",
                                                 "password": "long enough pw"}).status_code == 409
    assert client.post("/api/auth/signup", json={"username": "x" + name, "display_name": "x", "email": f"{name}@EXAMPLE.com",
                                                 "password": "long enough pw"}).status_code == 409   # emails are case-insensitive
    for bad in ("ab", "Has Space", "admin"):
        assert client.post("/api/auth/signup", json={"username": bad, "display_name": "x", "email": f"{uuid.uuid4().hex}@e.com",
                                                     "password": "long enough pw"}).status_code == 422
    assert client.post("/api/auth/login", json={"login": name, "password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"login": f"{name}@example.com", "password": "correct horse battery"})
    assert r.status_code == 200
    second = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.post("/api/auth/logout", headers=second).status_code == 200
    assert client.get("/api/me", headers=second).status_code == 401
    assert client.get("/api/me", headers=auth).status_code == 200   # other sessions survive
    assert client.get("/api/me").status_code == 401


def test_login_attempts_are_rate_limited(client):
    codes = [client.post("/api/auth/login", json={"login": "nobody", "password": "x"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429


def test_library_sync_round_trip(client):
    _, auth = signup(client)
    assert client.get("/api/me/state", headers=auth).json()["data"] is None
    state = {"library": {"arrival-2016": {"status": "completed", "score": 9}}, "journal": [{"id": "j1", "text": "Wow"}]}
    assert client.put("/api/me/state", json=state, headers=auth).status_code == 200
    assert client.get("/api/me/state", headers=auth).json()["data"] == state
    assert client.put("/api/me/state", content=b"[1,2]", headers={**auth, "content-type": "application/json"}).status_code == 422


def test_reviews_likes_comments_and_permissions(client):
    alice, a = signup(client)
    bob, b = signup(client)
    assert client.put("/api/works/arrival-2016/review", json={"body": ""}, headers=a).status_code == 422
    assert client.put("/api/works/no-such-work/review", json={"score": 8}, headers=a).status_code == 404
    r = client.put("/api/works/arrival-2016/review", json={"score": 9, "body": "Language as time travel.", "spoiler": False}, headers=a)
    assert r.json()["created"] is True
    rid = r.json()["id"]
    assert client.put("/api/works/arrival-2016/review", json={"score": 10, "body": "Even better twice."}, headers=a).json()["created"] is False
    page = client.get("/api/works/arrival-2016/reviews").json()
    assert page["count"] == 1 and page["mean_score"] == 10.0 and page["reviews"][0]["user"]["username"] == alice
    assert client.post(f"/api/reviews/{rid}/like", headers=b).status_code == 200
    assert client.post(f"/api/reviews/{rid}/like", headers=b).status_code == 200   # idempotent
    assert client.post(f"/api/reviews/{rid}/comments", json={"body": "Agreed!"}, headers=b).status_code == 201
    seen = client.get("/api/works/arrival-2016/reviews", headers=b).json()["reviews"][0]
    assert seen["likes"] == 1 and seen["liked"] and seen["comments"] == 1 and not seen["mine"]
    comment = client.get(f"/api/reviews/{rid}/comments", headers=b).json()[0]
    assert comment["mine"] and comment["body"] == "Agreed!"
    assert client.delete(f"/api/comments/{comment['id']}", headers=a).status_code == 404   # only the author deletes
    assert client.delete(f"/api/comments/{comment['id']}", headers=b).status_code == 200
    assert client.post("/api/reviews/not-a-uuid/like", headers=b).status_code == 404
    assert client.delete("/api/works/arrival-2016/review", headers=a).status_code == 200
    assert client.get("/api/works/arrival-2016/reviews").json()["count"] == 0


def test_follow_feed_and_private_accounts(client):
    alice, a = signup(client)
    bob, b = signup(client)
    carol, c = signup(client)
    assert client.post(f"/api/users/{bob}/follow", headers=b).status_code == 422
    client.post(f"/api/users/{alice}/follow", headers=b)
    client.put("/api/works/dune-1965/review", json={"score": 8, "body": "Spice and politics."}, headers=a)
    client.post("/api/activity", json={"kind": "finished", "work_slug": "arrival-2016"}, headers=a)
    client.post("/api/activity", json={"kind": "finished", "work_slug": "arrival-2016"}, headers=a)   # deduplicated
    client.post("/api/activity", json={"kind": "started", "work_slug": "dune-1965"}, headers=c)
    feed = client.get("/api/feed", headers=b).json()
    kinds = [(x["user"]["username"], x["kind"]) for x in feed]
    assert (alice, "review") in kinds and kinds.count((alice, "finished")) == 1 and (carol, "started") not in kinds
    assert next(x for x in feed if x["kind"] == "review")["review"]["excerpt"] == "Spice and politics."
    prof = client.get(f"/api/users/{alice}", headers=b).json()
    assert prof["followers"] == 1 and prof["following"] and prof["reviews"] == 1 and prof["visible"]
    assert client.get(f"/api/users/{bob}").json()["following_count"] == 1
    # Private: hidden from strangers, visible to followers
    client.patch("/api/me", json={"is_private": True, "bio": "Reader."}, headers=a)
    stranger = client.get(f"/api/users/{alice}", headers=c).json()
    assert not stranger["visible"] and stranger["reviews_recent"] == [] and stranger["activity"] == []
    assert all(r["user"]["username"] != alice for r in client.get("/api/works/dune-1965/reviews", headers=c).json()["reviews"])
    assert client.get(f"/api/users/{alice}", headers=b).json()["visible"]
    assert any(x["user"]["username"] == alice for x in client.get("/api/feed", headers=b).json())
    community_page = client.get("/api/community", headers=c).json()
    assert all(r["user"]["username"] != alice for r in community_page["reviews"])
    # Sharing off: activity isn't posted
    client.patch("/api/me", json={"share_activity": False}, headers=c)
    assert client.post("/api/activity", json={"kind": "finished", "work_slug": "dune-1965"}, headers=c).json() == {"shared": False}


def test_community_trending_lists_challenges_reports_and_delete(client):
    alice, a = signup(client)
    bob, b = signup(client)
    for who in (a, b):
        client.post("/api/activity", json={"kind": "finished", "work_slug": "halloween-1978"}, headers=who)
    page = client.get("/api/community").json()
    assert {"slug": "halloween-1978", "activity": 2} in [{"slug": t["slug"], "activity": t["activity"]} for t in page["trending"]]
    assert page["members"] >= 2
    slugs = ["halloween-1978", "nope", "coraline-2009", "coraline-2009"]
    lst = client.post("/api/lists", json={"name": "Spooky starters", "slugs": slugs}, headers=a).json()
    assert lst["slugs"] == ["halloween-1978", "coraline-2009"]
    assert client.get(f"/api/lists/{lst['id']}").json()["user"]["username"] == alice
    assert client.delete(f"/api/lists/{lst['id']}", headers=b).status_code == 404
    # Challenges
    assert client.post("/api/challenges/not-a-programme/2026/join", headers=a).status_code == 404
    assert client.put("/api/challenges/spooktober/2026/progress", json={"done": [1]}, headers=a).status_code == 404
    assert client.post("/api/challenges/spooktober/2026/join", headers=a).status_code == 200
    assert client.put("/api/challenges/spooktober/2026/progress", json={"done": [3, 1, 1, 400]}, headers=a).json()["done"] == [1, 3]
    client.post("/api/challenges/spooktober/2026/join", headers=b)
    ch = client.get("/api/challenges/spooktober/2026", headers=a).json()
    assert ch["members"] == 2 and ch["joined"] and ch["my_days"] == [1, 3] and ch["leaders"][0]["user"]["username"] == alice
    assert any(x["kind"] == "joined_challenge" for x in client.get("/api/feed", headers=a).json())
    assert client.post("/api/reports", json={"target_kind": "list", "target_id": lst["id"], "reason": "spam"}, headers=b).status_code == 201
    # Deleting an account removes what it wrote
    client.put("/api/works/coraline-2009/review", json={"score": 7}, headers=a)
    assert client.post("/api/me/delete", json={"password": "wrong"}, headers=a).status_code == 401
    assert client.post("/api/me/delete", json={"password": "correct horse battery"}, headers=a).status_code == 200
    assert client.get(f"/api/users/{alice}").status_code == 404
    assert client.get("/api/works/coraline-2009/reviews").json()["count"] == 0
    assert client.get("/api/me", headers=a).status_code == 401


def test_calendar_slugs_match_the_programmes_file():
    assert {"spooktober", "twelve-days-of-christmas", "pride-month", "diwali"} <= community.challenge_slugs()
