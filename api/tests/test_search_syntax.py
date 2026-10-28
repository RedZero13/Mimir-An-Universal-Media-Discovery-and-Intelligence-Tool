"""The search box's syntax, matching and suggestions (demo/search.cjs), and that the built app carries it with its Help guide."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_search_module_passes_its_checks():
    r = subprocess.run(["node", str(ROOT / "demo" / "search.test.cjs")], capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "all checks passed" in r.stdout


def test_built_app_bundles_search_and_help_guide_is_a_static_page(tmp_path):
    site = tmp_path / "site"
    r = subprocess.run(["node", str(ROOT / "demo" / "build.cjs"), "--site", str(site)], capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr
    app_js = "".join(p.read_text(errors="replace") for p in site.rglob("*.js")) + (site / "index.html").read_text(errors="replace")
    assert "MimirSearch" in app_js, "the app bundles the search module"
    guide = (site / "help" / "search-syntax" / "index.html").read_text()
    assert "year:2015..2020" in guide and "regular expression" in guide
