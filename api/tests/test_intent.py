import pytest

from mde import taxonomy
from mde.discovery.intent import RuleBasedIntentParser

TITLES = {"arrival": "arrival-2016", "outer wilds": "outer-wilds-2019", "blade runner": "blade-runner-1982",
          "journey": "journey-2012", "discovery": "discovery-2001"}


@pytest.fixture(scope="module")
def parser():
    return RuleBasedIntentParser(taxonomy.load(), lambda t: TITLES.get(t.strip().lower()))


def prefs(intent):
    return {p.term for p in intent.preferences}


def avoids(intent):
    return {a.term: a for a in intent.avoid}


def test_directive_example(parser):
    i = parser.parse("I want an intelligent science-fiction film with ambitious world-building, philosophical "
                     "questions, a strong atmosphere, and very little graphic violence. Ideally under two hours, "
                     "and not something obvious that everyone recommends.")
    assert i.media == ["film"]
    assert {"genre:science-fiction", "world:rich-worldbuilding", "complexity:intellectually-demanding",
            "style:atmospheric"} <= prefs(i)
    violence = avoids(i)["advisory:graphic-violence"]
    assert violence.hard and violence.threshold == 0.6     # "very little" tolerates mild violence
    assert i.length.max_minutes == 120 and not i.length.hard
    assert i.novelty == "obscure"


@pytest.mark.parametrize("query,hard", [
    ("a film under 2 hours", True),
    ("a film, ideally under 2 hours", False),
    ("a film under 90 minutes if possible", False),
    ("a film strictly under 90 minutes", True),
])
def test_length_softness(parser, query, hard):
    assert parser.parse(query).length.hard is hard


def test_vague_length_depends_on_medium(parser):
    length = parser.parse("something I can finish in one evening").length
    assert not length.hard
    assert length.for_medium("game") > length.for_medium("film")


def test_negation_scope_stops_at_the_next_phrase(parser):
    i = parser.parse("not too slow sci-fi with time loops")
    assert "pacing:slow-burn" in avoids(i)
    assert {"genre:science-fiction", "narrative:time-loop"} <= prefs(i)


def test_negation_carries_over_coordinated_items(parser):
    i = parser.parse("no gore or jump scares but funny")
    a = avoids(i)
    assert a["advisory:graphic-violence"].hard and a["advisory:jump-scares"].hard
    assert "mood:funny" in prefs(i)


def test_mood_avoidance_is_soft(parser):
    a = avoids(parser.parse("a fantasy book, nothing bleak"))["mood:bleak"]
    assert not a.hard


def test_reference_resolution_and_other_medium(parser):
    i = parser.parse("something like Blade Runner but in a different medium")
    assert i.reference_slug == "blade-runner-1982"
    assert i.reference_other_medium


def test_like_as_a_verb_is_not_a_reference(parser):
    i = parser.parse("I'd like a romantic film")
    assert i.reference_slug is None
    assert "mood:romantic" in prefs(i)


def test_title_words_without_a_cue_are_not_references(parser):
    assert parser.parse("an uplifting journey of self-discovery").reference_slug is None


def test_language_decade_and_media(parser):
    i = parser.parse("japanese films from the 80s")
    assert i.languages == ["ja"] and (i.year_min, i.year_max) == (1980, 1989) and i.media == ["film"]


def test_excluded_medium(parser):
    i = parser.parse("anything about grief, but not a film")
    assert "film" in i.excluded_media and "film" not in i.media


def test_plural_synonyms(parser):
    assert "narrative:time-loop" in prefs(parser.parse("games with time loops"))


def test_leftover_keywords_exclude_stopwords(parser):
    assert parser.parse("a film about architecture").keywords == ["architecture"]
