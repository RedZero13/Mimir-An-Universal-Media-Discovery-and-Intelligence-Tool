"""Open Library: covers, median page counts and reader ratings for books."""

from __future__ import annotations

from mde.catalogue.model import normalise_title
from mde.ingest.http import Client

SEARCH = "https://openlibrary.org/search.json"
LICENCE = "Open Library data: open; cover images remain the publishers' and are shown for identification"
FIELDS = "key,title,author_name,first_publish_year,cover_i,number_of_pages_median,edition_count,ratings_average,ratings_count"


def best_doc(docs: list[dict], title: str, author: str | None, year: int | None) -> tuple[dict | None, str]:
    """Exact (normalised) title, author surname present, and year within two (translations publish later)."""
    want = normalise_title(title)
    surname = (author or "").split()[-1].lower() if author else None
    for d in docs:
        if normalise_title(d.get("title", "")) != want:
            continue
        if surname and not any(surname in a.lower() for a in d.get("author_name", [])):
            continue
        fy = d.get("first_publish_year")
        if year and fy and abs(fy - year) > 2:
            continue
        return d, "exact title, author and year"
    return None, "no doc with matching title, author and year"


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
        doc, why = best_doc(docs, work["title"], author, work.get("year"))
        if doc is None:
            return {"match": None, "reason": why, "candidates": [{"key": d.get("key"), "title": d.get("title"),
                                                                    "authors": d.get("author_name"), "year": d.get("first_publish_year")}
                                                                   for d in docs[:5]]}
        return {"match": {"key": doc["key"], "reason": why}, **from_doc(doc)}
