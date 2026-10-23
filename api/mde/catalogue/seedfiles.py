"""The editorial seed: catalogue.json (the pilot, with defaults) plus every other seed/*.json, merged in name order.

Splitting the seed by medium keeps each file reviewable. Pure: reads files, imports nothing from the database layer.
"""

from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).parent.parent / "seed"


def read_seed(seed_dir: Path = SEED_DIR) -> dict:
    base = json.loads((seed_dir / "catalogue.json").read_text())
    base.setdefault("relationships", [])
    overlays: list[dict] = []
    for path in sorted(seed_dir.glob("*.json")):
        if path.name == "catalogue.json":
            continue
        part = json.loads(path.read_text())
        base["works"] += part.get("works", [])
        base["relationships"] += part.get("relationships", [])
        overlays.append(part.get("terms", {}))
    # Term overlays (seed/subgenres.json) add tags to works defined in any file.
    by_slug = {w["slug"]: w for w in base["works"]}
    for overlay in overlays:
        for slug, terms in overlay.items():
            if slug not in by_slug:
                raise ValueError(f"term overlay names unknown work {slug!r}")
            by_slug[slug]["terms"] = {**by_slug[slug].get("terms", {}), **terms}
    return base
