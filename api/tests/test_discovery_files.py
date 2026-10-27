"""The built site tells crawlers what it holds: a sitemap index split by type, robots.txt, llms.txt, and pages the audit accepts."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from mde.audit.engine import load_context, run_audit

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    if not shutil.which("node"):
        pytest.skip("node is not installed")
    out = tmp_path_factory.mktemp("site")
    subprocess.run(
        ["node", str(ROOT / "demo" / "build.cjs"), "--site", str(out)], check=True, env={**os.environ, "MIMIR_NO_MINIFY": "1"}, timeout=600
    )
    return out


def test_sitemap_index_lists_files_that_exist_and_split_by_type(site):
    index = (site / "sitemap.xml").read_text()
    assert "<sitemapindex" in index
    files = re.findall(r"<loc>[^<]+/(sitemap-[^<]+\.xml)</loc>", index)
    assert "sitemap-pages.xml" in files and "sitemap-works-films.xml" in files
    seen: set[str] = set()
    for f in files:
        locs = re.findall(r"<loc>([^<]+)</loc>", (site / f).read_text())
        assert 0 < len(locs) <= 50000, f
        assert not seen & set(locs), f"{f} repeats a URL"
        seen |= set(locs)


def test_robots_allows_search_and_answer_crawlers_and_names_the_sitemap(site):
    robots = (site / "robots.txt").read_text()
    for bot in ("Googlebot", "Bingbot", "OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"):
        assert f"User-agent: {bot}\nAllow: /" in robots
    assert "Disallow" not in robots
    assert "Sitemap: https://mimir.terratalesmedia.world/sitemap.xml" in robots


def test_llms_files_describe_the_site(site):
    short, full = (site / "llms.txt").read_text(), (site / "llms-full.txt").read_text()
    assert short.startswith("# Mimir\n\n> ") and "not assessed" in short
    assert full.startswith(short) and len(full) > len(short)
    for link in re.findall(r"\]\((https://mimir\.terratalesmedia\.world/[^)#]*)\)", short):
        assert (site / link.removeprefix("https://mimir.terratalesmedia.world/").lstrip("/")).exists(), link


def test_built_pages_pass_the_page_audit(site):
    _, findings = run_audit(load_context(site), {"P001", "P002", "P003", "P004", "P005"}, set())
    assert not findings, "\n".join(f"{f.rule} {f.key}: {f.message}" for f in findings[:10])
