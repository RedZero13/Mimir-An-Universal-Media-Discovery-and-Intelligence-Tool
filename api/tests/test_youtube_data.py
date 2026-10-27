"""The YouTube section: every channel and video is tied to ids read from YouTube, and nothing is invented."""

import json
import re
from pathlib import Path

from mde.catalogue.seedfiles import read_seed

ENRICH = json.loads((Path(__file__).parent.parent / "mde" / "data" / "enrichment" / "youtube.json").read_text())["works"]
WORKS = [w for w in read_seed()["works"] if w["medium"] in ("channel", "online_video")]
CHANNELS = {w["slug"]: w for w in WORKS if w["medium"] == "channel"}


def test_every_channel_has_a_channel_id_and_a_handle():
    for slug, w in CHANNELS.items():
        ids = ENRICH[slug]["ids"]
        assert re.fullmatch(r"UC[\w-]{22}", ids["youtube_channel"]), slug
        assert w["attributes"]["handle"].startswith("@"), slug
        assert ENRICH[slug]["links"][0]["url"].endswith(w["attributes"]["handle"]), slug


def test_every_video_belongs_to_a_channel_and_has_a_video_id():
    for w in WORKS:
        if w["medium"] != "online_video":
            continue
        assert w["attributes"]["channel"] in CHANNELS, w["slug"]
        vid = ENRICH[w["slug"]]["ids"]["youtube_video"]
        assert re.fullmatch(r"[\w-]{11}", vid), w["slug"]
        assert w["slug"] == f"yt-{re.sub(r'[^a-z0-9]+', '-', vid.lower()).strip('-')}-{w['year']}", w["slug"]
        assert ENRICH[w["slug"]]["images"][0]["url"] == f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def test_no_duplicate_video_ids_or_channels():
    vids = [ENRICH[w["slug"]]["ids"]["youtube_video"] for w in WORKS if w["medium"] == "online_video"]
    assert len(vids) == len(set(vids))
    chans = [ENRICH[s]["ids"]["youtube_channel"] for s in CHANNELS]
    assert len(chans) == len(set(chans))


def test_new_channels_do_not_claim_a_parents_guide():
    """Advisories need an assessment; an unassessed channel carries none, which the site shows as "not assessed"."""
    more = json.loads((Path(__file__).parent.parent / "mde" / "seed" / "youtube-more.json").read_text())["works"]
    assert more and all("advisories" not in w for w in more)
