# Third-party notices

Mimir is proprietary (see `LICENSE`). These parts come from others and keep their own terms.

## Fonts (`demo/fonts/`)

Cinzel, Cormorant Garamond, Inter and JetBrains Mono, Latin subsets as served by Google Fonts, each under the
[SIL Open Font License 1.1](https://openfontlicense.org/).

## Open data (`api/mde/data/enrichment/`)

| Source | Terms |
| --- | --- |
| Wikidata | CC0 1.0. Wikimedia Commons images keep their individual licences and attributions, shown where used |
| Open Library | Data available for reuse; cover images remain the publishers' and are shown for identification |
| MusicBrainz | Core data CC0 1.0; Cover Art Archive images remain their owners' |
| LibriVox | Recordings and catalogue data in the public domain (US) |
| Audible India, YouTube | Facts (lengths, dates, IDs) and links only; thumbnails and avatars remain the creators', shown to identify the work |

Details per source, including what is stored and displayed, are in `docs/SOURCES.md`.

## Software

The API depends on FastAPI, psycopg and other packages listed in `api/pyproject.toml`; the web app on Next.js,
React and the packages in `web/package.json`. Each is used under its own licence.
