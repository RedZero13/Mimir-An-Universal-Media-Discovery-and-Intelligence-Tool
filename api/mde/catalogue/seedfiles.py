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
    for path in sorted(seed_dir.glob("*.json")):
        if path.name == "catalogue.json":
            continue
        part = json.loads(path.read_text())
        base["works"] += part.get("works", [])
        base["relationships"] += part.get("relationships", [])
    return base
