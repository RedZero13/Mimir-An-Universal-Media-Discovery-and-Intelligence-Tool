"""Open Library: covers, median page counts and reader ratings for books."""

from __future__ import annotations

import re
import unicodedata

from mde.catalogue.model import normalise_title
from mde.ingest.http import Client

SEARCH = "https://openlibrary.org/search.json"
LICENCE = "Open Library data: open; cover images remain the publishers' and are shown for identification"
FIELDS = "key,title,author_name,first_publish_year,cover_i,number_of_pages_median,edition_count,ratings_average,ratings_count"


def _clean(title: str) -> str:
    """Drop edition and series notes Open Library appends in brackets, e.g. '(Helen and Kurt Wolff Books)'."""
    return normalise_title(re.sub(r"\s*\([^)]*\)\s*$", "", title))


def _fold(name: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c)).lower()


def _author_ok(surname: str | None, names: list[str]) -> bool:
    """Surname present, ignoring accents. A name with no Latin letters (村上春樹, 刘慈欣) can't be compared, so it is
    accepted: the search itself was already filtered by author."""
    if not surname:
        return True
    return any(surname in _fold(a) or not re.search(r"[A-Za-z]", _fold(a)) for a in names)


def best_doc(docs: list[dict], title: str | list[str], author: str | None, year: int | None) -> tuple[dict | None, str]:
    """Exact (normalised) title and author surname present. Year within two is preferred; translations often carry the
    year of the English edition, so an exact title-and-author match is still accepted with the difference stated."""
    wants = {_clean(t) for t in ([title] if isinstance(title, str) else title)}
    surname = _fold(author.split()[-1]) if author else None
    hits = [d for d in docs if _clean(d.get("title", "")) in wants and _author_ok(surname, d.get("author_name", []))]
    for d in hits:
        fy = d.get("first_publish_year")
        if not (year and fy and abs(fy - year) > 2):
            return d, "exact title, author and year"
    if hits:
        d = max(hits, key=lambda x: x.get("edition_count") or 0)
        return d, f"exact title and author; first published {d.get('first_publish_year')} here, {year} in the catalogue"
    return None, "no doc with matching title and author"


def from_doc(doc: dict) -> dict:
    out = {"key": doc["key"], "url": f"https://openlibrary.org{doc['key']}", "facts": {}, "scores": [], "images": []}
    if doc.get("number_of_pages_median"):
        out["facts"]["page_count"] = int(doc["number_of_pages_median"])
    if doc.get("cover_i"):
        out["images"].append({"kind": "cover", "url": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg",
                              "licence": "Cover via Open Library, shown for identification; rights remain with the publisher",
                              "attribution": "Open Library"})
    if doc.get("ratings_count"):
        out["scores"].append({"publisher": "Open Library readers", "metric": "average rating",
                              "value": round(float(doc["ratings_average"]), 2), "scale_max": 5.0,
                              "votes": int(doc["ratings_count"]), "as_of": None})
    return out


class OpenLibrary:
    def __init__(self, client: Client):
        self.client = client

    def enrich(self, work: dict) -> dict:
        author = next((c[1] for c in work.get("credits", []) if c[0] == "author"), None)
        params = {"title": work["title"], "limit": 10, "fields": FIELDS}
        if author:
            params["author"] = author
        docs = self.client.get_json(SEARCH, params).get("docs", [])
        titles = [work["title"], *((work.get("attributes") or {}).get("aka") or [])]
        for alt in titles[1:]:
            docs += self.client.get_json(SEARCH, {**params, "title": alt}).get("docs", [])
        doc, why = best_doc(docs, titles, author, work.get("year"))
        if doc is None:
            return {"match": None, "reason": why, "candidates": [{"key": d.get("key"), "title": d.get("title"),
                                                                    "authors": d.get("author_name"), "year": d.get("first_publish_year")}
                                                                   for d in docs[:5]]}
        return {"match": {"key": doc["key"], "reason": why}, **from_doc(doc)}
