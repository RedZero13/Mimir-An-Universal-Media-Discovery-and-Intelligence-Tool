"""Outbound links: where to read reactions, listen or find out more. Links only; nothing is fetched."""

from __future__ import annotations

from urllib.parse import quote, quote_plus


def links_for(work: dict, ids: dict, wikipedia: str | None = None) -> list[dict]:
    title, year, medium = work["title"], work.get("year"), work["medium"]
    creator = next((c[1] for c in work.get("credits", []) if c[0] in ("director", "author", "developer", "artist")), "")
    q = f"{title} {year or ''}".strip()
    out: list[dict] = []

    def add(kind: str, label: str, url: str) -> None:
        out.append({"kind": kind, "label": label, "url": url})

    if medium == "film":
        add("reactions:letterboxd", "Letterboxd",
            f"https://letterboxd.com/film/{ids['letterboxd']}/" if ids.get("letterboxd")
            else f"https://letterboxd.com/search/{quote(title)}/")
        add("reactions:rotten-tomatoes", "Rotten Tomatoes",
            f"https://www.rottentomatoes.com/{ids['rotten_tomatoes']}" if ids.get("rotten_tomatoes")
            else f"https://www.rottentomatoes.com/search?search={quote_plus(title)}")
        if ids.get("imdb"):
            add("info:imdb", "IMDb", f"https://www.imdb.com/title/{ids['imdb']}/")
        if ids.get("metacritic"):
            add("reactions:metacritic", "Metacritic", f"https://www.metacritic.com/{ids['metacritic']}")
        add("watch:justwatch", "Where to watch (JustWatch)", f"https://www.justwatch.com/us/search?q={quote_plus(title)}")
    elif medium == "book":
        if ids.get("openlibrary"):
            add("info:openlibrary", "Open Library", f"https://openlibrary.org/works/{ids['openlibrary']}")
        add("reactions:goodreads", "Goodreads", f"https://www.goodreads.com/search?q={quote_plus(f'{title} {creator}')}")
        add("reactions:storygraph", "The StoryGraph", f"https://app.thestorygraph.com/browse?search_term={quote_plus(title)}")
    elif medium == "game":
        if ids.get("steam"):
            add("buy:steam", "Steam", f"https://store.steampowered.com/app/{ids['steam']}/")
        add("reactions:metacritic", "Metacritic", f"https://www.metacritic.com/search/{quote(title)}/")
    elif medium == "album":
        add("listen:spotify", "Listen on Spotify", f"https://open.spotify.com/search/{quote(f'{creator} {title}')}")
        add("listen:youtube-music", "YouTube Music", f"https://music.youtube.com/search?q={quote_plus(f'{creator} {title}')}")
        if ids.get("musicbrainz_release_group"):
            add("info:musicbrainz", "MusicBrainz", f"https://musicbrainz.org/release-group/{ids['musicbrainz_release_group']}")
    reddit_q = f'"{title}"' + (f" {year}" if year else "")
    add("reactions:reddit", "Reddit discussions", f"https://www.reddit.com/search/?q={quote_plus(reddit_q)}")
    add("reactions:youtube", "Video reviews on YouTube", f"https://www.youtube.com/results?search_query={quote_plus(q + ' review')}")
    if wikipedia:
        add("info:wikipedia", "Wikipedia", wikipedia)
    return out


def spotify_track(artist: str, title: str) -> str:
    return f"https://open.spotify.com/search/{quote(f'{artist} {title}')}"
