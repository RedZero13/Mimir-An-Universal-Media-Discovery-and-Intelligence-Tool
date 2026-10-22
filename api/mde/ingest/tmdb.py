"""TMDB posters, used only when TMDB_API_KEY (v3 key) or TMDB_READ_TOKEN (v4 token) is configured.

TMDB requires attribution ("This product uses the TMDB API but is not endorsed or certified by TMDB") and a
commercial agreement for commercial use; see docs/SOURCES.md.
"""

from __future__ import annotations

import os

from mde.ingest.http import Client

API = "https://api.themoviedb.org/3"
IMAGES = "https://image.tmdb.org/t/p/w500"
ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."


def configured() -> bool:
    return bool(os.environ.get("TMDB_API_KEY") or os.environ.get("TMDB_READ_TOKEN"))


class TMDB:
    def __init__(self, client: Client):
        self.client = client
        self.key = os.environ.get("TMDB_API_KEY")
        token = os.environ.get("TMDB_READ_TOKEN")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}

    def _get(self, path: str, **params) -> dict:
        if self.key:
            params["api_key"] = self.key
        return self.client.get_json(f"{API}{path}", params, headers=self.headers)

    def enrich(self, work: dict, ids: dict) -> dict:
        movie = None
        if ids.get("tmdb_movie"):
            movie = self._get(f"/movie/{ids['tmdb_movie']}")
        elif ids.get("imdb"):
            movie = (self._get(f"/find/{ids['imdb']}", external_source="imdb_id").get("movie_results") or [None])[0]
        if not movie or not movie.get("poster_path"):
            return {"match": None, "reason": "no TMDB movie with a poster for this work's IDs"}
        return {"match": {"tmdb": movie.get("id")},
                "images": [{"kind": "poster", "url": f"{IMAGES}{movie['poster_path']}", "licence": "Poster via TMDB",
                            "attribution": ATTRIBUTION}]}
