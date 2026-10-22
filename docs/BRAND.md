# Mimir: brand guide

**Mimir · A Terratales Venture.** This guide extends the *Terratales Brand Guidelines, Volume II* and the
*Strategic Foundation, Volume I*. Where they speak, they win: Mimir takes colour, type, voice and the
endorsement rules from them and adds only what a product needs.

## 1. Name and position

**Mimir** (pronounced *MEE-meer*). In Norse myth, Mímir kept a well among the roots of Yggdrasil, and whoever
drank from it understood. Volume I calls Yggdrasil's roots "the wellspring of story". Mimir is that well: the
place in the Terratales tree where every story can be found and drawn up.

- **What it is:** a catalogue and discovery engine for films, books, games and music. You describe how you
  want to feel and it finds what fits, with the reasons for every pick.
- **Where it sits:** a Tier-2 *endorsed venture* (Vol. II §14), like Akashic Records. It has its own product
  identity, signed "A Terratales Venture". Volume I §12 places catalogues in product surfaces rather than the
  corporate site, so Mimir lives at its own address (`mimir.terratalesmedia.world`) and is linked from the main
  site.
- **Who it serves:** the Seekers (16–34, mobile-first, fluent across story-worlds) and the Fandom (Vol. II §04).
- **Tagline:** *Drawn from the well of every story.*
- **Eyebrow / descriptor:** *The well beneath the tree.*

Before public launch, run a trademark search. "Grafana Mimir" is an existing software product, in an
unrelated category (observability).

## 2. The mark

A single gold line in a thin circle, drawn in the same language as the realm icons (Vol. II §12:
single-weight gold line, rounded joins, circular node framing).

| Element | Meaning |
| --- | --- |
| Horizon with end ticks | Borrowed from the seal: the threshold between the rooted and the seen |
| Leaf above the horizon | A story in motion, leaving the tree |
| Five roots | The tree's roots reaching down below the horizon |
| Ripples | Mímir's well, which the roots drink from |

The Terratales seal is never redrawn or recoloured (Vol. II §08). Mimir has its own mark, and the seal appears
only in the endorsement lockup.

### Files (`brand/`)

| File | Use |
| --- | --- |
| `mark.svg` | Gold on dark, for screens up to about 120px |
| `mark-large.svg` | Same drawing with a finer line, for hero and print sizes (keeps the 1.5–2px look) |
| `mark-ink.svg` | Brand black on parchment |
| `favicon.svg`, `favicon-32.png` | Simplified mark on a black disc, for tabs; below 40px the full drawing closes up |
| `app-icon.svg`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` | Home-screen and PWA icons |
| `lockup-horizontal.svg` | Mark + MIMIR + "A TERRATALES VENTURE": headers, documents |
| `lockup-horizontal-ink.svg` | The same on parchment |
| `lockup-stacked.svg` | Mark over wordmark: covers, splash, title cards |
| `wordmark.svg` | MIMIR alone, Cinzel SemiBold, 0.12em tracking, as outlines |
| `og-image.png` | 1200×630 social card |
| `terratales-seal-64.png`, `-128.png` | The Terratales seal, downsized from terratalesmedia.world, for the endorsement only |

**Clear space:** at least the height of the ripples' outer ellipse on every side. **Minimum size:** full mark
24px; below that, use the favicon drawing.

**Don't:** fill the mark, add a second colour, put it on mid-tones or photographs without a dark scrim, set it
in gold on white, or reflow the wordmark in another typeface.

## 3. Colour

The family palette, unchanged (Vol. II §09). Night grounds the page, gold is structure, and parchment carries
text: **60 · 30 · 10**.

| Token | Hex | Mimir use |
| --- | --- | --- |
| Brand black | `#131315` | Page ground |
| Surface | `#1A1813` | Inputs, notices |
| Bone | `#EDE3CC` | Headlines, titles |
| Ink | `#E7DECB` | Body text |
| Cream | `#D8C084` | Secondary text, endorsement descriptor |
| Gold bright | `#D8B24A` | Links, the mark, buttons, active states |
| Yggdrasil gold | `#C0902F` | Eyebrows (large or letter-spaced text only) |
| Gold deep | `#8A6A18` | Bar gradients |
| Muted / faint | `#9A8E72` / `#6E685C` | Supporting text, metadata |
| Hairline | `rgba(216,192,132,.16)` | Dividers. Rules divide; boxes are rare |

**Product semantics (Mimir only):** the parents' guide needs severity colours. They stay warm, inside the
lamplight palette, and always come with a label, never colour alone. None `#8FA58A`, Mild `#D8C084`, Moderate
`#E0A04A`, Severe `#E07A5F`, Not assessed in faint with a dashed dot.

Dark is the only colourway on screen. Use parchment for print and documents.

## 4. Typography

| Voice | Face | Mimir use |
| --- | --- | --- |
| Display | Cinzel 500–600 | The wordmark, eyebrows (12px, 0.34em), facet and fact labels (9.5–10.5px, 0.28–0.3em), result numerals (I, II, III). Caps only. |
| Headings | Cormorant Garamond 500, italics | Page and work titles, section heads, the italic "headline" that says why a pick fits |
| Body / UI | Inter 300–600 | Everything functional: text, controls, navigation, notes |
| Data | JetBrains Mono 400–500 | Metadata lines, counts, ratings badges, score breakdowns, basis labels |

One Cinzel moment per view (the eyebrow); body text at 60–75 characters; line height 1.6–1.7.

## 5. Voice

The product UI follows Vol. II §11: **"Friendly, simple. A guide who gets out of your way."** Mythic in the
framing (the well, *seek*, *drawn from*), plain in every instruction.

- Explain choices in ordinary words: "Not a match for: rich world-building."
- Say what isn't known: "Not assessed" is a first-class answer, never hidden.
- Empty states and errors are a steady hand: "Nothing in the catalogue matches this well enough to recommend."
- Lean in: *stories, works, seek, draw, thread, well, roots.* Avoid: *content*, hype, ALL-CAPS shouting, occult
  jargon that hides meaning.

Key lines:
- Hero: *Drawn from the well of every story.* / *Describe a feeling, an idea, a favourite or a time limit.
  Mimir finds the films, books, games and music that fit, and tells you why each one does.*
- Action: **Seek**
- Reading panel: *How Mimir read you*

## 6. Interface patterns

- **Medium medallions:** film, book, game and album icons, each in a thin gold circle (single weight, 1.3px
  at 22px).
- **Basis labels:** *Catalogue* (solid hairline) for recorded facts; *Interpretation* (dashed gold) for
  editorial readings. Every reason and tag carries one.
- **Strength bars:** 3px, deep-to-bright gold gradient on a faint track.
- **Ratings:** monospaced outline badge (`PG-13`, `M`), never a colour fill.
- **The well:** the only motion is the hero ripples, a slow 9-second cycle that stays still for reduced motion.

## 7. Endorsement

Per Vol. II §14: the Terratales seal at 24px or more (Mimir uses 32px), with **A TERRATALES VENTURE** in Cinzel
600 and 0.28em tracking, in cream. It appears in the footer of every page and on the About page, links to
terratalesmedia.world, and is never larger than Mimir's own mark. The header lockup carries the same
descriptor under the wordmark.
