"""The observance calendar (catalogue/observances.json) is page-only data: check it stays well-formed."""

import json
from datetime import date
from pathlib import Path

from mde import taxonomy

DAYS = json.loads((Path(__file__).parent.parent / "mde/catalogue/observances.json").read_text())["days"]
PROGRAMMES = {p["slug"] for p in json.loads((Path(__file__).parent.parent / "mde/catalogue/calendar.json").read_text())["programmes"]}


def test_slugs_are_unique_and_every_day_has_a_date():
    assert len({d["slug"] for d in DAYS}) == len(DAYS)
    for d in DAYS:
        assert ("date" in d) != ("nth" in d), d["slug"]
        if "date" in d:
            date(2024, int(d["date"][:2]), int(d["date"][3:]))   # a real calendar day (2024 is a leap year)
        else:
            month, weekday, n = d["nth"]
            assert 1 <= month <= 12 and 0 <= weekday <= 6 and 1 <= n <= 4, d["slug"]


def test_rules_use_real_taxonomy_terms_and_known_programmes():
    keys = set(taxonomy.load().terms)
    for d in DAYS:
        for k in d["rule"].get("any_tags", []):
            assert k in keys, f"{d['slug']}: {k}"
        assert d["kind"] in {"un", "unesco", "observed", "informal"}, d["slug"]
        assert d.get("programme") is None or d["programme"] in PROGRAMMES, d["slug"]
        assert d["about"] and d["why"], d["slug"]
