"""The in-game trackers: the wish maths (demo/wish.cjs), the preset data, and that the built app carries them."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "api" / "mde" / "catalogue" / "game-trackers.json"


def test_wish_maths_passes_its_checks():
    r = subprocess.run(["node", str(ROOT / "demo" / "wish.test.cjs")], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "all checks passed" in r.stdout


def test_presets_are_complete_and_sane():
    d = json.loads(DATA.read_text())
    games = {g["key"]: g for g in d["games"]}
    assert {"genshin-impact", "honkai-star-rail", "zenless-zone-zero", "wuthering-waves"} <= set(games)
    for g in games.values():
        assert g["banners"] and g["per_pull"] > 0 and g["currency"]
        for b in g["banners"]:
            assert 0 < b["base"] < 5 and 1 < b["soft"] < b["hard"] <= 100 and 0 < b["step"] <= 20 and 0 <= b["featured"] <= 1 and b["pity4"] >= 2
    gi = {c["key"]: c["items"] for c in games["genshin-impact"]["categories"]}
    assert len(gi["characters"]) > 80 and len(gi["weapons"]) > 80
    for cat in (c for g in games.values() for c in g["categories"]):
        names = [i["name"] for i in cat["items"]]
        assert len(names) == len(set(names)), "no repeated names"
        assert all(i["rarity"] in (3, 4, 5) and i["name"].strip() and "(" not in i["name"] for i in cat["items"])
    assert any(i["name"] == "Diluc" and i["rarity"] == 5 for i in gi["characters"])


def test_built_app_carries_the_tracker(tmp_path):
    site = tmp_path / "site"
    r = subprocess.run(["node", str(ROOT / "demo" / "build.cjs"), "--site", str(site)], capture_output=True, text=True, timeout=240)
    assert r.returncode == 0, r.stderr
    js = "".join(p.read_text(errors="replace") for p in site.rglob("*.js"))
    assert "MimirWish" in js and "game-tracker" in js
    data = next(site.glob("assets/data.*.json")).read_text()
    assert '"gametrackers"' in data and "Genshin Impact" in data
