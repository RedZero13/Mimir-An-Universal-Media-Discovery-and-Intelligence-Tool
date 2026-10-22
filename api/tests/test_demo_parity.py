"""The browser demo's JavaScript engine (demo/engine.cjs) must produce exactly what the Python engine produces."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from enrichment_fixture import FIXTURE

from mde.catalogue.browse import load_shelves
from mde.catalogue.memory import MemoryCatalogue

ROOT = Path(__file__).parent.parent.parent
BENCHMARK = json.loads((ROOT / "api/benchmark/queries.json").read_text())

EXTRA_QUERIES = [
    "",
    "a film",
    "something to watch tonight",
    "a quick read",
    "bite-sized games",
    "a really eerie, deeply atmospheric horror game",
    "a slightly funny drama",
    "something like \"Arrival\"",
    "something like \"Not A Real Title\"",
    "films like spirited away but not anime",
    "if i loved dune, what should i read",
    "in the vein of Disco Elysium, any medium",
    "something like Journey in another medium",
    "foreign language films about class",
    "korean thrillers",
    "films from the 70s",
    "books before 1970",
    "games after 2015",
    "recent melancholic albums",
    "a popular crowd-pleaser",
    "hidden gems about memory",
    "a film under 90 minutes, ideally",
    "a film no longer than an hour and a half",
    "a game under 10 hours",
    "a movie up to 2 hrs",
    "no sex, no gore, no atrocities, nothing bleak",
    "not too much violence and not too slow",
    "avoid jump scares or body horror please",
    "something hopeful but not too sentimental",
    "anything but a book about grief",
    "not a game, something about artificial intelligence and robots",
    "a story about language, translation and grief",
    "something cosy and wholesome for a rainy day",
    "an album to listen to while working, ambient and minimal",
    "dystopian surveillance across any medium",
    "a mind-bending puzzle box with time loops",
    "world-class worldbuilding",
    "music for focus — calm, minimal",
    "I loved Blade Runner",
    "what's like stalker",
    "Something LIKE OUTER WILDS!!!",
    "a constructor game",
]


BROWSE_CASES = [
    {},
    {"media": ["film"]},
    {"media": ["game", "book"], "sort": "title"},
    {"tags": ["theme:grief-loss"]},
    {"tags": ["theme:consciousness-ai", "genre:science-fiction"], "sort": "popular"},
    {"decade": 1970},
    {"language": "ja"},
    {"country": "GB", "sort": "oldest"},
    {"max_minutes": 100, "sort": "shortest"},
    {"media": ["film"], "avoid": ["advisory:graphic-violence", "advisory:strong-language"], "sort": "newest"},
    {"avoid": ["advisory:substance-use"]},
    {"q": "tarkovsky"},
    {"q": "  the  "},
    {"q": "zzz-nothing"},
    {"media": ["album"], "tags": ["mood:melancholic"], "sort": "shortest"},
    {"exclude": ["genre:science-fiction", "mood:bleak"], "sort": "title"},
    {"media": ["film"], "year_min": 1980, "year_max": 1999, "sort": "oldest"},
    {"year_min": 2015, "exclude": ["theme:grief-loss"]},
]


SEED = json.loads((ROOT / "api/mde/seed/catalogue.json").read_text())


def _catalogue(enrichment):
    return MemoryCatalogue(SEED, enrichment=enrichment)


def _views(cat):
    tag_keys = [t["key"] for d in cat.tags() for t in d["terms"]] + ["theme:not-a-tag", "advisory:strong-language"]
    people = [p["slug"] for p in cat.people()] + ["nobody"]
    shelves = [s["slug"] for s in load_shelves()["shelves"]] + ["no-such-shelf"]
    groups = [g["slug"] for g in cat.groups()] + ["no-such-group"]
    return ([["browse", b] for b in BROWSE_CASES] + [["tag", k] for k in tag_keys] + [["tags", None]]
            + [["person", s] for s in people] + [["people", None]]
            + [["shelves", None]] + [["shelf", s] for s in shelves] + [["groups", None]] + [["group", g] for g in groups]
            + [["mood_rings", None], ["remix_rack", None]])


def _run(cat, kind, arg):
    from mde.catalogue.browse import BrowseFilters
    return {"browse": lambda a: cat.browse(BrowseFilters(**a)), "tag": cat.tag, "tags": lambda _: cat.tags(),
            "person": cat.person, "people": lambda _: cat.people(), "shelves": lambda _: cat.shelves(),
            "shelf": cat.shelf, "groups": lambda _: cat.groups(), "group": cat.group,
            "mood_rings": lambda _: cat.mood_rings(), "remix_rack": lambda _: cat.remix_rack()}[kind](arg)


# Each side runs twice: with no enrichment, and with the labelled test fixture (images, scores, series, tracks …).
@pytest.fixture(scope="module", params=["seed-only", "enriched"])
def js_output(request):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    enrichment = {} if request.param == "seed-only" else FIXTURE
    cat = _catalogue(enrichment)
    queries = [q["query"] for q in BENCHMARK["queries"]] + EXTRA_QUERIES
    slugs = [w.slug for w in cat.works]
    views = _views(cat)
    payload = {"queries": queries, "slugs": slugs, "views": views, "enrichment": enrichment}
    proc = subprocess.run([node, str(ROOT / "demo/parity.cjs")], input=json.dumps(payload),
                          capture_output=True, text=True, check=True)
    return cat, queries, slugs, views, json.loads(proc.stdout)


def _normalise(obj):
    # JSON round-trip so tuples/ints/floats compare the same way on both sides.
    return json.loads(json.dumps(obj))


def test_discovery_output_is_identical(js_output):
    cat, queries, _, _, out = js_output
    mismatches = []
    for query, js in zip(queries, out["discover"], strict=True):
        py = _normalise(cat.discover(query).to_dict())
        if py != js:
            mismatches.append(query)
    assert not mismatches, f"JS and Python differ for: {mismatches}"


def test_work_pages_are_identical(js_output):
    cat, _, slugs, _, out = js_output
    for slug, js in zip(slugs, out["works"], strict=True):
        assert _normalise(cat.work(slug)) == js, slug


def test_catalogue_views_are_identical(js_output):
    cat, _, _, views, out = js_output
    mismatches = [v for v, js in zip(views, out["views"], strict=True) if _normalise(_run(cat, *v)) != js]
    assert not mismatches, mismatches
