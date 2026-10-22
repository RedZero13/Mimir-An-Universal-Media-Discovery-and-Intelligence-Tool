"""The in-memory catalogue (used by the browser demo) must behave like the database-backed engine."""

import ast
import re
from pathlib import Path

from benchmark.run import run_benchmark_offline
from mde.catalogue.memory import MemoryCatalogue
from mde.catalogue.model import RELATIONSHIP_TYPES
from mde.catalogue.seedfiles import SEED_DIR

# Behaviour tests run on the fixed pilot file so they don't move as the beta catalogue grows.
PILOT = SEED_DIR / "catalogue.json"

PURE_MODULES = ["mde/catalogue/model.py", "mde/catalogue/memory.py", "mde/discovery/intent.py",
                "mde/discovery/rank.py", "mde/discovery/explain.py", "mde/discovery/pipeline.py",
                "mde/taxonomy/__init__.py", "mde/catalogue/seedfiles.py", "mde/catalogue/providers.py", "mde/catalogue/browse.py",
                "mde/catalogue/enrich.py"]


def test_benchmark_passes_offline():
    report = run_benchmark_offline()
    failures = {q["id"]: q["failures"] for q in report["queries"] if q["failures"]}
    assert not failures, failures


def test_pure_modules_never_import_the_database_driver_at_runtime():
    root = Path(__file__).parent.parent
    for rel in PURE_MODULES:
        tree = ast.parse((root / rel).read_text())
        for node in tree.body:  # top-level imports only; TYPE_CHECKING blocks are ast.If and skipped
            if isinstance(node, ast.Import | ast.ImportFrom):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                assert not any(n.startswith("psycopg") or n in ("mde.catalogue.repository", "mde.catalogue.load",
                                                                "mde.discovery.engine") for n in names), rel


def test_relationship_types_match_migration():
    sql = "".join(p.read_text() for p in sorted((Path(__file__).parent.parent / "mde/migrations").glob("*.sql")))
    rows = re.findall(r"\('(\w+)', '([^']+)', '([^']+)', (true|false), (true|false)\)", sql)
    assert {r[0]: (r[1], r[2], r[4] == "true") for r in rows} == RELATIONSHIP_TYPES


def test_work_page_data():
    work = MemoryCatalogue.from_seed(PILOT).work("arrival-2016")
    assert work["relationships"][0]["slug"] == "story-of-your-life-1998"
    assert work["relationships"][0]["factual"]
    assert {d["dimension"] for d in work["tags"]} >= {"genre", "theme", "mood"}
    assert MemoryCatalogue.from_seed(PILOT).work("nope") is None


def test_parents_guide_distinguishes_none_from_not_assessed():
    guide = MemoryCatalogue.from_seed(PILOT).work("arrival-2016")["parents_guide"]
    groups = {g["slug"]: g for g in guide["groups"]}
    assert guide["ratings"] == [{"system": "MPA", "rating": "PG-13", "reason": "Brief strong language"}]
    assert groups["violence"]["severity"] == "Mild"
    assert groups["language"]["severity"] == "Mild"
    assert groups["substances"]["severity"] == "Not assessed"     # never claimed to be "none"
    assert groups["sex"]["severity"] == "None"
    unassessed = MemoryCatalogue.from_seed(PILOT).work("ok-computer-1997")["parents_guide"]
    assert not unassessed["assessed"] and all(g["severity"] == "Not assessed" for g in unassessed["groups"])


def test_spoiler_notes_are_kept_separate():
    guide = MemoryCatalogue.from_seed(PILOT).work("solaris-1972")["parents_guide"]
    item = next(i for g in guide["groups"] for i in g["items"] if i["key"] == "advisory:suicide-self-harm")
    assert item["note"] and item["spoiler_note"] and item["spoiler_note"] not in item["note"]


def test_browse_filters_and_facets():
    from mde.catalogue.browse import BrowseFilters
    cat = MemoryCatalogue.from_seed(PILOT)
    everything = cat.browse(BrowseFilters())
    assert everything["total"] == len(cat.works)
    assert {f["value"]: f["count"] for f in everything["facets"]["medium"]} == {"film": 22, "book": 15, "game": 11, "album": 8}
    safe = cat.browse(BrowseFilters(avoid=["advisory:graphic-violence"]))
    # Unassessed works are left out rather than presumed safe.
    assert "ok-computer-1997" not in [r["slug"] for r in safe["results"]]
    assert "come-and-see-1985" not in [r["slug"] for r in safe["results"]]
    short = cat.browse(BrowseFilters(media=["film"], max_minutes=100, sort="shortest"))
    assert [r["slug"] for r in short["results"]][:2] == ["primer-2004", "my-neighbor-totoro-1988"]
    tagged = cat.browse(BrowseFilters(tags=["theme:consciousness-ai", "genre:horror"]))
    assert [r["slug"] for r in tagged["results"]] == ["soma-2015"]
    assert [r["slug"] for r in cat.browse(BrowseFilters(q="tarkovsky"))["results"]] == ["solaris-1972", "stalker-1979"]  # same tier, then title


def test_tag_and_person_pages():
    cat = MemoryCatalogue.from_seed(PILOT)
    tag = cat.tag("theme:grief-loss")
    strengths = [w["strength"] for w in tag["works"]]
    assert strengths == sorted(strengths, reverse=True) and min(strengths) >= 0.4
    person = cat.person("ursula-k-le-guin")
    assert [w["slug"] for w in person["works"]] == ["the-dispossessed-1974", "the-left-hand-of-darkness-1969"]
    assert cat.person("nobody") is None and cat.tag("theme:nope") is None
