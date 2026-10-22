"""A small enrichment sample in the exact shape mde/ingest writes, for tests only.

Values are illustrative, not fetched, and this module is never written to mde/data/enrichment/.
"""

FIXTURE = {
    "wikidata": {
        "source": "wikidata", "licence": "CC0 1.0", "generated_at": "2026-10-01T00:00:00Z", "unmatched": ["primer-2004"],
        "works": {
            "arrival-2016": {
                "match": {"qid": "Q-test-1", "confidence": 1.0, "reason": "fixture"},
                "facts": {"release_year": 2016, "runtime_minutes": 118},
                "ids": {"imdb": "tt-test", "letterboxd": "arrival-test"},
                "scores": [{"publisher": "Rotten Tomatoes", "metric": "score", "value": 90, "scale_max": 100, "votes": 400, "as_of": "2024-01-01"},
                           {"publisher": "Metacritic", "metric": "score", "value": 80, "scale_max": 100, "votes": None, "as_of": None}],
                "box_office": [{"scope": "worldwide", "amount": 200000000, "currency": "USD"}],
                "series": [],
                "images": [{"kind": "still", "url": "https://example.org/still.jpg", "licence": "CC BY-SA 4.0", "attribution": "A photographer"}],
                "links": [{"kind": "reactions:reddit", "label": "Reddit discussions", "url": "https://www.reddit.com/search/?q=a"},
                          {"kind": "reactions:letterboxd", "label": "Letterboxd", "url": "https://letterboxd.com/film/arrival-test/"}],
                "conflicts": [{"field": "runtime_minutes", "seed": 116, "source": 118}],
            },
            "blade-runner-2049-2017": {
                "match": {"qid": "Q-test-2", "confidence": 1.0, "reason": "fixture"}, "facts": {"release_year": 2017},
                "ids": {}, "scores": [], "box_office": [], "images": [], "links": [],
                "series": [{"qid": "Q-test-s", "name": "Blade Runner", "position": "2"}],
            },
            "primer-2004": {"match": None, "reason": "no confident match", "candidates": [],
                            "links": [{"kind": "reactions:reddit", "label": "Reddit discussions", "url": "https://www.reddit.com/search/?q=p"}]},
        },
    },
    "openlibrary": {
        "source": "openlibrary", "licence": "test", "generated_at": "2026-10-01T00:00:00Z", "unmatched": [],
        "works": {"dune-1965": {"match": {"key": "/works/OL-test-W", "reason": "fixture"}, "key": "/works/OL-test-W",
                                "facts": {"page_count": 600},
                                "images": [{"kind": "cover", "url": "https://example.org/dune.jpg", "licence": "test cover", "attribution": "Open Library"}],
                                "scores": [{"publisher": "Open Library readers", "metric": "average rating", "value": 4.2, "scale_max": 5, "votes": 900, "as_of": None}]}},
    },
    "musicbrainz": {
        "source": "musicbrainz", "licence": "test", "generated_at": "2026-10-01T00:00:00Z", "unmatched": [],
        "works": {"ok-computer-1997": {"match": {"mbid": "mb-test", "release": "rel-test", "reason": "fixture"},
                                       "facts": {"runtime_minutes": 54},
                                       "tracks": [{"disc": 1, "position": 1, "title": "Track One", "seconds": 300, "recording": "r1",
                                                   "remixes": [{"title": "Track One (Remix)", "artist": "Someone", "recording": "r9", "direction": "remixed_as"}]},
                                                  {"disc": 1, "position": 2, "title": "Track Two", "seconds": 240, "recording": "r2", "remixes": []}],
                                       "images": [{"kind": "cover", "url": "https://example.org/okc.jpg", "licence": "test cover", "attribution": "CAA"}]}},
    },
}
