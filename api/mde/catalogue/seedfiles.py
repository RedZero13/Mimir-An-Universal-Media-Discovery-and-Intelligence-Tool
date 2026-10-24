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
        overlays.append({"terms": part.get("terms", {}), "attributes": part.get("attributes", {}), "credits": part.get("credits", {})})
    # Overlays add to works defined in any file: tags (seed/subgenres.json), attributes such as franchises, and
    # extra credits such as lead cast (seed/people-and-franchises.json). Existing values win over overlay attributes.
    by_slug = {w["slug"]: w for w in base["works"]}

    def target(slug: str) -> dict:
        if slug not in by_slug:
            raise ValueError(f"overlay names unknown work {slug!r}")
        return by_slug[slug]

    for overlay in overlays:
        for slug, terms in overlay["terms"].items():
            w = target(slug)
            w["terms"] = {**w.get("terms", {}), **terms}
        for slug, attrs in overlay["attributes"].items():
            w = target(slug)
            w["attributes"] = {**attrs, **w.get("attributes", {})}
        for slug, credits in overlay["credits"].items():
            w = target(slug)
            have = {(c[0], c[1]) for c in w.get("credits", [])}
            added = []
            for c in credits:   # a credit already present (or repeated in the overlay) is skipped
                if (c[0], c[1]) not in have:
                    have.add((c[0], c[1]))
                    added.append(c)
            w["credits"] = [*w.get("credits", []), *added]
    return base
