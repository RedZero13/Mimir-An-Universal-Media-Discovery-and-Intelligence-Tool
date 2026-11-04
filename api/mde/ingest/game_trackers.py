# ruff: noqa: E501
"""Character and weapon lists for the in-game trackers (Genshin Impact, Honkai: Star Rail, Zenless Zone Zero), plus the wish rules.

    python -m mde.ingest.game_trackers          fetch the lists and write catalogue/game-trackers.json

The lists come from the EnkaNetwork API-docs repository (https://github.com/EnkaNetwork/API-docs, open community data: names, rarity,
element and weapon type; nothing is copied from the games' own pages). Entries the repository has no English name for are left out.
The wish rules are the published base rates and pity limits as the community has measured them; they are only presets, and the
tracker lets people edit every number, because the games change them.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.request
from pathlib import Path

from mde.ingest.game_checklists import checklist_games

RAW = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/"
OUT = Path(__file__).parent.parent / "catalogue" / "game-trackers.json"
UA = "MimirCatalogue/0.1 (+https://mimir.terratalesmedia.world)"

# Wish rules: hard = the pull on which a 5-star is certain, soft = the first pull whose rate rises, step = how much each later pull adds
# (percentage points), base = the rate before the soft pity (percent), guarantee = the chance the 5-star is the featured one ("5050" or "7525").
RULES = {
    "genshin-impact": {
        "name": "Genshin Impact",
        "currency": "Primogems",
        "per_pull": 160,
        "pull_name": "Wish",
        "banners": [
            {"key": "character", "name": "Character event wish", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.5, "pity4": 10},
            {"key": "weapon", "name": "Weapon event wish", "hard": 80, "soft": 63, "step": 7.0, "base": 0.7, "featured": 0.75, "pity4": 10},
            {"key": "standard", "name": "Standard wish", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.0, "pity4": 10},
        ],
    },
    "honkai-star-rail": {
        "name": "Honkai: Star Rail",
        "currency": "Stellar Jade",
        "per_pull": 160,
        "pull_name": "Warp",
        "banners": [
            {"key": "character", "name": "Character event warp", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.5, "pity4": 10},
            {"key": "lightcone", "name": "Light cone event warp", "hard": 80, "soft": 66, "step": 7.0, "base": 0.8, "featured": 0.75, "pity4": 10},
            {"key": "standard", "name": "Stellar warp (standard)", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.0, "pity4": 10},
        ],
    },
    "zenless-zone-zero": {
        "name": "Zenless Zone Zero",
        "currency": "Polychrome",
        "per_pull": 160,
        "pull_name": "Signal search",
        "banners": [
            {"key": "agent", "name": "Exclusive channel (agent)", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.5, "pity4": 10},
            {"key": "wengine", "name": "W-engine channel", "hard": 80, "soft": 65, "step": 7.0, "base": 1.0, "featured": 0.75, "pity4": 10},
            {"key": "standard", "name": "Stable channel (standard)", "hard": 90, "soft": 74, "step": 6.0, "base": 0.6, "featured": 0.0, "pity4": 10},
        ],
    },
    "wuthering-waves": {
        "name": "Wuthering Waves",
        "currency": "Astrite",
        "per_pull": 160,
        "pull_name": "Convene",
        "banners": [
            {
                "key": "character",
                "name": "Featured resonator convene",
                "hard": 80,
                "soft": 66,
                "step": 6.0,
                "base": 0.8,
                "featured": 0.5,
                "pity4": 10,
            },
            {"key": "weapon", "name": "Featured weapon convene", "hard": 80, "soft": 66, "step": 6.0, "base": 0.8, "featured": 1.0, "pity4": 10},
            {"key": "standard", "name": "Standard convene", "hard": 80, "soft": 66, "step": 6.0, "base": 0.8, "featured": 0.0, "pity4": 10},
        ],
    },
}


def get(path: str):
    req = urllib.request.Request(RAW + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def genshin() -> list[dict]:
    loc = get("loc.json")["en"]
    elements = {"Fire": "Pyro", "Water": "Hydro", "Wind": "Anemo", "Electric": "Electro", "Grass": "Dendro", "Ice": "Cryo", "Rock": "Geo"}
    weapons = {
        "WEAPON_SWORD_ONE_HAND": "Sword",
        "WEAPON_CLAYMORE": "Claymore",
        "WEAPON_POLE": "Polearm",
        "WEAPON_BOW": "Bow",
        "WEAPON_CATALYST": "Catalyst",
    }
    chars = []
    for cid, c in get("characters.json").items():
        name = loc.get(str(c.get("NameTextMapHash", "")))
        rar = {"QUALITY_ORANGE": 5, "QUALITY_PURPLE": 4}.get(c.get("QualityType"))
        if name and rar:
            chars.append(
                {
                    "id": cid,
                    "name": name,
                    "rarity": rar,
                    "type": elements.get(c.get("Element"), c.get("Element")),
                    "sub": weapons.get(c.get("WeaponType"), ""),
                }
            )
    wtypes = {1: "Sword", 10: "Catalyst", 11: "Claymore", 12: "Bow", 13: "Polearm"}
    weps = []
    for wid, w in get("gi/weapons.json").items():
        name = loc.get(str(w.get("NameTextMapHash", "")))
        if name and w.get("Rarity", 0) >= 3:
            weps.append({"id": wid, "name": name, "rarity": w["Rarity"], "type": wtypes.get(w.get("WeaponType"), "")})
    return [
        {"key": "characters", "label": "Characters", "types_label": "Element", "items": chars},
        {"key": "weapons", "label": "Weapons", "types_label": "Type", "items": weps},
    ]


def hsr() -> list[dict]:
    loc = get("hsr/hsr.json")["en"]
    paths = {
        "Knight": "Preservation",
        "Rogue": "The Hunt",
        "Mage": "Erudition",
        "Warlock": "Nihility",
        "Warrior": "Destruction",
        "Shaman": "Harmony",
        "Priest": "Abundance",
        "Memory": "Remembrance",
    }
    chars = []
    for cid, c in get("hsr/honker_characters.json").items():
        name = loc.get(str(c.get("AvatarFullName", {}).get("Hash", ""))) or loc.get(str(c.get("AvatarName", {}).get("Hash", "")))
        if name and c.get("Rarity") in (4, 5):
            chars.append(
                {
                    "id": cid,
                    "name": name,
                    "rarity": c["Rarity"],
                    "type": c.get("Element", ""),
                    "sub": paths.get(c.get("AvatarBaseType"), c.get("AvatarBaseType", "")),
                }
            )
    cones = []
    for wid, w in get("hsr/honker_weps.json").items():
        name = loc.get(str(w.get("EquipmentName", {}).get("Hash", "")))
        if name and w.get("Rarity", 0) >= 3:
            cones.append({"id": wid, "name": name, "rarity": w["Rarity"], "type": paths.get(w.get("AvatarBaseType"), w.get("AvatarBaseType", ""))})
    return [
        {"key": "characters", "label": "Characters", "types_label": "Element", "items": chars},
        {"key": "lightcones", "label": "Light cones", "types_label": "Path", "items": cones},
    ]


def zzz() -> list[dict]:
    loc = get("zzz/locs.json")["en"]
    ranks = {2: "B", 3: "A", 4: "S"}
    agents = []
    for aid, a in get("zzz/avatars.json").items():
        name = loc.get(a.get("Name", ""))
        rank = ranks.get(a.get("Rarity"))
        if name and rank in ("A", "S") and "Soldier" not in name:
            agents.append(
                {
                    "id": aid,
                    "name": name,
                    "rarity": 5 if rank == "S" else 4,
                    "rank": rank,
                    "type": "/".join(a.get("ElementTypes", [])),
                    "sub": a.get("ProfessionType", ""),
                }
            )
    engines = []
    for wid, w in get("zzz/weapons.json").items():
        name = loc.get(w.get("ItemName", ""))
        rank = ranks.get(w.get("Rarity"))
        if name and rank in ("A", "S"):
            engines.append({"id": wid, "name": name, "rarity": 5 if rank == "S" else 4, "rank": rank, "type": w.get("ProfessionType", "")})
    return [
        {"key": "agents", "label": "Agents", "types_label": "Element", "items": agents},
        {"key": "wengines", "label": "W-engines", "types_label": "Specialty", "items": engines},
    ]


def main() -> None:
    games = []
    # The repository's Honkai: Star Rail names are keyed by hashes that lose precision in its JSON, so that game has no lists yet.
    for key, build in (("genshin-impact", genshin), ("honkai-star-rail", lambda: []), ("zenless-zone-zero", zzz)):
        cats = build()
        if not cats:
            games.append({"key": key, **RULES[key], "categories": []})
            continue
        for c in cats:
            seen: set[str] = set()
            # Trial copies ("Name (Trial)") and repeated entries are not separate things to own.
            c["items"] = [i for i in c["items"] if "(" not in i["name"] and not (i["name"] in seen or seen.add(i["name"]))]
            c["items"].sort(key=lambda i: (-i["rarity"], i["name"]))
        games.append({"key": key, **RULES[key], "categories": cats})
        print(key, {c["key"]: len(c["items"]) for c in cats})
    games.append({"key": "wuthering-waves", **RULES["wuthering-waves"], "categories": []})
    for g in checklist_games():
        g["source"] = "Checklists written by hand from public knowledge" + ("; Pokémon names from Wikidata (CC0)" if g["key"] == "pokedex" else "") + ". Anything missing can be added under Checklists."
        games.append(g)
    OUT.write_text(
        json.dumps(
            {
                "about": "Wish rules are community-measured presets (editable in the tracker); lists are from the EnkaNetwork API-docs open data and may lag the newest releases.",
                "generated": dt.date.today().isoformat(),
                "games": games,
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n"
    )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
