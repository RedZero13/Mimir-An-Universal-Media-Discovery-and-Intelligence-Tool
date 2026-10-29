"""A polite, resumable parallel fetcher: results append to a JSON-lines file, so an interrupted run continues where it stopped."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USER_AGENT = "MimirCatalogue/0.1 (+https://mimir.terratalesmedia.world; hello@terratalesmedia.world)"


def get_json(url: str, timeout: float = 30, retries: int = 4, headers: dict | None = None):
    """GET a URL and parse JSON. Retries throttling and server errors with growing waits; returns None for 404."""
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = e
            wait = float(e.headers.get("Retry-After") or 0) if e.code in (429, 503) else 0
            time.sleep(min(60, wait or 2 ** (attempt + 1)))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            last = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def done_keys(path: Path) -> set[str]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text().splitlines():
        try:
            out.add(json.loads(line)["key"])
        except (ValueError, KeyError):
            pass
    return out


def run(
    items: Iterable[tuple[str, object]],
    fn: Callable[[object], object],
    path: Path,
    workers: int = 6,
    min_gap: float = 0.0,
    log: Callable[[str], None] = print,
) -> None:
    """For each (key, arg) not already in `path`, call fn(arg) and append {"key", "data"}. `min_gap` spaces request starts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    have = done_keys(path)
    todo = [(k, a) for k, a in items if k not in have]
    log(f"{path.name}: {len(have)} done, {len(todo)} to fetch")
    lock, gate, count, errors = threading.Lock(), threading.Lock(), [0], [0]
    last = [0.0]

    def one(item):
        k, a = item
        if min_gap:
            with gate:
                wait = last[0] + min_gap - time.time()
                if wait > 0:
                    time.sleep(wait)
                last[0] = time.time()
        try:
            data = fn(a)
        except Exception as e:  # noqa: BLE001 - one failure must not stop the run; the key stays "to do" for the next run
            errors[0] += 1
            if errors[0] <= 5:
                log(f"  {k}: {str(e)[:120]}")
            return
        with lock:
            with path.open("a") as f:
                f.write(json.dumps({"key": k, "data": data}, ensure_ascii=False) + "\n")
            count[0] += 1
            if count[0] % 250 == 0:
                log(f"  {path.name}: {count[0]} / {len(todo)}")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    log(f"{path.name}: finished, {count[0]} fetched, {errors[0]} failed")


def load(path: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
                out[r["key"]] = r["data"]
            except (ValueError, KeyError):
                pass
    return out
