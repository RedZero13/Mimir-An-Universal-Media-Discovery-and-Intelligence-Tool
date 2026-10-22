"""The in-memory catalogue (used by the browser demo) must behave like the database-backed engine."""

import ast
import re
from pathlib import Path

from benchmark.run import run_benchmark_offline
from mde.catalogue.memory import MemoryCatalogue
from mde.catalogue.model import RELATIONSHIP_TYPES

PURE_MODULES = ["mde/catalogue/model.py", "mde/catalogue/memory.py", "mde/discovery/intent.py",
                "mde/discovery/rank.py", "mde/discovery/explain.py", "mde/discovery/pipeline.py",
                "mde/taxonomy/__init__.py"]


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
    sql = (Path(__file__).parent.parent / "mde/migrations/0001_foundation.sql").read_text()
    rows = re.findall(r"\('(\w+)', '([^']+)', '([^']+)', (true|false), (true|false)\)", sql)
    assert {r[0]: (r[1], r[2], r[4] == "true") for r in rows} == RELATIONSHIP_TYPES


def test_work_page_data():
    work = MemoryCatalogue.from_seed().work("arrival-2016")
    assert work["relationships"][0]["slug"] == "story-of-your-life-1998"
    assert work["relationships"][0]["factual"]
    assert {c["dimension"] for c in work["classifications"]} >= {"genre", "theme", "mood", "advisory"}
    assert MemoryCatalogue.from_seed().work("nope") is None
