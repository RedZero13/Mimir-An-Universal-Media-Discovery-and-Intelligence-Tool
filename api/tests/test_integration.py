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


def test_only_assessed_advisory_categories_are_stored(conn):
    rows = conn.execute(
        "SELECT w.slug, count(*) FILTER (WHERE t.dimension = 'advisory') AS n, "
        "count(*) FILTER (WHERE t.dimension = 'advisory' AND c.strength = 0) AS zeros FROM work w "
        "LEFT JOIN classification c ON c.work_id = w.id LEFT JOIN taxonomy_term t ON t.id = c.term_id "
        "WHERE w.slug IN ('arrival-2016', 'ok-computer-1997', 'kind-of-blue-1959') GROUP BY w.slug").fetchall()
    n = {r["slug"]: (r["n"], r["zeros"]) for r in rows}
    assert n["arrival-2016"] == (6, 4)          # five original categories + strong language; four are "none"
    assert n["ok-computer-1997"] == (0, 0)      # not assessed at all
    assert n["kind-of-blue-1959"] == (8, 8)     # instrumental: every category assessed as none


def test_parents_guide_notes_and_ratings_are_stored(conn):
    row = conn.execute(
        "SELECT c.evidence, c.spoiler_evidence FROM classification c JOIN work w ON w.id = c.work_id "
        "JOIN taxonomy_term t ON t.id = c.term_id WHERE w.slug = 'solaris-1972' AND t.slug = 'suicide-self-harm'"
    ).fetchone()
    assert row["evidence"] and row["spoiler_evidence"]
    rating = conn.execute("SELECT r.system, r.rating FROM content_rating r JOIN work w ON w.id = r.work_id "
                          "WHERE w.slug = 'arrival-2016'").fetchone()
    assert (rating["system"], rating["rating"]) == ("MPA", "PG-13")


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
    assert work["tags"] and work["sources"] and work["provenance"]
    assert all(t["basis"] == "interpretation" for d in work["tags"] for t in d["terms"])
    ok = client.post("/api/feedback", json={"event_id": body["event_id"], "work_slug": slug, "kind": "relevant"})
    assert ok.status_code == 201
    assert client.post("/api/feedback", json={"work_slug": slug, "kind": "nonsense"}).status_code == 422
    assert client.post("/api/feedback", json={"event_id": "not-a-uuid", "work_slug": slug,
                                              "kind": "relevant"}).status_code == 422
    assert client.get("/api/works/does-not-exist").status_code == 404
    assert client.get("/api/discover", params={"q": "x"}).status_code == 422


def test_api_catalogue_views_match_the_in_memory_catalogue(client):
    """Same pure views over PostgreSQL and over the seed file must give the same pages."""
    from mde.catalogue.browse import BrowseFilters
    from mde.catalogue.memory import MemoryCatalogue
    mem = MemoryCatalogue.from_seed()

    r = client.get("/api/works", params={"medium": "film", "avoid": "advisory:graphic-violence", "sort": "newest"})
    assert r.status_code == 200
    assert r.json() == json.loads(json.dumps(mem.browse(BrowseFilters(media=["film"], avoid=["advisory:graphic-violence"],
                                                                         sort="newest"))))
    r = client.get("/api/works", params={"exclude": "genre:science-fiction", "year_min": 1980, "year_max": 2010})
    assert r.json() == json.loads(json.dumps(mem.browse(BrowseFilters(exclude=["genre:science-fiction"], year_min=1980,
                                                                         year_max=2010))))
    page = client.get("/api/works/annihilation-2018").json()
    expected = json.loads(json.dumps(mem.work("annihilation-2018")))
    assert {k: page[k] for k in expected} == expected
    assert client.get("/api/tags/theme/grief-loss").json() == json.loads(json.dumps(mem.tag("theme:grief-loss")))
    assert client.get("/api/people/denis-villeneuve").json() == json.loads(json.dumps(mem.person("denis-villeneuve")))
    assert client.get("/api/people").json() == json.loads(json.dumps(mem.people()))
    assert client.get("/api/tags").json() == json.loads(json.dumps(mem.tags()))

    for path, view in [("/api/shelves", mem.shelves()), ("/api/shelves/nepo-babies", mem.shelf("nepo-babies")),
                       ("/api/groups", mem.groups()), ("/api/music/moods", mem.mood_rings()),
                       ("/api/music/remixes", mem.remix_rack())]:
        assert client.get(path).json() == json.loads(json.dumps(view)), path
    group = mem.groups()[0]["slug"]
    assert client.get(f"/api/groups/{group}").json() == json.loads(json.dumps(mem.group(group)))
    assert client.get("/api/shelves/nope").status_code == 404
    assert client.get("/api/groups/nope").status_code == 404

    assert client.get("/api/tags/theme/nope").status_code == 404
    assert client.get("/api/people/nobody").status_code == 404
    assert client.get("/api/works", params={"tag": "theme:nope"}).status_code == 422
    assert client.get("/api/works", params={"avoid": "mood:bleak"}).status_code == 422


def test_enrichment_round_trips_through_postgres(conn):
    """Profiles read back from the database equal the in-memory merge of the same enrichment."""
    from dataclasses import asdict

    from enrichment_fixture import FIXTURE

    from mde.catalogue.load import SEED_PATH, import_catalogue
    from mde.catalogue.memory import MemoryCatalogue
    from mde.catalogue.repository import load_profiles

    data = json.loads(SEED_PATH.read_text())
    import_catalogue(conn, data, enrichment=FIXTURE)
    stats = import_catalogue(conn, data, enrichment=FIXTURE)
    assert stats.works_updated == 0                     # idempotent with enrichment too
    db = {p.slug: asdict(p) for p in load_profiles(conn)}
    mem = {p.slug: asdict(p) for p in MemoryCatalogue(data, enrichment=FIXTURE).works}
    for slug in mem:
        db[slug].pop("id"), mem[slug].pop("id")
        assert db[slug] == mem[slug], slug
    arrival = mem["arrival-2016"]
    assert arrival["runtime_minutes"] == 118 and arrival["fact_sources"] == {"runtime_minutes": {"source": "wikidata", "seed": 116}}
    assert mem["dune-1965"]["page_count"] == 600
    assert mem["ok-computer-1997"]["tracks"][0]["remixes"][0]["direction"] == "remixed_as"
    assert [g["slug"] for g in mem["blade-runner-2049-2017"]["groups"]] == ["blade-runner"]
    assert mem["primer-2004"]["links"][0]["kind"] == "reactions:reddit"   # links survive an unmatched record
    conn.rollback()
