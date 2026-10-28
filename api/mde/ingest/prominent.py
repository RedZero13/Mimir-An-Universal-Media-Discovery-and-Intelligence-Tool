# ruff: noqa: E501  (the artist and award lists are long data lines)
"""Prominent works of any age, from Wikidata (CC0): the best-known albums of the world's most-listened-to artists, and works that won or
were nominated for the major awards. Writes a reviewable seed file, seed/prominent.json.

    python -m mde.ingest.prominent                # resolve artists and awards, rank, write the seed
    python -m mde.ingest.prominent --offline      # rebuild from the HTTP cache only

Artists: a named list of the most-streamed, chart-topping and Grammy-recognised acts worldwide (Spotify and YouTube streaming leaders,
Billboard toppers, Latin, K-pop, Indian, African, Japanese and European stars, and the catalogue legends), each resolved on Wikidata
and kept only if it has a MusicBrainz artist id and real coverage. Their albums come from Wikidata, ranked by Wikipedia coverage.
Awards: the labelled award categories below are resolved on Wikidata (an unresolved label is reported and skipped); every work that
received or was nominated for one, and has enough coverage, is added with the award named in its summary.
Streaming and award facts are public knowledge, but nothing here is copied from a chart: the ranking is Wikidata's own coverage.
Works already in the catalogue are skipped. No parents' guide, mood or theme is claimed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mde.catalogue.model import normalise_title
from mde.catalogue.seedfiles import read_seed
from mde.ingest.http import Client
from mde.ingest.recent import COLLIDES, QUERY_TYPES, SPARQL, convert, fetch, genre_index, item_ids, start_date
from mde.ingest.wikidata import TYPES, Wikidata, label_of

OUT = Path(__file__).parent.parent / "seed" / "prominent.json"
ALBUMS_PER_ARTIST = 6
MIN_ARTIST_SITELINKS = 20
MIN_ALBUM_SITELINKS = 3
MIN_AWARD_SITELINKS = 12
MUSIC_WORDS = ("singer", "rapper", "musician", "band", "duo", "dj", "producer", "group", "songwriter", "artist", "composer", "vocal", "trio", "boy band", "girl group")

ARTISTS = """Taylor Swift|Bad Bunny|The Weeknd|Drake|Ed Sheeran|Justin Bieber|Ariana Grande|Billie Eilish|Eminem|Post Malone|Bruno Mars|Kendrick Lamar|
Coldplay|Travis Scott|Rihanna|Dua Lipa|Imagine Dragons|BTS|Harry Styles|Doja Cat|SZA|Olivia Rodrigo|Sabrina Carpenter|Chappell Roan|Kanye West|J Balvin|
Shakira|Arijit Singh|Karol G|Peso Pluma|Beyoncé|Adele|Lady Gaga|Katy Perry|Maroon 5|Selena Gomez|Shawn Mendes|Lana Del Rey|Lizzo|Rosalía|Daddy Yankee|
Ozuna|Anitta|Burna Boy|Wizkid|Tems|Rema|Davido|Blackpink|Jungkook|Stray Kids|NewJeans|Twice|Seventeen|A. R. Rahman|Lata Mangeshkar|Kishore Kumar|Pritam|
Anirudh Ravichander|Diljit Dosanjh|Badshah|Sidhu Moose Wala|Yo Yo Honey Singh|Shreya Ghoshal|Sonu Nigam|Atif Aslam|Nusrat Fateh Ali Khan|Jay-Z|
Nicki Minaj|Cardi B|Megan Thee Stallion|Lil Wayne|50 Cent|Snoop Dogg|Dr. Dre|J. Cole|Lil Nas X|Future|21 Savage|Metro Boomin|Tyler, the Creator|
Frank Ocean|Childish Gambino|Kali Uchis|Miley Cyrus|Demi Lovato|Charlie Puth|Sam Smith|Lewis Capaldi|Elton John|Paul McCartney|The Beatles|Queen|
Led Zeppelin|Pink Floyd|Michael Jackson|Madonna|Prince|David Bowie|Bob Dylan|Fleetwood Mac|ABBA|U2|Radiohead|Nirvana|Metallica|AC/DC|The Rolling Stones|
Bruce Springsteen|Eagles|Oasis|Arctic Monkeys|Foo Fighters|Red Hot Chili Peppers|Linkin Park|Green Day|Muse|Twenty One Pilots|The 1975|Tame Impala|Gorillaz|
Daft Punk|Calvin Harris|David Guetta|Avicii|Martin Garrix|Kygo|Zedd|Skrillex|Swedish House Mafia|Tiësto|Fred again..|Bon Iver|Phoebe Bridgers|Hozier|
Noah Kahan|Zach Bryan|Morgan Wallen|Luke Combs|Chris Stapleton|Kacey Musgraves|Whitney Houston|Mariah Carey|Celine Dion|Stevie Wonder|Marvin Gaye|
Aretha Franklin|Amy Winehouse|Frank Sinatra|Elvis Presley|Johnny Cash|Billy Joel|Phil Collins|Britney Spears|Christina Aguilera|Justin Timberlake|Usher|
Chris Brown|Alicia Keys|John Legend|Janelle Monáe|Solange|H.E.R.|Summer Walker|Jhené Aiko|Brent Faiyaz|Daniel Caesar|Giveon|The Kid Laroi|Gracie Abrams|
Tate McRae|Benson Boone|Teddy Swims|Shaboozey|Tyla|Raye|Central Cee|Stormzy|Dave|Little Simz|Skepta|Ice Spice|GloRilla|Sexyy Red|Playboi Carti|
Don Toliver|Lil Uzi Vert|Juice WRLD|XXXTentacion|Mac Miller|Pop Smoke|Kid Cudi|Maluma|Feid|Rauw Alejandro|Myke Towers|Becky G|Natanael Cano|
Fuerza Regida|Grupo Frontera|Luis Miguel|Juanes|Carlos Vives|Enrique Iglesias|Ricky Martin|Marc Anthony|Camilo|Sebastián Yatra|Bizarrap|Quevedo|Maná|
Rammstein|Måneskin|Stromae|Aya Nakamura|Yoasobi|Kenshi Yonezu|Ado|Official Hige Dandism|Fujii Kaze|Hikaru Utada|X Japan|Babymetal|Ayra Starr|Asake|
Fela Kuti|Youssou N'Dour|Fairuz|Amr Diab|Lorde|Florence and the Machine|Mitski|Frank Zappa|Kate Bush|Joni Mitchell|Neil Young|Bob Marley|Santana|
Gojira|Tool|System of a Down|Slipknot|Iron Maiden|Black Sabbath|Judas Priest|Pearl Jam|Soundgarden|Smashing Pumpkins|The Cure|Depeche Mode|New Order|Blur|
Pulp|The Smiths|Joy Division|The Strokes|The Killers|Kings of Leon|Paramore|Fall Out Boy|My Chemical Romance|Panic! at the Disco|Weezer|The White Stripes|
Jack White|Vampire Weekend|Arcade Fire|Beach House|Wet Leg|Boygenius|Olivia Dean|Role Model|Alex Warren|Leon Thomas|Kehlani|Victoria Monét|Muni Long|
Jessie Murph|Zara Larsson|Lola Young|Djo|Ravyn Lenae|Addison Rae|Reneé Rapp|Ella Langley|Lainey Wilson|Jelly Roll|Bailey Zimmerman|Cody Johnson""".replace("\n", "").split("|")

# Award categories (Wikidata labels) per medium. A label that does not resolve to an item with that label is skipped and reported.
AWARDS = {
    "film": ["Academy Award for Best Picture", "Academy Award for Best Animated Feature", "Academy Award for Best International Feature Film",
             "Academy Award for Best Documentary Feature Film", "BAFTA Award for Best Film", "BAFTA Award for Best Animated Film",
             "BAFTA Award for Best Film Not in the English Language", "BAFTA Award for Outstanding British Film", "Palme d'Or",
             "Golden Lion", "Golden Globe Award for Best Motion Picture – Drama", "Golden Globe Award for Best Motion Picture – Musical or Comedy",
             "Filmfare Award for Best Film"],
    "series": ["Primetime Emmy Award for Outstanding Drama Series", "Primetime Emmy Award for Outstanding Comedy Series",
               "Primetime Emmy Award for Outstanding Limited or Anthology Series", "BAFTA TV Award for Best Drama Series",
               "Golden Globe Award for Best Television Series – Drama", "Peabody Award"],
    "game": ["The Game Award for Game of the Year", "The Game Award for Best Game Direction", "The Game Award for Best Narrative",
             "The Game Award for Best Action Game", "The Game Award for Best Action/Adventure Game", "The Game Award for Best Role Playing Game",
             "The Game Award for Best Independent Game", "The Game Award for Best Multiplayer Game", "BAFTA Games Award for Best Game",
             "Golden Joystick Award for Ultimate Game of the Year", "D.I.C.E. Award for Game of the Year"],
    "album": ["Grammy Award for Album of the Year", "Grammy Award for Best Rock Album", "Grammy Award for Best Rap Album",
              "Grammy Award for Best Pop Vocal Album", "Grammy Award for Best R&B Album", "Grammy Award for Best Country Album",
              "Grammy Award for Best Alternative Music Album", "Grammy Award for Best Latin Pop Album", "Grammy Award for Best Dance/Electronic Album",
              "Grammy Award for Best Progressive R&B Album", "Mercury Prize", "Brit Award for British Album of the Year", "Polaris Music Prize"],
    "book": ["Booker Prize", "Pulitzer Prize for Fiction", "National Book Award for Fiction", "Hugo Award for Best Novel", "Nebula Award for Best Novel",
             "Women's Prize for Fiction", "Carnegie Medal in Literature", "Newbery Medal"],
}


def sparql(client: Client, query: str) -> list[dict]:
    r = client.get_json(SPARQL, {"query": query, "format": "json"})
    return [{k: v["value"].rsplit("/", 1)[-1] for k, v in b.items()} for b in r["results"]["bindings"]]


def esc_lit(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def by_label(client: Client, names: list[str], extra: str, log=print) -> dict[str, tuple[str, int]]:
    """name -> (QID, sitelinks): for each English label, the most widely covered item that also satisfies the `extra` triple pattern.
    One batched SPARQL query per 40 names (the query service, not the throttled search API)."""
    found: dict[str, tuple[str, int]] = {}
    for i in range(0, len(names), 40):
        vals = " ".join(f'"{esc_lit(n)}"@en' for n in names[i:i + 40])
        try:
            rows = sparql(client, f"""SELECT ?item ?name ?sl WHERE {{ VALUES ?name {{ {vals} }}
              ?item rdfs:label ?name . {extra} ?item wikibase:sitelinks ?sl . }}""")
        except Exception as e:   # noqa: BLE001 - a failed batch only loses its own names
            log(f"  batch {i // 40}: {str(e)[:80]}")
            continue
        for r in rows:
            name = next((n for n in names[i:i + 40] if n.lower() == r["name"].lower()), r["name"])
            if int(r["sl"]) > found.get(name, ("", -1))[1]:
                found[name] = (r["item"], int(r["sl"]))
    return found


MB_SEARCH = "https://musicbrainz.org/ws/2/artist/"


def by_musicbrainz(client: Client, names: list[str], log=print) -> dict[str, tuple[str, int]]:
    """name -> (QID, sitelinks) for names the label lookup missed: MusicBrainz finds the artist's id, Wikidata maps the id to its item."""
    mbids: dict[str, str] = {}
    for name in names:
        try:
            r = client.get_json(MB_SEARCH, {"query": f'artist:"{name}"', "fmt": "json", "limit": 3})
        except Exception as e:   # noqa: BLE001 - a failed lookup only loses that name
            log(f"  musicbrainz {name}: {str(e)[:60]}")
            continue
        for a in r.get("artists", []):
            if a.get("score", 0) >= 95 and a.get("name", "").lower() == name.lower():
                mbids[a["id"]] = name
                break
    found: dict[str, tuple[str, int]] = {}
    ids = list(mbids)
    for i in range(0, len(ids), 40):
        vals = " ".join(f'"{m}"' for m in ids[i:i + 40])
        try:
            rows = sparql(client, f"SELECT ?item ?mb ?sl WHERE {{ VALUES ?mb {{ {vals} }} ?item wdt:P434 ?mb ; wikibase:sitelinks ?sl . }}")
        except Exception as e:   # noqa: BLE001
            log(f"  wikidata ids batch {i // 40}: {str(e)[:60]}")
            continue
        for r in rows:
            name = mbids.get(r["mb"])
            if name and int(r["sl"]) > found.get(name, ("", -1))[1]:
                found[name] = (r["item"], int(r["sl"]))
    return found


def artists(client: Client, log=print) -> dict[str, str]:
    """QID -> name for the named artists that resolve to a musical act (has a MusicBrainz artist id) with enough coverage."""
    got = by_label(client, ARTISTS, "?item wdt:P434 ?mb .", log)
    got.update(by_musicbrainz(client, [n for n in ARTISTS if n not in got], log))
    keep = {q: name for name, (q, sl) in got.items() if sl >= MIN_ARTIST_SITELINKS}
    for name in ARTISTS:
        if name not in got:
            log(f"  not resolved: {name}")
    log(f"artists: {len(got)} resolved, {len(keep)} kept")
    return keep


def artist_albums(client: Client, artist_ids: list[str], log=print) -> dict[str, int]:
    """Album QID -> sitelinks: each artist's most widely covered albums."""
    types = " ".join(f"wd:{t}" for t in sorted(QUERY_TYPES["album"]))
    best: dict[str, int] = {}
    for i in range(0, len(artist_ids), 25):
        vals = " ".join(f"wd:{a}" for a in artist_ids[i:i + 25])
        try:
            rows = sparql(client, f"""SELECT ?album ?artist ?sl WHERE {{
              VALUES ?artist {{ {vals} }} VALUES ?type {{ {types} }}
              ?album wdt:P175 ?artist ; wdt:P31 ?type ; wikibase:sitelinks ?sl . FILTER(?sl >= {MIN_ALBUM_SITELINKS}) }}""")
        except Exception as e:   # noqa: BLE001
            log(f"  albums batch {i // 25}: {str(e)[:80]}")
            continue
        per: dict[str, list[tuple[int, str]]] = {}
        for r in rows:
            per.setdefault(r["artist"], []).append((int(r["sl"]), r["album"]))
        for lst in per.values():
            for n, a in sorted(lst, reverse=True)[:ALBUMS_PER_ARTIST]:
                best[a] = n
    return best


def award_works(client: Client, log=print) -> dict[str, tuple[int, list[str]]]:
    """Work QID -> (sitelinks, [award labels]) for works that received or were nominated for a listed award."""
    labels_by_q: dict[str, tuple[str, str]] = {}
    for medium, names in AWARDS.items():
        got = by_label(client, names, "", log)
        for name in names:
            if name in got:
                labels_by_q[got[name][0]] = (name, medium)
            else:
                log(f"  award not resolved: {name}")
    out: dict[str, tuple[int, list[str]]] = {}
    for q, (name, _medium) in labels_by_q.items():
        try:
            rows = sparql(client, f"""SELECT ?work ?sl WHERE {{ ?work (wdt:P166|wdt:P1411) wd:{q} ; wikibase:sitelinks ?sl .
              FILTER(?sl >= {MIN_AWARD_SITELINKS}) }} LIMIT 400""")
        except Exception as e:   # noqa: BLE001
            log(f"  {name}: {str(e)[:80]}")
            continue
        for r in rows:
            n, names = out.get(r["work"], (int(r["sl"]), []))
            names.append(name)
            out[r["work"]] = (n, names)
    log(f"awards: {len(labels_by_q)} categories resolved, {len(out)} works")
    return out


def build(wd: Wikidata, client: Client, log=print) -> list[dict]:
    mine = {w["slug"] for w in json.loads(OUT.read_text())["works"]} if OUT.exists() else set()
    seed = [w for w in read_seed()["works"] if w["slug"] not in mine]
    known = {(w["medium"], normalise_title(w["title"]), w.get("year")) for w in seed}
    taken = {w["slug"] for w in seed}
    cand: dict[str, tuple[int, list[str]]] = {q: (n, []) for q, n in artist_albums(client, list(artists(client, log)), log).items()}
    for q, (n, names) in award_works(client, log).items():
        cand[q] = (max(n, cand.get(q, (0, []))[0]), names)
    ents = fetch(client, sorted(cand))
    picked, notes = [], {}
    for q, e in ents.items():
        medium = next((m for m in TYPES if set(item_ids(e, "P31")) & TYPES[m]), None)
        d = start_date(e)
        title = label_of(e)
        if not medium or not d or not title or normalise_title(title) in COLLIDES:
            continue
        year = int(d[:4])
        if any((medium, normalise_title(title), y) in known for y in (year - 1, year, year + 1)):
            continue
        n = len(e.get("sitelinks", {}))
        picked.append((medium, year, n, q, e))
        notes[q] = cand[q][1]
    log(f"{len(picked)} new works to add")
    works = convert(wd, picked, taken, genre_index())
    for w in works:
        won = notes.get(w["attributes"]["wikidata"])
        if won:
            w["summary"] += " Won or was nominated for: " + "; ".join(sorted(set(won))[:3]) + "."
    return works


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    client = Client(offline=args.offline, max_age_days=365)
    works = build(Wikidata(client), client)
    about = ("Prominent works from Wikidata (CC0): albums by the most-streamed and chart-topping artists, and works that won or were "
             "nominated for major awards. Regenerate with python -m mde.ingest.prominent; review before merging. No parents' guide is claimed.")
    OUT.write_text(json.dumps({"about": about, "works": works}, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {len(works)} works to {OUT}")


if __name__ == "__main__":
    main()
