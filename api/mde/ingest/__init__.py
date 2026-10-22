"""Fetching open data about catalogue works.

Each connector reads the editorial seed, looks each work up in one source, and returns normalised facts with
provenance. `run.py` writes them to mde/data/enrichment/<source>.json, a reviewable, committed file; raw
payloads stay in the local HTTP cache. Nothing here scrapes websites: only documented open APIs are used, and
every source's licence is recorded with its data (see docs/SOURCES.md).
"""
