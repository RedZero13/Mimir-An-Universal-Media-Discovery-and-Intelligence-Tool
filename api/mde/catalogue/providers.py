"""Where to watch, listen, read or play: one link per service, built from providers.json.

Links open each service's search for the work (or its exact page when the catalogue holds the service's ID).
Nothing here claims a title is available on a service; that varies by region and over time.
Pure: no I/O beyond reading the registry. Mirrored by demo/engine.cjs (whereFor) and parity-tested.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from mde.catalogue.model import WorkProfile

PROVIDERS_PATH = Path(__file__).parent / "providers.json"


@lru_cache(maxsize=1)
def load_providers() -> dict:
    return json.loads(PROVIDERS_PATH.read_text())


def _encode(q: str, enc: str) -> str:
    encoded = quote(q, safe="")
    return encoded.replace("%20", "+") if enc == "query" else encoded


def item_of(w: WorkProfile) -> dict:
    platforms = w.attributes.get("platforms")
    return {"medium": w.medium, "title": w.title, "creator": w.creators[0] if w.creators else "", "year": w.year,
            "platforms": list(platforms) if isinstance(platforms, list) else [], "ids": dict(w.ids)}


def where_to(item: dict, region: str | None = None, spec: dict | None = None) -> dict | None:
    spec = spec or load_providers()
    media = spec["media"].get(item["medium"])
    if media is None:
        return None
    region = region if region in spec["regions"] else spec["default_region"]
    fields = spec["regions"][region]
    platforms = item.get("platforms") or []
    ids = item.get("ids") or {}
    out = []
    for p in media["providers"]:
        if "regions" in p and region not in p["regions"]:
            continue
        if "platforms" in p and platforms and not any(x in platforms for x in p["platforms"]):
            continue
        exact = p.get("exact")
        if exact and ids.get(exact["id"]):
            url = exact["url"].replace("{id}", quote(str(ids[exact["id"]]), safe=""))
        else:
            q = p["q"]
            for key in ("title", "creator", "year"):
                value = item.get(key)
                q = q.replace("{" + key + "}", "" if value is None else str(value))
            q = re.sub(r"\s+", " ", q).strip()
            url = p["url"]
            for key, value in fields.items():
                url = url.replace("{" + key + "}", value)
            url = url.replace("{q}", _encode(q, p["enc"]))
        out.append({"id": p["id"], "name": p["name"], "verb": p.get("verb", media["verb"]), "url": url,
                    "exact": bool(exact and ids.get(exact["id"]))})
    default = media["default"] if any(p["id"] == media["default"] for p in out) else (out[0]["id"] if out else None)
    return {"medium": item["medium"], "verb": media["verb"], "region": region, "default": default, "providers": out}
