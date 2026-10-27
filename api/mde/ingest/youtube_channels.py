"""Read public facts about YouTube channels from their own pages and RSS feeds: no API key, nothing guessed.

    python -m mde.ingest.youtube_channels @kurzgesagt @veritasium --out channels.json

For each handle it records the channel id, name, joined date, country, the counts YouTube shows, the creator's own
description, and the newest videos in the channel's feed (id, title, published date, views). A handle that does not
resolve, or whose page has no channel id, is reported in `missing` and left out.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "Mozilla/5.0 (compatible; MimirCatalogue/0.1; +https://mimir.terratalesmedia.world)"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}


def _get(url: str, retries: int = 3) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+1; SOCS=CAI"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ""
            if attempt == retries - 1:
                raise
        except urllib.error.URLError:
            if attempt == retries - 1:
                raise
        time.sleep(2 ** (attempt + 1))
    return ""


def _first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text)
    return html.unescape(m.group(1)) if m else None


def humanise(n: int) -> str:
    return f"{n / 1_000_000:.1f}M".replace(".0M", "M") if n >= 1_000_000 else f"{round(n / 1000)}K" if n >= 10_000 else f"{n:,}"


def channel(handle: str) -> dict | None:
    handle = handle if handle.startswith("@") else f"@{handle}"
    page = _get(f"https://www.youtube.com/{handle}/about")
    cid = _first(r'<link rel="alternate" type="application/rss\+xml"[^>]*channel_id=(UC[\w-]{22})', page) or _first(
        r'<meta itemprop="identifier" content="(UC[\w-]{22})"', page
    )
    if not page or not cid:
        return None
    joined = _first(r'joinedDateText":\{"content":"Joined ([^"]+)"', page)
    year = int(m.group(1)) if joined and (m := re.search(r"(\d{4})", joined)) else None
    out = {
        "handle": handle,
        "channel_id": cid,
        "title": _first(r'<meta property="og:title" content="([^"]*)"', page),
        "joined": joined,
        "year": year,
        "country": _first(r'"country":"([^"]+)"', page),
        "subscribers": _first(r'"subscriberCountText":\{"accessibility":\{"accessibilityData":\{"label":"([^"]+)"', page),
        "videos": _first(r'"videoCountText":\{"content":"([^"]+)"', page),
        "description": _first(r'<meta property="og:description" content="([^"]*)"', page),
        "avatar": _first(r'<meta property="og:image" content="([^"]*)"', page),
        "videos_recent": [],
    }
    feed = _get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
    if feed:
        root = ET.fromstring(feed)
        for e in root.findall("a:entry", NS):
            stats = e.find("m:group/m:community/m:statistics", NS)
            out["videos_recent"].append(
                {
                    "id": e.findtext("yt:videoId", namespaces=NS),
                    "title": e.findtext("a:title", namespaces=NS),
                    "published": (e.findtext("a:published", namespaces=NS) or "")[:10],
                    "views": int(stats.get("views")) if stats is not None and stats.get("views") else None,
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("handles", nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    found, missing = [], []
    for h in a.handles:
        c = channel(h)
        (found if c else missing).append(c or h)
        time.sleep(0.5)
    a.out.write_text(json.dumps({"channels": found, "missing": missing}, indent=1, ensure_ascii=False))
    print(f"{len(found)} channels, {len(missing)} missing: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
