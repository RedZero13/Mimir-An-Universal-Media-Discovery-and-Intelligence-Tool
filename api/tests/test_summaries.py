"""seed/summaries.json: short summaries for widely known imported works."""

import json

from mde.catalogue.seedfiles import SEED_DIR, read_seed


def _summaries() -> dict[str, str]:
    return json.loads((SEED_DIR / "summaries.json").read_text())["summaries"]


def test_every_summary_names_a_real_work_without_its_own_summary():
    base = {}
    for path in SEED_DIR.glob("*.json"):
        if path.name == "summaries.json":
            continue
        for w in json.loads(path.read_text()).get("works", []):
            base[w["slug"]] = w
    for slug in _summaries():
        assert slug in base, f"unknown work {slug}"
        assert not base[slug].get("summary"), f"{slug} already has a summary"


def test_summaries_are_short_plain_sentences():
    for slug, text in _summaries().items():
        assert 40 <= len(text) <= 330, slug
        assert text.rstrip().endswith((".", ".'")), slug
        assert "  " not in text, slug


def test_loaded_works_carry_the_summary():
    loaded = {w["slug"]: w for w in read_seed()["works"]}
    for slug, text in _summaries().items():
        assert loaded[slug]["summary"] == text
