"""MusicBrainz (core data CC0) and the Cover Art Archive: album identity, tracklists, track lengths, remixes, covers."""

from __future__ import annotations

import re
import unicodedata

from mde.ingest.http import Client

WS = "https://musicbrainz.org/ws/2"
LICENCE = "MusicBrainz core data CC0; cover art via the Cover Art Archive, rights remain with the owners"


def lucene(text: str) -> str:
    """Escape a value for a quoted MusicBrainz (Lucene) query term."""
    return re.sub(r'([+\-&|!(){}\[\]^"~*?:\\/])', r"\\\1", text)


def _key(text: str) -> str:
    """Comparison key that ignores case, accents, punctuation (’ vs ', ‐ vs -), "&" vs "and" and a leading article."""
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    text = re.sub(r"^(the|a|an)\s+", "", text.replace("&", " and ").strip())
    return re.sub(r"[\W_]", "", text)


def best_release_group(groups: list[dict], title: str | list[str], artist: str | None, year: int | None) -> dict | None:
    wants = {_key(t) for t in ([title] if isinstance(title, str) else title)}
    for g in groups:
        if _key(g.get("title", "")) not in wants or g.get("primary-type") not in ("Album", "EP"):
            continue
        # Joined as credited ("Prince" + " and " + "The Revolution"), so multi-artist credits compare whole.
        credit = "".join(a.get("name", "") + a.get("joinphrase", " ") for a in g.get("artist-credit", []) if isinstance(a, dict))
        if artist and _key(artist) not in _key(credit):
            continue
        first = (g.get("first-release-date") or "")[:4]
        if year and first.isdigit() and abs(int(first) - year) > 1:
            continue
        return g
    return None


def pick_release(releases: list[dict]) -> dict | None:
    """The standard edition: among official releases with a track list, the most common track count (so one-off
    bonus-track and deluxe editions lose), then the earliest date. Ties between counts go to the earliest release."""
    with_tracks = [r for r in releases if any(m.get("tracks") for m in r.get("media", []))]
    if not with_tracks:
        return None
    count = lambda r: sum(len(m.get("tracks", [])) for m in r.get("media", []))  # noqa: E731
    freq: dict[int, int] = {}
    for r in with_tracks:
        freq[count(r)] = freq.get(count(r), 0) + 1
    first = {n: min(r.get("date") or "9999" for r in with_tracks if count(r) == n) for n in freq}
    standard = min(freq, key=lambda n: (-freq[n], first[n]))
    return min((r for r in with_tracks if count(r) == standard), key=lambda r: r.get("date") or "9999")


def tracklist(release: dict) -> list[dict]:
    out = []
    for disc, medium in enumerate(release.get("media", []), start=1):
        for t in medium.get("tracks", []):
            rec = t.get("recording", {})
            length = t.get("length") or rec.get("length")
            out.append({"disc": disc, "position": t.get("position"), "title": t.get("title") or rec.get("title"),
                        "seconds": round(length / 1000) if length else None, "recording": rec.get("id")})
    return out


def remixes(recording: dict) -> list[dict]:
    """Recording-to-recording 'remix' relations: backward means the other recording remixes this one."""
    out = []
    for rel in recording.get("relations", []):
        if rel.get("type") != "remix" or rel.get("target-type") != "recording":
            continue
        other = rel.get("recording", {})
        artists = " & ".join(a.get("name", "") for a in other.get("artist-credit", []) if isinstance(a, dict))
        out.append({"title": other.get("title"), "artist": artists or None, "recording": other.get("id"),
                    "direction": "remixed_as" if rel.get("direction") == "backward" else "remix_of"})
    return out


class MusicBrainz:
    def __init__(self, client: Client, with_remixes: bool = True):
        self.client = client
        self.with_remixes = with_remixes

    def enrich(self, work: dict) -> dict:
        artist = next((c[1] for c in work.get("credits", []) if c[0] == "artist"), None)
        titles = [work["title"], *((work.get("attributes") or {}).get("aka") or [])]
        groups: list[dict] = []
        g = None
        for t in titles:
            q = f'releasegroup:"{lucene(t)}"' + (f' AND artist:"{lucene(artist)}"' if artist else "")
            groups += self.client.get_json(f"{WS}/release-group", {"query": q, "fmt": "json", "limit": 10}).get("release-groups", [])
            g = best_release_group(groups, titles, artist, work.get("year"))
            if g:
                break
        if g is None:
            return {"match": None, "reason": "no album release group with matching title, artist and year",
                    "candidates": [{"mbid": x.get("id"), "title": x.get("title"), "type": x.get("primary-type"),
                                    "first": x.get("first-release-date")} for x in groups[:5]]}
        rels = self.client.get_json(f"{WS}/release", {"release-group": g["id"], "status": "official", "inc": "recordings",
                                                      "fmt": "json", "limit": 50}).get("releases", [])
        rel = pick_release(rels)
        tracks = tracklist(rel) if rel else []
        if self.with_remixes:
            for t in tracks:
                if t["recording"]:
                    data = self.client.get_json(f"{WS}/recording/{t['recording']}",
                                                {"inc": "recording-rels+artist-credits", "fmt": "json"})
                    t["remixes"] = remixes(data)
        total = sum(t["seconds"] or 0 for t in tracks)
        return {
            "match": {"mbid": g["id"], "release": rel["id"] if rel else None, "reason": "exact title, artist and year"},
            "url": f"https://musicbrainz.org/release-group/{g['id']}",
            "facts": {"runtime_minutes": round(total / 60)} if total and all(t["seconds"] for t in tracks) else {},
            "tracks": tracks,
            "images": [{"kind": "cover", "url": f"https://coverartarchive.org/release-group/{g['id']}/front-500",
                        "licence": "Cover via the Cover Art Archive, shown for identification; rights remain with the owners",
                        "attribution": "Cover Art Archive / MusicBrainz"}],
        }
