import json

import pytest
from fastapi.testclient import TestClient

from mde.catalogue.load import ValidationFailed, import_catalogue, load_seed
from mde.discovery.engine import discover
from mde.migrate import migrate


def counts(conn):
    return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]
            for t in ("work", "credit", "classification", "relationship", "person", "organisation")}


def test_migrations_are_idempotent(conn):
    assert migrate(conn) == []


def test_seed_is_idempotent(conn):
    before = counts(conn)
    stats = load_seed(conn)
    assert stats.works_inserted == 0 and stats.works_updated == 0
    assert counts(conn) == before


def test_invalid_import_writes_nothing(conn):
    before = counts(conn)
    with pytest.raises(ValidationFailed):
        import_catalogue(conn, {"works": [{"slug": "bad", "medium": "film", "title": "Bad",
                                           "terms": {"mood:not-a-term": 1}}]})
    assert counts(conn) == before


def test_assessed_advisories_are_explicit_zeros_and_unassessed_are_absent(conn):
    rows = conn.execute(
        "SELECT w.slug, count(*) FILTER (WHERE t.dimension = 'advisory') AS n FROM work w "
        "LEFT JOIN classification c ON c.work_id = w.id LEFT JOIN taxonomy_term t ON t.id = c.term_id "
        "WHERE w.slug IN ('arrival-2016', 'ok-computer-1997') GROUP BY w.slug").fetchall()
    n = {r["slug"]: r["n"] for r in rows}
    assert n["arrival-2016"] == 5 and n["ok-computer-1997"] == 0


def test_discover_logs_event_and_explains(conn):
    resp = discover(conn, "a book like Arrival").to_dict()
    assert resp["event_id"]
    assert resp["reference"]["slug"] == "arrival-2016"
    first = resp["results"][0]
    assert first["slug"] == "story-of-your-life-1998"
    assert first["reasons"][0]["kind"] == "relationship" and first["reasons"][0]["basis"] == "catalogue"


def test_benchmark_passes(conn):
    from benchmark.run import run_benchmark
    report = run_benchmark(conn)
    failures = {q["id"]: q["failures"] for q in report["queries"] if q["failures"]}
    assert not failures, json.dumps(failures, indent=2)


@pytest.fixture
def client(database_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", database_url)
    from mde.app import app
    return TestClient(app)


def test_api_discover_work_and_feedback(client):
    r = client.get("/api/discover", params={"q": "comforting films"})
    assert r.status_code == 200
    body = r.json()
    slug = body["results"][0]["slug"]
    work = client.get(f"/api/works/{slug}").json()
    assert work["classifications"] and work["sources"]
    assert all(c["origin"] == "ai_assisted" for c in work["classifications"])
    ok = client.post("/api/feedback", json={"event_id": body["event_id"], "work_slug": slug, "kind": "relevant"})
    assert ok.status_code == 201
    assert client.post("/api/feedback", json={"work_slug": slug, "kind": "nonsense"}).status_code == 422
    assert client.post("/api/feedback", json={"event_id": "not-a-uuid", "work_slug": slug,
                                              "kind": "relevant"}).status_code == 422
    assert client.get("/api/works/does-not-exist").status_code == 404
    assert client.get("/api/discover", params={"q": "x"}).status_code == 422
