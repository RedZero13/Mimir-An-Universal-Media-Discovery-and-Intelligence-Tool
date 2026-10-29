"""Brings the imported works toward the standard of the hand-classified pilot.

The pilot works carry a written summary, 12 to 16 tags across genre, theme, mood, pacing, style, world and narrative, an age rating,
a length, credits and franchise links. The imported works arrived as genre-only entries. The modules here fetch open facts for them
(Wikidata, Wikipedia, TVmaze, Steam, MusicBrainz and others), derive tags from that material with a transparent rule set, and write
the result back into the seed files, never overwriting what a person wrote.

    python -m mde.enrich.wikidata_digest   facts from Wikidata, one entity per work (resumable)
    python -m mde.enrich.wikipedia_text    Wikipedia lead text, used only as input to the tagger (resumable, not committed)
"""
