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
    assert "Disallow: /privacy/" in robots and "Disallow: /terms/" in robots, "legal pages are held back from crawlers"
    assert robots.count("Disallow") == robots.count("User-agent") * 5, "every group blocks the five legal pages and nothing else"
    assert "Sitemap: https://mimir.terratalesmedia.world/sitemap.xml" in robots


def test_llms_files_describe_the_site(site):
    short, full = (site / "llms.txt").read_text(), (site / "llms-full.txt").read_text()
    assert short.startswith("# Mimir\n\n> ") and "not assessed" in short
    assert full.startswith(short) and len(full) > len(short)
    for link in re.findall(r"\]\((https://mimir\.terratalesmedia\.world/[^)#]*)\)", short):
        assert (site / link.removeprefix("https://mimir.terratalesmedia.world/").lstrip("/")).exists(), link


def test_built_pages_pass_the_page_audit(site):
    _, findings = run_audit(load_context(site), {"P001", "P002", "P003", "P004", "P005", "P006"}, set())
    assert not findings, "\n".join(f"{f.rule} {f.key}: {f.message}" for f in findings[:10])


def test_legal_pages_are_built_and_linked_but_held_back_from_search(site):
    for slug in ("privacy", "cookies", "terms", "data-requests", "security"):
        html = (site / slug / "index.html").read_text()
        assert "<h1>" in html and "Version 2026-10" in html, slug
        assert f"https://mimir.terratalesmedia.world/{slug}/" not in (site / "sitemap-pages.xml").read_text(), "on hold: not in the sitemap"
        assert '<meta name="robots" content="noindex, nofollow">' in html, slug
    privacy = (site / "privacy" / "index.html").read_text()
    assert "Data Protection Board of India" in privacy and "Third Floor" in privacy
    assert "To be added" in privacy, "unfilled placeholders must stay visible, not be dropped"
    assert 'href="/privacy/"' in (site / "index.html").read_text(), "the app footer links to the notice"


def test_franchise_help_tool_and_day_pages_are_built_and_listed(site):
    sitemap = "".join((site / f).read_text() for f in sorted(p.name for p in site.glob("sitemap-*.xml")))
    got = (site / "franchises" / "game-of-thrones" / "index.html").read_text()
    assert "House of the Dragon" in got and "A Game of Thrones" in got and "ItemList" in got and "<h1>Game of Thrones in order</h1>" in got
    assert "FAQPage" in (site / "help" / "index.html").read_text()
    assert len(list((site / "help").glob("*/index.html"))) >= 27  # 21 guides and 6 categories
    assert len(list((site / "tools").glob("*/index.html"))) == 9
    assert len(list((site / "days").glob("*/index.html"))) >= 45
    for rel in ("franchises/game-of-thrones", "tools/decide", "days/laughter-day", "help/what-is-mimir", "tags/genre-comedy", "about"):
        assert f"https://mimir.terratalesmedia.world/{rel}/" in sitemap, rel
    home = (site / "index.html").read_text()
    assert "SearchAction" in home and 'href="/franchises/"' in home and 'href="/help/"' in home
    assert "parents' guide for each work" not in home


def test_titles_only_promise_a_parents_guide_for_assessed_works(site):
    import re

    promised = 0
    for f in list((site / "works").glob("*/index.html"))[:400]:
        t = f.read_text()
        if re.search(r"<title>[^<]*parents&#39; guide|<title>[^<]*parents' guide", t):
            promised += 1
            assert "noindex" not in t, f"{f}: a noindex page should not advertise a parents' guide"
    assert promised > 0


def test_work_pages_carry_a_parents_guide_section_and_similar_works(site):
    rich = (site / "works" / "no-country-for-old-men-2007" / "index.html").read_text()
    assert (
        "Parents' guide" in rich and "Violence &amp; gore" in rich and "More films like No Country for Old Men" in rich and "In other media" in rich
    )
    thin = (site / "works" / "cars-2006" / "index.html").read_text()
    assert "Not assessed yet" in thin and "should not be treated as suitable for any age" in thin
