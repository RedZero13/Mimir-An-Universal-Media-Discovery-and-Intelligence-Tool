# ruff: noqa: E501
"""Writes what the fetchers found into the catalogue, filling gaps only: it never replaces a value a person wrote.

    python -m mde.enrich.apply              dry run: prints coverage before and after
    python -m mde.enrich.apply --write      updates seed/reference-*.json, seed/recent.json, data/enrichment/{wikidata,openlibrary}.json, catalogue/gaps.json

Seed: tags (themes, moods, pacing, style, world, narrative and named subgenres), age ratings, official content notes where a rating board
published them, lengths, platforms, episode counts, franchises, countries and languages. Enrichment: ids, review scores, box office, page counts.
"""

from __future__ import annotations

import argparse
import json
import re

from mde.enrich import authoring, pool, tagger
from mde.enrich.wikidata_digest import DIGEST, LABELS
from mde.enrich.worklist import MDE, TEXT, seed_files, worklist

ENRICHMENT = MDE / "data" / "enrichment"
GAPS = MDE / "catalogue" / "gaps.json"
VERSION = "mimir-tagger-1"

COUNTRY = {
    "Q30": "US",
    "Q145": "GB",
    "Q142": "FR",
    "Q183": "DE",
    "Q668": "IN",
    "Q17": "JP",
    "Q884": "KR",
    "Q148": "CN",
    "Q159": "RU",
    "Q38": "IT",
    "Q29": "ES",
    "Q16": "CA",
    "Q408": "AU",
    "Q96": "MX",
    "Q155": "BR",
    "Q414": "AR",
    "Q34": "SE",
    "Q35": "DK",
    "Q20": "NO",
    "Q33": "FI",
    "Q27": "IE",
    "Q31": "BE",
    "Q55": "NL",
    "Q39": "CH",
    "Q40": "AT",
    "Q36": "PL",
    "Q43": "TR",
    "Q794": "IR",
    "Q801": "IL",
    "Q79": "EG",
    "Q1033": "NG",
    "Q258": "ZA",
    "Q865": "TW",
    "Q8646": "HK",
    "Q252": "ID",
    "Q869": "TH",
    "Q881": "VN",
    "Q928": "PH",
    "Q833": "MY",
    "Q334": "SG",
    "Q664": "NZ",
    "Q45": "PT",
    "Q41": "GR",
    "Q213": "CZ",
    "Q28": "HU",
    "Q218": "RO",
    "Q212": "UA",
    "Q189": "IS",
    "Q298": "CL",
    "Q739": "CO",
    "Q419": "PE",
    "Q241": "CU",
    "Q902": "BD",
    "Q843": "PK",
}
LANGUAGE = {
    "Q1860": "en",
    "Q150": "fr",
    "Q188": "de",
    "Q1321": "es",
    "Q652": "it",
    "Q5287": "ja",
    "Q9176": "ko",
    "Q7850": "zh",
    "Q13955": "ar",
    "Q1568": "hi",
    "Q5885": "ta",
    "Q8097": "te",
    "Q36236": "ml",
    "Q9063": "kn",
    "Q1571": "pa" if False else "pa",
    "Q9168": "fa",
    "Q7737": "ru",
    "Q809": "pl",
    "Q9027": "sv",
    "Q9035": "da",
    "Q9043": "no",
    "Q1412": "fi",
    "Q7411": "nl",
    "Q5146": "pt",
    "Q256": "tr",
    "Q9129": "el",
    "Q9288": "he",
    "Q9056": "cs",
    "Q9067": "hu",
    "Q9078": "ro",
    "Q8798": "uk",
    "Q9199": "bn",
}
CURRENCY = {
    "Q4917": "USD",
    "Q4916": "EUR",
    "Q25224": "GBP",
    "Q8146": "JPY",
    "Q202040": "KRW",
    "Q80524": "INR",
    "Q1104069": "CAD",
    "Q259502": "AUD",
    "Q39099": "CNY",
}
PUBLISHERS = {"Q105584": "Rotten Tomatoes", "Q150248": "Metacritic", "Q37312": "IMDb"}
PLAYTIME = {
    "crpg": 60,
    "rpg": 40,
    "jrpg": 50,
    "action-rpg": 40,
    "soulslike": 35,
    "4x-strategy": 30,
    "strategy": 25,
    "tactics": 25,
    "farming-sim": 40,
    "life-sim": 30,
    "sandbox-survival": 30,
    "action-adventure": 20,
    "roguelike": 20,
    "action-roguelite": 20,
    "deckbuilder": 15,
    "stealth": 15,
    "metroidvania": 12,
    "third-person-shooter": 12,
    "first-person-shooter": 10,
    "shooter": 10,
    "racing": 10,
    "open-world-racing": 15,
    "platformer": 6,
    "precision-platformer": 6,
    "3d-platformer": 10,
    "puzzle": 4,
    "logic-puzzle": 4,
    "physics-puzzle": 4,
    "deduction-game": 6,
    "narrative-adventure": 8,
    "cozy-game": 15,
    "puzzle-platformer": 6,
    "falling-block": 2,
    "social-deduction": 2,
}
RATED = re.compile(r"(?:\(|^)(?:MPA|MPAA|ESRB|PEGI|BBFC|FSK|CBFC)\b|\b(?:rated|rating)\b", re.I)
DESCRIPTORS = [  # content notes the rating boards publish, as advisory intensities (only what the board names is recorded)
    (r"intense violence|extreme violence|graphic violence|realistic violence|blood and gore", "graphic-violence", 0.8),
    (r"\bviolence\b|\bviolent", "graphic-violence", 0.6),
    (r"fantasy violence|mild violence|cartoon violence|comic mischief", "graphic-violence", 0.3),
    (r"\bblood\b", "graphic-violence", 0.5),
    (r"strong language|\bbad language|extreme language", "strong-language", 0.7),
    (r"\blanguage\b|crude humor|mild language", "strong-language", 0.4),
    (r"sexual content|sexual themes|sexual violence|strong sexual|nudity(?! \(partial)", "sexual-content", 0.7),
    (r"partial nudity|suggestive themes|mild sexual|sexual innuendo|\bsex\b", "sexual-content", 0.4),
    (r"drug", "substance-use", 0.5),
    (r"alcohol|tobacco|smoking", "substance-use", 0.3),
    (r"\bfear\b|horror|jump scare", "jump-scares", 0.5),
]


def rating_pair(label: str | None) -> tuple[str, str] | None:
    """('MPA', 'R') from a Wikidata rating-class label such as 'R (MPA film rating)'; None when the label is not a recognisable class."""
    if not label:
        return None
    for board, pat in (
        ("MPA", r"^(G|PG|PG-13|R|NC-17)\b"),
        ("ESRB", r"^(?:ESRB )?(E10\+|EC|E|T|M|AO)\b(?!\w)"),
        ("PEGI", r"^(?:PEGI )?(3|7|12|16|18)\b"),
        ("BBFC", r"^(?:BBFC )?(U|PG|12A|12|15|18|R18)\b"),
        ("FSK", r"^(?:FSK )?(0|6|12|16|18)\b"),
    ):
        m = re.match(pat, label.strip())
        if m and (board.lower() in label.lower() or board == "MPA" and re.search(r"MPA|MPAA|film rating|motion picture", label, re.I)):
            return board, m.group(1)
    return None


def advisories_from(notes: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    text = " ; ".join(notes).lower()
    for rx, cat, v in DESCRIPTORS:
        if re.search(rx, text):
            out[cat] = max(out.get(cat, 0), v)
    return out


OVERLAY_SUMMARIES = set(json.loads((MDE / "seed" / "summaries.json").read_text()).get("summaries", {}))  # summaries written earlier, kept as they are


class Sources:
    def __init__(self) -> None:
        self.dig = pool.load(DIGEST)
        self.wp = pool.load(TEXT / "wikipedia.jsonl")
        self.labels = {k: (v or {}).get("label") for k, v in pool.load(LABELS).items()}
        self.by = {n: pool.load(TEXT / f"{n}.jsonl") for n in ("tvmaze", "steam", "deezer", "musicbrainz", "openlibrary")}

    def blob(self, w: dict, slug: str, qid: str) -> str:
        d, wp = self.dig.get(qid) or {}, self.wp.get(qid) or {}
        parts = [d.get("description"), wp.get("description"), wp.get("extract")]
        tv, st, dz, mb, ol = (self.by[n].get(slug) or {} for n in ("tvmaze", "steam", "deezer", "musicbrainz", "openlibrary"))
        parts += [
            tv.get("summary"),
            " ".join(tv.get("genres") or []),
            st.get("description"),
            " ".join(st.get("genres") or []),
            " ".join(dz.get("genres") or []),
            " ".join(mb.get("tags") or []),
            " ".join(mb.get("genres") or []),
            ol.get("description"),
            " ".join(ol.get("subjects") or []),
            " ".join(ol.get("places") or []),
            " ".join(ol.get("people") or []),
        ]
        return " . ".join(p for p in parts if p)


def estimate_playtime(genres: list[str]) -> float:
    for g in genres:
        if g in PLAYTIME:
            return PLAYTIME[g]
    return 12


def merge_authored(w: dict, a: dict, stats: dict) -> bool:
    """The hand-written layer: its summary fills an empty or stub one, its tags replace machine-inferred non-genre tags, and wrong genres can be dropped."""
    changed = False
    if a.get("summary") and authoring.is_stub(w.get("summary")) and w["slug"] not in OVERLAY_SUMMARIES:
        w["summary"] = a["summary"]
        stats["authored_summary"] += 1
        changed = True
    terms = w.setdefault("terms", {})
    keep = {k: v for k, v in terms.items() if k.startswith("genre:") and k not in set(a.get("drop") or [])}
    new = {**keep, **{k: v for k, v in (a.get("terms") or {}).items()}}
    if new != terms:
        w["terms"] = new
        stats["authored_terms"] += 1
        changed = True
    return changed


def enrich_seed_work(w: dict, ev: Sources, qid: str, stats: dict, hand: dict | None = None) -> bool:
    """Fill one seed record in place; returns True when anything changed."""
    slug = w["slug"]
    if hand and slug in hand:
        merged = merge_authored(w, hand[slug], stats)
        return enrich_facts(w, ev, qid, stats, tag=False) or merged
    return enrich_facts(w, ev, qid, stats, tag=True)


def enrich_facts(w: dict, ev: Sources, qid: str, stats: dict, tag: bool) -> bool:
    slug, medium = w["slug"], w["medium"]
    d = ev.dig.get(qid) or {}
    changed = False
    terms = w.setdefault("terms", {})
    genres = [k.split(":", 1)[1] for k in terms if k.startswith("genre:")]
    text = ev.blob(w, slug, qid)
    runtime = w.get("runtime_minutes")
    tv, st, dz = (ev.by[n].get(slug) or {} for n in ("tvmaze", "steam", "deezer"))
    if not runtime and d.get("duration"):
        amount, unit = d["duration"]
        runtime = round(amount * {"Q7727": 1, "Q11574": 1 / 60, "Q25235": 60}.get(unit, 0)) or None
        if runtime and medium == "film" and 20 <= runtime <= 600:
            w["runtime_minutes"] = runtime
            stats["runtime"] += 1
            changed = True
    if medium == "album" and not w.get("runtime_minutes") and dz.get("seconds"):
        w["runtime_minutes"] = max(1, round(dz["seconds"] / 60))
        stats["runtime"] += 1
        changed = True
    new = {}
    if tag:
        new = tagger.tag(medium, text, genres, runtime if medium == "film" else None, w.get("year"))
        new.update(tagger.subgenres(medium, text, set(terms)))
        tv_tags = (tv.get("genres") or []) + (st.get("genres") or []) + (dz.get("genres") or [])
        mb = ev.by["musicbrainz"].get(slug) or {}
        ol = ev.by["openlibrary"].get(slug) or {}
        tv_tags += (mb.get("genres") or []) + (mb.get("tags") or []) + (ol.get("subjects") or [])
        new.update(tagger.genres_from_tags(medium, tv_tags, set(terms) | set(new)))
    for k, v in new.items():
        if k not in terms:
            terms[k] = v
            stats["terms"] += 1
            changed = True
    attrs = w.setdefault("attributes", {})
    if medium == "series":
        for key, val in (
            ("episodes", tv.get("episodes") or d.get("episodes")),
            ("seasons", tv.get("seasons") or d.get("seasons")),
            ("episode_minutes", tv.get("episode_runtime") or tv.get("runtime")),
        ):
            if val and not attrs.get(key):
                attrs[key] = val
                stats[key] += 1
                changed = True
    if medium == "game":
        if not w.get("playtime_hours") and not w.get("runtime_minutes"):
            w["playtime_hours"] = estimate_playtime(genres)
            w["length_is_estimate"] = True
            stats["playtime"] += 1
            changed = True
        plats = set(attrs.get("platforms") or [])
        for k, name in (("windows", "PC"), ("mac", "PC"), ("linux", "PC")):
            if (st.get("platforms") or {}).get(k):
                plats.add(name)
        for q in d.get("platform", []):
            lab = (ev.labels.get(q) or "").lower()
            for needle, name in (
                ("playstation", "PlayStation"),
                ("xbox", "Xbox"),
                ("nintendo", "Nintendo"),
                ("windows", "PC"),
                ("macos", "PC"),
                ("linux", "PC"),
                ("steam", "PC"),
            ):
                if needle in lab:
                    plats.add(name)
        if plats and set(attrs.get("platforms") or []) != plats:
            attrs["platforms"] = sorted(plats)
            stats["platforms"] += 1
            changed = True
    if not w.get("countries"):
        c = [COUNTRY[q] for q in d.get("origin", []) if q in COUNTRY]
        if c:
            w["countries"] = c
            stats["countries"] += 1
            changed = True
    if not w.get("language"):
        lg = next((LANGUAGE[q] for q in d.get("language", []) if q in LANGUAGE), None)
        if lg:
            w["language"] = lg
            stats["language"] += 1
            changed = True
    # age ratings: Wikidata rating classes, then the boards' own entries on Steam
    ratings = [list(r) for r in w.get("ratings", [])]
    have = {r[0] for r in ratings}
    for kind in ("mpaa", "esrb", "pegi", "bbfc", "fsk"):
        for q in d.get(kind, []):
            pair = rating_pair(ev.labels.get(q))
            if pair and pair[0] not in have:
                ratings.append([pair[0], pair[1], None])
                have.add(pair[0])
    for board, rec in (st.get("ratings") or {}).items():
        b = {"esrb": "ESRB", "pegi": "PEGI"}.get(board)
        if b and b not in have and rec.get("rating"):
            r = str(rec["rating"]).upper()
            ratings.append([b, r if b == "PEGI" else {"E10": "E10+"}.get(r, r), None])
            have.add(b)
    # One order everywhere: the database returns ratings by system, so the seed lists them that way too.
    ratings.sort(key=lambda r: r[0])
    if ratings != w.get("ratings", []) and ratings:
        w["ratings"] = ratings
        stats["ratings"] += 1
        changed = True
    # official content notes become partial advisories (everything the board did not name stays "not assessed")
    notes = [r.get("descriptors") or "" for r in (st.get("ratings") or {}).values()] + [st.get("content_notes") or ""]
    adv = advisories_from([n for n in notes if n])
    if dz.get("explicit"):
        adv["strong-language"] = max(adv.get("strong-language", 0), 0.6)
    if adv:
        cur = w.setdefault("advisories", {})
        for k, v in adv.items():
            if k not in cur:
                cur[k] = v
                stats["advisories"] += 1
                changed = True
    return changed


def run(write: bool) -> None:
    ev = Sources()
    work_qid = {w["slug"]: w["qid"] for w in worklist()}
    hand = authoring.authored()
    stats: dict[str, int] = {
        k: 0
        for k in (
            "authored_summary",
            "authored_terms",
            "terms",
            "runtime",
            "episodes",
            "seasons",
            "episode_minutes",
            "playtime",
            "platforms",
            "countries",
            "language",
            "ratings",
            "advisories",
        )
    }
    touched = 0
    for f in seed_files():
        raw = f.read_text()
        data = json.loads(raw)
        for w in data["works"]:
            qid = work_qid.get(w["slug"])
            if qid and enrich_seed_work(w, ev, qid, stats, hand):
                touched += 1
        if write:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + ("\n" if raw.endswith("\n") else ""))
    print(f"works touched: {touched}")
    print(json.dumps(stats))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    run(ap.parse_args().write)


if __name__ == "__main__":
    main()
