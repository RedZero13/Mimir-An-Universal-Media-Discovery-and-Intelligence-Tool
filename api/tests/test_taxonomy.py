import json

import pytest

from mde import taxonomy
from mde.catalogue.load import SEED_PATH, possible_duplicates, validate


def test_taxonomy_loads_and_every_term_is_defined():
    tax = taxonomy.load()
    assert tax.version
    for term in tax.terms.values():
        assert term.definition, term.key
        assert term.dimension in tax.dimensions


def test_ambiguous_synonym_is_rejected():
    data = {"version": "x", "dimensions": [{"slug": "mood", "label": "M", "description": "d", "kind": "graded"}],
            "terms": [{"dimension": "mood", "slug": "a", "label": "A", "definition": "d", "synonyms": ["dark"]},
                      {"dimension": "mood", "slug": "b", "label": "B", "definition": "d", "synonyms": ["dark"]}]}
    with pytest.raises(ValueError, match="dark"):
        taxonomy.parse(data)


def test_seed_catalogue_is_valid_and_has_no_duplicates():
    data = json.loads(SEED_PATH.read_text())
    assert validate(data, taxonomy.load()) == []
    assert possible_duplicates(data["works"]) == []


def test_validation_reports_unknown_terms_and_bad_strengths():
    data = {"works": [{"slug": "x", "medium": "film", "title": "X", "terms": {"mood:nonexistent": 0.5, "mood:eerie": 2}}],
            "relationships": [["x", "sequel_of", "missing", "", 0.5]]}
    errors = validate(data, taxonomy.load())
    assert any("unknown term" in e for e in errors)
    assert any("must be in [0, 1]" in e for e in errors)
    assert any("unknown work" in e for e in errors)


def test_duplicate_detection_ignores_leading_article():
    works = [{"slug": "a", "medium": "book", "title": "The Dispossessed", "year": 1974},
             {"slug": "b", "medium": "book", "title": "Dispossessed", "year": 1974}]
    assert possible_duplicates(works) == ["b looks like a duplicate of a"]
