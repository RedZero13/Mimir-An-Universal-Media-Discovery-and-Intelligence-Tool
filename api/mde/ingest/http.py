"""A polite HTTP client for open-data APIs: identifies itself, rate-limits per host, retries, and caches."""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "MimirCatalogue/0.1 (+https://mimir.terratalesmedia.world; hello@terratalesmedia.world)"
CACHE_DIR = Path(os.environ.get("MDE_CACHE_DIR", Path(__file__).parent.parent / "data" / "cache"))

# Minimum seconds between requests to one host. MusicBrainz asks for at most one request per second.
MIN_INTERVAL = {"musicbrainz.org": 1.1, "coverartarchive.org": 0.5, "openlibrary.org": 0.6, "www.wikidata.org": 0.2,
                "query.wikidata.org": 1.0, "api.themoviedb.org": 0.1}


class FetchError(Exception):
    pass


class NotCached(FetchError):
    """Raised in offline mode when a response isn't in the cache."""


class Client:
    def __init__(self, offline: bool = False, cache_dir: Path = CACHE_DIR, max_age_days: float = 30):
        self.offline = offline
        self.cache_dir = cache_dir
        self.max_age = max_age_days * 86400
        self._last: dict[str, float] = {}
        self.down: dict[str, str] = {}   # hosts that couldn't be reached this run: fail fast instead of retrying each URL

    def _cache_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.cache_dir / h[:2] / f"{h}.json"

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        path = self._cache_path(url)
        if path.exists() and (self.offline or time.time() - path.stat().st_mtime < self.max_age):
            return json.loads(path.read_text())["body"]
        if self.offline:
            raise NotCached(url)
        body = self._fetch(url, headers or {})
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"url": url, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "body": body}))
        return body

    def fetched_at(self, url: str, params: dict | None = None) -> str | None:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        path = self._cache_path(url)
        return json.loads(path.read_text())["fetched_at"] if path.exists() else None

    def _fetch(self, url: str, headers: dict) -> dict:
        host = urllib.parse.urlparse(url).netloc
        if host in self.down:
            raise FetchError(f"{host} unreachable: {self.down[host]}")
        wait = MIN_INTERVAL.get(host, 0.3) - (time.monotonic() - self._last.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **headers})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    self._last[host] = time.monotonic()
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                self._last[host] = time.monotonic()
                if e.code == 404:
                    return {}
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(float(e.headers.get("Retry-After") or 2 ** (attempt + 1)))
                    continue
                raise FetchError(f"{url}: HTTP {e.code}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                reason = getattr(e, "reason", e)
                if attempt < 1:
                    time.sleep(2)
                    continue
                self.down[host] = str(reason)
                raise FetchError(f"{url}: {reason}") from e
        raise FetchError(url)
