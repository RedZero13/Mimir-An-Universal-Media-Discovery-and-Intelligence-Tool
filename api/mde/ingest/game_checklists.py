# ruff: noqa: E501  (data tables: one franchise or list per line reads better than wrapping)
"""Checklist trackers for games without a gacha: every game in a franchise, bosses, villagers, the Pokédex.

Hand-written from public knowledge (titles and years are facts); the Pokédex names come from Wikidata (CC0), saved in
catalogue/pokedex.json. Anything missing or new can be added by a player under Checklists in the tracker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

POKEDEX = Path(__file__).parent.parent / "catalogue" / "pokedex.json"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _games(rows: list[tuple[str, int]]) -> list[dict]:
    return [{"id": _slug(f"{n}-{y}"), "name": n, "type": f"{y // 10 * 10}s", "sub": str(y)} for n, y in rows]


def _plain(rows: list[tuple[str, str]], sub: str = "") -> list[dict]:
    return [{"id": _slug(n), "name": n, "type": t, **({"sub": sub} if sub else {})} for n, t in rows]


FRANCHISES: list[tuple[str, str, list[tuple[str, int]], str]] = [
    ("super-mario", "Super Mario (platformers)", [
        ("Super Mario Bros.", 1985), ("Super Mario Bros.: The Lost Levels", 1986), ("Super Mario Bros. 2", 1988), ("Super Mario Bros. 3", 1988),
        ("Super Mario Land", 1989), ("Super Mario World", 1990), ("Super Mario Land 2: 6 Golden Coins", 1992), ("Super Mario 64", 1996),
        ("Super Mario Sunshine", 2002), ("New Super Mario Bros.", 2006), ("Super Mario Galaxy", 2007), ("New Super Mario Bros. Wii", 2009),
        ("Super Mario Galaxy 2", 2010), ("Super Mario 3D Land", 2011), ("New Super Mario Bros. 2", 2012), ("New Super Mario Bros. U", 2012),
        ("Super Mario 3D World", 2013), ("Super Mario Maker", 2015), ("Super Mario Run", 2016), ("Super Mario Odyssey", 2017),
        ("Super Mario Maker 2", 2019), ("Super Mario Bros. Wonder", 2023)], "Mario"),
    ("mario-kart", "Mario Kart", [
        ("Super Mario Kart", 1992), ("Mario Kart 64", 1996), ("Mario Kart: Super Circuit", 2001), ("Mario Kart: Double Dash!!", 2003),
        ("Mario Kart DS", 2005), ("Mario Kart Wii", 2008), ("Mario Kart 7", 2011), ("Mario Kart 8", 2014), ("Mario Kart 8 Deluxe", 2017),
        ("Mario Kart World", 2025)], "Mario Kart"),
    ("zelda", "The Legend of Zelda", [
        ("The Legend of Zelda", 1986), ("Zelda II: The Adventure of Link", 1987), ("A Link to the Past", 1991), ("Link's Awakening", 1993),
        ("Ocarina of Time", 1998), ("Majora's Mask", 2000), ("Oracle of Seasons", 2001), ("Oracle of Ages", 2001), ("Four Swords", 2002),
        ("The Wind Waker", 2002), ("The Minish Cap", 2004), ("Twilight Princess", 2006), ("Phantom Hourglass", 2007), ("Spirit Tracks", 2009),
        ("Skyward Sword", 2011), ("A Link Between Worlds", 2013), ("Tri Force Heroes", 2015), ("Breath of the Wild", 2017),
        ("Tears of the Kingdom", 2023), ("Echoes of Wisdom", 2024)], "Zelda"),
    ("pokemon-games", "Pokémon (main games)", [
        ("Pokémon Red and Blue", 1996), ("Pokémon Yellow", 1998), ("Pokémon Gold and Silver", 1999), ("Pokémon Crystal", 2000),
        ("Pokémon Ruby and Sapphire", 2002), ("Pokémon FireRed and LeafGreen", 2004), ("Pokémon Emerald", 2004), ("Pokémon Diamond and Pearl", 2006),
        ("Pokémon Platinum", 2008), ("Pokémon HeartGold and SoulSilver", 2009), ("Pokémon Black and White", 2010), ("Pokémon Black 2 and White 2", 2012),
        ("Pokémon X and Y", 2013), ("Pokémon Omega Ruby and Alpha Sapphire", 2014), ("Pokémon Sun and Moon", 2016), ("Pokémon Ultra Sun and Ultra Moon", 2017),
        ("Pokémon Let's Go, Pikachu! and Let's Go, Eevee!", 2018), ("Pokémon Sword and Shield", 2019), ("Pokémon Brilliant Diamond and Shining Pearl", 2021),
        ("Pokémon Legends: Arceus", 2022), ("Pokémon Scarlet and Violet", 2022), ("Pokémon Legends: Z-A", 2025)], "Pokémon"),
    ("final-fantasy", "Final Fantasy (main series)", [
        ("Final Fantasy", 1987), ("Final Fantasy II", 1988), ("Final Fantasy III", 1990), ("Final Fantasy IV", 1991), ("Final Fantasy V", 1992),
        ("Final Fantasy VI", 1994), ("Final Fantasy VII", 1997), ("Final Fantasy VIII", 1999), ("Final Fantasy IX", 2000), ("Final Fantasy X", 2001),
        ("Final Fantasy XI", 2002), ("Final Fantasy XII", 2006), ("Final Fantasy XIII", 2009), ("Final Fantasy XIV", 2010), ("Final Fantasy XV", 2016),
        ("Final Fantasy VII Remake", 2020), ("Final Fantasy XVI", 2023), ("Final Fantasy VII Rebirth", 2024)], "Final Fantasy"),
    ("fromsoftware", "FromSoftware action games", [
        ("Demon's Souls", 2009), ("Dark Souls", 2011), ("Dark Souls II", 2014), ("Bloodborne", 2015), ("Dark Souls III", 2016), ("Sekiro: Shadows Die Twice", 2019),
        ("Elden Ring", 2022), ("Armored Core VI: Fires of Rubicon", 2023), ("Elden Ring Nightreign", 2025)], "FromSoftware"),
    ("resident-evil", "Resident Evil (main games and remakes)", [
        ("Resident Evil", 1996), ("Resident Evil 2", 1998), ("Resident Evil 3: Nemesis", 1999), ("Resident Evil – Code: Veronica", 2000),
        ("Resident Evil Zero", 2002), ("Resident Evil (remake)", 2002), ("Resident Evil 4", 2005), ("Resident Evil 5", 2009), ("Resident Evil 6", 2012),
        ("Resident Evil 7: Biohazard", 2017), ("Resident Evil 2 (remake)", 2019), ("Resident Evil 3 (remake)", 2020), ("Resident Evil Village", 2021),
        ("Resident Evil 4 (remake)", 2023)], "Resident Evil"),
    ("grand-theft-auto", "Grand Theft Auto", [
        ("Grand Theft Auto", 1997), ("Grand Theft Auto 2", 1999), ("Grand Theft Auto III", 2001), ("Grand Theft Auto: Vice City", 2002),
        ("Grand Theft Auto: San Andreas", 2004), ("Grand Theft Auto IV", 2008), ("Grand Theft Auto V", 2013)], "Grand Theft Auto"),
    ("assassins-creed", "Assassin's Creed (main games)", [
        ("Assassin's Creed", 2007), ("Assassin's Creed II", 2009), ("Assassin's Creed: Brotherhood", 2010), ("Assassin's Creed: Revelations", 2011),
        ("Assassin's Creed III", 2012), ("Assassin's Creed IV: Black Flag", 2013), ("Assassin's Creed Rogue", 2014), ("Assassin's Creed Unity", 2014),
        ("Assassin's Creed Syndicate", 2015), ("Assassin's Creed Origins", 2017), ("Assassin's Creed Odyssey", 2018), ("Assassin's Creed Valhalla", 2020),
        ("Assassin's Creed Mirage", 2023), ("Assassin's Creed Shadows", 2025)], "Assassin's Creed"),
    ("mass-effect-witcher", "Mass Effect and The Witcher", [
        ("Mass Effect", 2007), ("Mass Effect 2", 2010), ("Mass Effect 3", 2012), ("Mass Effect: Andromeda", 2017),
        ("The Witcher", 2007), ("The Witcher 2: Assassins of Kings", 2011), ("The Witcher 3: Wild Hunt", 2015)], "Mass Effect, The Witcher"),
    ("halo", "Halo", [
        ("Halo: Combat Evolved", 2001), ("Halo 2", 2004), ("Halo 3", 2007), ("Halo 3: ODST", 2009), ("Halo: Reach", 2010), ("Halo 4", 2012),
        ("Halo 5: Guardians", 2015), ("Halo Infinite", 2021)], "Halo"),
    ("metal-gear", "Metal Gear", [
        ("Metal Gear", 1987), ("Metal Gear 2: Solid Snake", 1990), ("Metal Gear Solid", 1998), ("Metal Gear Solid 2: Sons of Liberty", 2001),
        ("Metal Gear Solid 3: Snake Eater", 2004), ("Metal Gear Solid 4: Guns of the Patriots", 2008), ("Metal Gear Solid: Peace Walker", 2010),
        ("Metal Gear Solid V: Ground Zeroes", 2014), ("Metal Gear Solid V: The Phantom Pain", 2015)], "Metal Gear"),
    ("kingdom-hearts", "Kingdom Hearts", [
        ("Kingdom Hearts", 2002), ("Kingdom Hearts: Chain of Memories", 2004), ("Kingdom Hearts II", 2005), ("Kingdom Hearts 358/2 Days", 2009),
        ("Kingdom Hearts Birth by Sleep", 2010), ("Kingdom Hearts Re:coded", 2010), ("Kingdom Hearts 3D: Dream Drop Distance", 2012),
        ("Kingdom Hearts III", 2019)], "Kingdom Hearts"),
    ("god-of-war-uncharted-tlou", "God of War, Uncharted and The Last of Us", [
        ("God of War", 2005), ("God of War II", 2007), ("God of War III", 2010), ("God of War", 2018), ("God of War Ragnarök", 2022),
        ("Uncharted: Drake's Fortune", 2007), ("Uncharted 2: Among Thieves", 2009), ("Uncharted 3: Drake's Deception", 2011), ("Uncharted 4: A Thief's End", 2016),
        ("The Last of Us", 2013), ("The Last of Us Part II", 2020)], "PlayStation"),
    ("metroid", "Metroid", [
        ("Metroid", 1986), ("Metroid II: Return of Samus", 1991), ("Super Metroid", 1994), ("Metroid Prime", 2002), ("Metroid Fusion", 2002),
        ("Metroid Prime 2: Echoes", 2004), ("Metroid Prime 3: Corruption", 2007), ("Metroid Dread", 2021), ("Metroid Prime 4: Beyond", 2025)], "Metroid"),
    ("city-builders", "SimCity and city builders", [
        ("SimCity", 1989), ("SimCity 2000", 1993), ("SimCity 3000", 1999), ("SimCity 4", 2003), ("SimCity Societies", 2007), ("SimCity", 2013),
        ("Cities: Skylines", 2015), ("Cities: Skylines II", 2023)], "SimCity"),
    ("sims-civ", "The Sims and Civilization", [
        ("The Sims", 2000), ("The Sims 2", 2004), ("The Sims 3", 2009), ("The Sims 4", 2014),
        ("Sid Meier's Civilization", 1991), ("Civilization II", 1996), ("Civilization III", 2001), ("Civilization IV", 2005), ("Civilization V", 2010),
        ("Civilization VI", 2016), ("Civilization VII", 2025)], "The Sims, Civilization"),
    ("candy-crush", "Candy Crush", [
        ("Candy Crush Saga", 2012), ("Candy Crush Soda Saga", 2014), ("Candy Crush Jelly Saga", 2016), ("Candy Crush Friends Saga", 2018)], "Candy Crush"),
]


def _franchise_games() -> list[dict]:
    out = []
    for key, name, rows, _about in FRANCHISES:
        out.append({
            "key": key, "name": name, "kind": "checklist", "pull_name": "", "banners": [],
            "categories": [{"key": "games", "label": "Games", "verb": ["Played", "Not played"], "types_label": "Decade", "items": _games(rows)}],
        })
    return out


def _dex() -> list[dict]:
    names = json.loads(POKEDEX.read_text())
    gens = [(151, "Gen I (Kanto)"), (251, "Gen II (Johto)"), (386, "Gen III (Hoenn)"), (493, "Gen IV (Sinnoh)"), (649, "Gen V (Unova)"), (721, "Gen VI (Kalos)"),
            (809, "Gen VII (Alola)"), (905, "Gen VIII (Galar and Hisui)"), (1025, "Gen IX (Paldea)")]
    items = []
    for n in range(1, 1026):
        gen = next(label for top, label in gens if n <= top)
        items.append({"id": str(n), "name": names[str(n)], "type": gen, "sub": f"#{n:04d}"})
    return items


ELDEN_BOSSES = [
    ("Margit, the Fell Omen", "Main"), ("Godrick the Grafted", "Demigod"), ("Red Wolf of Radagon", "Main"), ("Rennala, Queen of the Full Moon", "Demigod"),
    ("Starscourge Radahn", "Demigod"), ("Rykard, Lord of Blasphemy", "Demigod"), ("Morgott, the Omen King", "Demigod"), ("Mohg, Lord of Blood", "Demigod"),
    ("Malenia, Blade of Miquella", "Demigod"), ("Godskin Duo", "Remembrance"), ("Fire Giant", "Remembrance"), ("Maliketh, the Black Blade", "Remembrance"),
    ("Astel, Naturalborn of the Void", "Remembrance"), ("Dragonlord Placidusax", "Remembrance"), ("Lichdragon Fortissax", "Remembrance"),
    ("Regal Ancestor Spirit", "Remembrance"), ("Hoarah Loux, Warrior", "Final"), ("Radagon of the Golden Order", "Final"), ("Elden Beast", "Final"),
    ("Mohg, the Omen", "Remembrance"),
    ("Messmer the Impaler", "Shadow of the Erdtree"), ("Romina, Saint of the Bud", "Shadow of the Erdtree"), ("Rellana, Twin Moon Knight", "Shadow of the Erdtree"),
    ("Divine Beast Dancing Lion", "Shadow of the Erdtree"), ("Metyr, Mother of Fingers", "Shadow of the Erdtree"), ("Bayle the Dread", "Shadow of the Erdtree"),
    ("Midra, Lord of Frenzied Flame", "Shadow of the Erdtree"), ("Commander Gaius", "Shadow of the Erdtree"), ("Putrescent Knight", "Shadow of the Erdtree"),
    ("Promised Consort Radahn", "Shadow of the Erdtree"),
]
RUNES = ["Godrick's Great Rune", "Radahn's Great Rune", "Morgott's Great Rune", "Rykard's Great Rune", "Mohg's Great Rune", "Malenia's Great Rune", "Miquella's Great Rune"]


def _singles() -> list[dict]:
    return [
        {"key": "elden-ring", "name": "Elden Ring", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "bosses", "label": "Bosses", "verb": ["Defeated", "Not defeated"], "types_label": "Kind", "items": _plain(ELDEN_BOSSES)},
            {"key": "runes", "label": "Great Runes", "verb": ["Found", "Not found"], "items": _plain([(r, "Great Rune") for r in RUNES])}]},
        {"key": "pokedex", "name": "Pokédex (all 1,025)", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "dex", "label": "Pokémon", "verb": ["Caught", "Not caught"], "types_label": "Generation", "items": _dex()}]},
        {"key": "stardew-valley", "name": "Stardew Valley", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "villagers", "label": "Villagers", "verb": ["Befriended", "Not yet"], "types_label": "Kind", "items": _plain(
                [(n, "Can marry") for n in ["Abigail", "Alex", "Elliott", "Emily", "Haley", "Harvey", "Leah", "Maru", "Penny", "Sam", "Sebastian", "Shane"]]
                + [(n, "Villager") for n in ["Caroline", "Clint", "Demetrius", "Evelyn", "George", "Gus", "Jas", "Jodi", "Kent", "Krobus", "Leo", "Lewis", "Linus",
                                              "Marnie", "Pam", "Pierre", "Robin", "Sandy", "Vincent", "Willy", "Wizard", "Dwarf"]])},
            {"key": "rooms", "label": "Community Center", "verb": ["Completed", "Not completed"], "items": _plain(
                [(n, "Room") for n in ["Crafts Room", "Pantry", "Fish Tank", "Boiler Room", "Bulletin Board", "Vault"]])},
            {"key": "skills", "label": "Skills at level 10", "verb": ["Mastered", "Not yet"], "items": _plain(
                [(n, "Skill") for n in ["Farming", "Mining", "Foraging", "Fishing", "Combat"]])}]},
        {"key": "zelda-modern", "name": "Zelda: Breath of the Wild and Tears of the Kingdom", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "botw", "label": "Breath of the Wild", "verb": ["Done", "Not done"], "types_label": "Kind", "items": _plain(
                [("Vah Ruta", "Divine Beast"), ("Vah Rudania", "Divine Beast"), ("Vah Medoh", "Divine Beast"), ("Vah Naboris", "Divine Beast"),
                 ("Mipha", "Champion"), ("Daruk", "Champion"), ("Revali", "Champion"), ("Urbosa", "Champion"), ("Calamity Ganon", "Final boss")])},
            {"key": "totk", "label": "Tears of the Kingdom", "verb": ["Done", "Not done"], "types_label": "Kind", "items": _plain(
                [("Wind Temple (Tulin)", "Temple"), ("Fire Temple (Yunobo)", "Temple"), ("Water Temple (Sidon)", "Temple"), ("Lightning Temple (Riju)", "Temple"),
                 ("Spirit Temple (Mineru)", "Temple"), ("Ganondorf", "Final boss")])}]},
        {"key": "hollow-knight", "name": "Hollow Knight", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "bosses", "label": "Bosses", "verb": ["Defeated", "Not defeated"], "items": _plain(
                [(n, "Boss") for n in ["Gruz Mother", "False Knight", "Hornet (Greenpath)", "Vengefly King", "Massive Moss Charger", "Brooding Mawlek", "Mantis Lords",
                                        "Soul Master", "Dung Defender", "Crystal Guardian", "Broken Vessel", "Watcher Knights", "Uumuu", "Nosk", "Flukemarm",
                                        "Hive Knight", "Traitor Lord", "Hornet (Kingdom's Edge)", "Troupe Master Grimm", "The Collector", "Nightmare King Grimm",
                                        "The Hollow Knight", "Radiance"]])}]},
        {"key": "minecraft", "name": "Minecraft", "kind": "checklist", "pull_name": "", "banners": [], "categories": [
            {"key": "milestones", "label": "Milestones", "verb": ["Done", "Not done"], "items": _plain(
                [(n, "Milestone") for n in ["Survive the first night", "Craft an iron pickaxe", "Find diamonds", "Enter the Nether", "Find a Nether fortress",
                                             "Trade with a piglin", "Find a stronghold", "Enter the End", "Defeat the Ender Dragon", "Defeat the Wither",
                                             "Defeat an Elder Guardian", "Find an Elytra", "Light a beacon", "Defeat the Warden"]])}]},
    ]


def checklist_games() -> list[dict]:
    return _singles() + _franchise_games()
