"""The review spreadsheet: an untouched export changes nothing; edited cells come back as corrections that read_seed applies."""

import json

import pytest

pytest.importorskip("openpyxl")
from openpyxl import load_workbook  # noqa: E402

from mde.catalogue import review_sheet  # noqa: E402
from mde.catalogue.seedfiles import read_seed  # noqa: E402


@pytest.fixture(scope="module")
def sheet(tmp_path_factory):
    return review_sheet.export(tmp_path_factory.mktemp("review") / "review.xlsx")


def _edit(src, dst, slug, cells):
    wb = load_workbook(src)
    ws = wb["Works"]
    col = {c.value: i + 1 for i, c in enumerate(ws[1])}
    row = next(r for r in range(2, ws.max_row + 1) if ws.cell(r, col["Key (do not edit)"]).value == slug)
    for header, value in cells.items():
        ws.cell(row, col[header]).value = value
    wb.save(dst)


def test_export_has_every_work_and_an_unedited_sheet_changes_nothing(sheet, tmp_path, monkeypatch):
    monkeypatch.setattr(review_sheet, "CORRECTIONS", tmp_path / "corrections.json")
    ws = load_workbook(sheet, read_only=True)["Works"]
    assert ws.max_row - 1 == len(read_seed()["works"])
    report = review_sheet.apply(sheet, dry_run=True)
    assert report == {"changed_works": 0, "reviewed": 0, "errors": []}


def test_edits_round_trip_and_bad_tags_are_refused(sheet, tmp_path, monkeypatch):
    out = tmp_path / "corrections.json"
    monkeypatch.setattr(review_sheet, "CORRECTIONS", out)
    edited = tmp_path / "edited.xlsx"
    _edit(sheet, edited, "arrival-2016", {
        "Title": "Arrival (reviewed)",
        "Genres": "science-fiction (1), drama (0.5)",
        "Parents' guide (topic strength | note)": "graphic-violence 0.2 | Little is shown.\nstrong-language 0.3",
        "Review status": "OK",
    })
    _edit(edited, edited, "titanic-1997", {"Moods": "not-a-real-mood (1)"})
    report = review_sheet.apply(edited)
    assert report["changed_works"] == 1 and report["reviewed"] == 1
    assert any("titanic-1997" in e and "unknown tags" in e for e in report["errors"])
    data = json.loads(out.read_text())
    w = {x["slug"]: x for x in read_seed(corrections=data)["works"]}["arrival-2016"]
    assert w["title"] == "Arrival (reviewed)"
    assert {k: v for k, v in w["terms"].items() if k.startswith("genre:")} == {"genre:science-fiction": 1, "genre:drama": 0.5}
    assert w["advisories"] == {"graphic-violence": [0.2, "Little is shown."], "strong-language": 0.3}
    assert data["review"]["arrival-2016"]["status"] == "OK"


def test_cell_formats_read_back():
    assert review_sheet.parse_credits("director: A; actor: B") == [["director", "A"], ["actor", "B"]]
    assert review_sheet.parse_terms("drama (0.7), comedy", "genre:") == {"genre:drama": 0.7, "genre:comedy": 1}
    assert review_sheet.parse_ratings("MPA | PG-13 | Language") == [["MPA", "PG-13", "Language"]]
    terms = {"genre:drama": 0.7, "mood:tense": 0.4, "style:atmospheric": 0.9}
    assert review_sheet.parse_terms(review_sheet.fmt_terms(terms, "genre:"), "genre:") == {"genre:drama": 0.7}
    assert review_sheet.parse_terms(review_sheet.fmt_terms(terms, None), None) == {"style:atmospheric": 0.9}
