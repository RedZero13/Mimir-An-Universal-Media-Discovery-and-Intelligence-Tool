"""Franchise pages gather every medium: shows with books, games and soundtracks, from the curated overlays."""

import json
from pathlib import Path

import pytest

from mde.catalogue.memory import MemoryCatalogue
from mde.catalogue.seedfiles import read_seed

SEED = Path(__file__).parent.parent / "mde" / "seed"
ENRICH = json.loads((Path(__file__).parent.parent / "mde" / "data" / "enrichment" / "musicbrainz.json").read_text())["works"]


@pytest.fixture(scope="module")
def cat():
    return MemoryCatalogue.from_seed()


@pytest.mark.parametrize(
    "slug,media",
    [
        ("game-of-thrones", {"series", "book", "album"}),
        ("middle-earth", {"film", "series", "book", "game", "album"}),
        ("dune", {"film", "book", "game", "album"}),
        ("wizarding-world", {"film", "book", "game", "album"}),
        ("the-last-of-us", {"series", "game", "album"}),
    ],
)
def test_one_page_per_franchise_across_media(cat, slug, media):
    g = cat.group(slug)
    assert g and media <= {w["medium"] for w in g["works"]}, slug


def test_game_of_thrones_and_house_of_the_dragon_share_a_page(cat):
    slugs = {w["slug"] for w in cat.group("game-of-thrones")["works"]}
    assert {"game-of-thrones-2011", "house-of-the-dragon-2022", "a-game-of-thrones-1996"} <= slugs


def test_rings_of_power_sits_with_the_lord_of_the_rings(cat):
    slugs = {w["slug"] for w in cat.group("middle-earth")["works"]}
    assert {"the-lord-of-the-rings-the-rings-of-power-2022", "the-fellowship-of-the-ring-2001", "the-hobbit-1937"} <= slugs


def test_every_soundtrack_is_tied_to_musicbrainz_and_a_franchise_with_other_works():
    works = json.loads((SEED / "soundtracks.json").read_text())["works"]
    all_works = read_seed()["works"]
    for w in works:
        rec = ENRICH[w["slug"]]
        assert rec["match"]["mbid"] and rec["match"]["release"] and rec["images"][0]["url"].endswith("/front-500"), w["slug"]
        franchise = w["attributes"]["franchises"][0]
        others = [x for x in all_works if x["slug"] != w["slug"] and franchise in ((x.get("attributes") or {}).get("franchises") or [])]
        assert others, f"{w['slug']}: no other work carries {franchise}"


def test_the_overlay_never_overrides_an_existing_franchise_list():
    over = json.loads((SEED / "franchises-merged.json").read_text())["attributes"]
    base = {w["slug"]: w for w in json.loads((SEED / "catalogue.json").read_text())["works"]}
    assert over and all(len(v["franchises"]) == 1 for v in over.values())
    for slug in over:
        assert not ((base.get(slug) or {}).get("attributes") or {}).get("franchises"), slug
