"""Wikimedia Commons: URLs, licences and authors for freely licensed images referenced from Wikidata."""

from __future__ import annotations

import html
import re

from mde.ingest.http import Client

API = "https://commons.wikimedia.org/w/api.php"


def image_info(client: Client, filename: str, width: int = 600) -> dict | None:
    data = client.get_json(API, {"action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
                                 "iiprop": "url|extmetadata", "iiurlwidth": width, "format": "json"})
    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [None])[0]
        if not info:
            return None
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", html.unescape(meta.get("Artist", {}).get("value", ""))).strip()
        return {"url": info.get("thumburl") or info["url"], "page": info.get("descriptionurl"),
                "licence": meta.get("LicenseShortName", {}).get("value", "see file page"),
                "attribution": artist or "Wikimedia Commons"}
    return None
