"""Connector parsing. Fixtures below are hand-written in each API's documented response shape to exercise the
parsers; they are not real records and never reach the catalogue."""

from mde.ingest import links, musicbrainz, openlibrary, wikidata


def snak(prop, value, kind="wikibase-entityid"):
    return {"snaktype": "value", "property": prop, "datavalue": {"value": value, "type": kind}}


def claim(prop, value, rank="normal", qualifiers=None):
    c = {"rank": rank, "mainsnak": snak(prop, value)}
    if qualifiers:
        c["qualifiers"] = {p: [snak(p, v) for v in vs] for p, vs in qualifiers.items()}
    return c


ENTITY = {  # shaped like wbgetentities output for a film item
    "labels": {"en": {"value": "Example Film"}},
    "aliases": {"en": [{"value": "Example"}]},
    "claims": {
        "P31": [claim("P31", {"id": "Q11424"})],
        "P577": [claim("P577", {"time": "+2016-09-01T00:00:00Z", "precision": 11}),
                 claim("P577", {"time": "+2016-11-11T00:00:00Z", "precision": 11})],
        "P2047": [claim("P2047", {"amount": "+116", "unit": "http://www.wikidata.org/entity/Q7727"})],
        "P2142": [claim("P2142", {"amount": "+203000000", "unit": "http://www.wikidata.org/entity/Q4917"},
                        qualifiers={"P3005": [{"id": "Q13780930"}]}),
                  claim("P2142", {"amount": "+100000000", "unit": "http://www.wikidata.org/entity/Q4917"},
                        qualifiers={"P3005": [{"id": "Q30"}]})],
        "P444": [claim("P444", "94%", qualifiers={"P447": [{"id": "Q105584"}], "P585": [{"time": "+2020-01-01T00:00:00Z"}]}),
                 claim("P444", "90%", qualifiers={"P447": [{"id": "Q105584"}], "P585": [{"time": "+2017-01-01T00:00:00Z"}]}),
                 claim("P444", "81/100", qualifiers={"P447": [{"id": "Q150248"}]})],
        "P179": [claim("P179", {"id": "Q999"}, qualifiers={"P1545": ["2"]})],
        "P345": [claim("P345", "tt0000001")],
        "P6127": [claim("P6127", "example-film")],
        "P155": [claim("P155", {"id": "Q111"}, rank="deprecated")],
    },
}


def test_wikidata_parsers():
    assert wikidata.year_of(ENTITY) == 2016
    assert wikidata.runtime_minutes(ENTITY) == 116
    assert wikidata.box_office(ENTITY)[0] == {"scope": "worldwide", "amount": 203000000.0, "currency": "USD"}
    scores = wikidata.review_scores(ENTITY, {"Q105584": "Rotten Tomatoes", "Q150248": "Metacritic"})
    assert scores == [
        {"publisher": "Metacritic", "metric": "score", "value": 81.0, "scale_max": 100.0, "votes": None, "as_of": None},
        {"publisher": "Rotten Tomatoes", "metric": "score", "value": 94.0, "scale_max": 100.0, "votes": None, "as_of": "2020-01-01"},
    ]  # most recent Rotten Tomatoes value wins
    assert wikidata.series(ENTITY) == [{"qid": "Q999", "position": "2"}]
    assert wikidata.external_ids(ENTITY) == {"imdb": "tt0000001", "letterboxd": "example-film"}
    assert wikidata.item_ids(ENTITY, "P155") == []  # deprecated statements are ignored


def test_wikidata_matching_is_conservative():
    assert wikidata.score_candidate(ENTITY, "Example Film", "film", 2016)[0] == 1.0
    assert wikidata.score_candidate(ENTITY, "Example", "film", 2017)[0] > 0.7      # alias, year off by one
    assert wikidata.score_candidate(ENTITY, "Example Film", "book", 2016)[0] == 0   # wrong type
    assert wikidata.score_candidate(ENTITY, "Example Film", "film", 1990)[0] == 0   # year disagrees


def test_parse_score():
    assert wikidata.parse_score("93%") == (93.0, 100.0)
    assert wikidata.parse_score("8.1/10") == (8.1, 10.0)
    assert wikidata.parse_score("A-") is None


def test_openlibrary_match_and_fields():
    docs = [{"key": "/works/OL1W", "title": "Dune Messiah", "author_name": ["Frank Herbert"], "first_publish_year": 1969},
            {"key": "/works/OL2W", "title": "Dune", "author_name": ["Frank Herbert"], "first_publish_year": 1965,
             "cover_i": 123, "number_of_pages_median": 600, "ratings_average": 4.25, "ratings_count": 900}]
    doc, _ = openlibrary.best_doc(docs, "Dune", "Frank Herbert", 1965)
    assert doc["key"] == "/works/OL2W"
    out = openlibrary.from_doc(doc)
    assert out["facts"] == {"page_count": 600}
    assert out["images"][0]["url"] == "https://covers.openlibrary.org/b/id/123-L.jpg"
    assert out["scores"][0]["votes"] == 900
    assert openlibrary.best_doc(docs, "Dune", "Someone Else", 1965)[0] is None


def test_musicbrainz_tracks_and_remixes():
    groups = [{"id": "single", "title": "Discovery", "primary-type": "Single", "artist-credit": [{"name": "Daft Punk"}]},
              {"id": "album", "title": "Discovery", "primary-type": "Album", "first-release-date": "2001-03-12",
               "artist-credit": [{"name": "Daft Punk"}]}]
    assert musicbrainz.best_release_group(groups, "Discovery", "Daft Punk", 2001)["id"] == "album"
    releases = [{"id": "late", "date": "2005", "media": [{"tracks": [{"position": 1, "title": "A", "length": 1000}]}]},
                {"id": "early", "date": "2001-03-12", "media": [{"tracks": [
                    {"position": 1, "title": "One", "length": 320000, "recording": {"id": "r1"}},
                    {"position": 2, "title": "Two", "recording": {"id": "r2", "length": 210500}}]}]}]
    rel = musicbrainz.pick_release(releases)
    assert rel["id"] == "early"
    assert musicbrainz.tracklist(rel) == [
        {"disc": 1, "position": 1, "title": "One", "seconds": 320, "recording": "r1"},
        {"disc": 1, "position": 2, "title": "Two", "seconds": 210, "recording": "r2"}]
    rec = {"relations": [{"type": "remix", "target-type": "recording", "direction": "backward",
                          "recording": {"id": "r9", "title": "One (Club Mix)", "artist-credit": [{"name": "DJ"}]}},
                         {"type": "producer", "target-type": "artist"}]}
    assert musicbrainz.remixes(rec) == [{"title": "One (Club Mix)", "artist": "DJ", "recording": "r9", "direction": "remixed_as"}]


def test_links_use_exact_ids_when_known():
    work = {"title": "Example Film", "year": 2016, "medium": "film", "credits": [["director", "A Person"]]}
    by_kind = {link["kind"]: link["url"] for link in links.links_for(work, {"letterboxd": "example-film", "rotten_tomatoes": "m/example"})}
    assert by_kind["reactions:letterboxd"] == "https://letterboxd.com/film/example-film/"
    assert by_kind["reactions:rotten-tomatoes"] == "https://www.rottentomatoes.com/m/example"
    assert "reddit.com/search" in by_kind["reactions:reddit"]
    album = {"title": "Kind of Blue", "medium": "album", "credits": [["artist", "Miles Davis"]]}
    assert any(link["kind"] == "listen:spotify" for link in links.links_for(album, {}))
