# Taxonomy and classification specification (v0.1.0)

The taxonomy is the product's core intellectual asset. It lives in
[`api/mde/taxonomy/taxonomy.json`](../api/mde/taxonomy/taxonomy.json) and is synced into `taxonomy_dimension` and
`taxonomy_term` on every import.

## Rules

1. **Controlled.** A classification may reference only a defined term. The importer rejects unknown terms, and
   free-form tags are not stored.
2. **Defined.** Every term has a one-sentence definition, applicable media (`*` = all), and synonyms. Synonyms
   double as the intent parser's lexicon, and one phrase may map to only one term (enforced at load time).
3. **Independent dimensions.** A work is classified separately on each dimension, so "comforting" and
   "melancholic" can both be high without contradiction.
4. **Graded.** `strength` ∈ [0, 1] says how strongly a term applies:

   | Strength | Meaning | Shown as |
   | --- | --- | --- |
   | 0.8–1.0 | defining characteristic | strong |
   | 0.55–0.8 | clearly present | clear |
   | 0.4–0.55 | present but secondary | partial |
   | < 0.4 | trace; never presented as a match | slight |

5. **Confidence is separate from strength.** `confidence` says how sure we are of the claim. The ranker
   moderates each term's contribution by `0.5 + 0.5 × confidence`.
6. **Origin and review are recorded.** `origin` (source / editorial / ai_assisted / community / derived),
   `is_interpretation`, `review_status` (unreviewed / reviewed / disputed / rejected), `source_id`,
   `taxonomy_version`. Rejected classifications are kept for audit but ignored by ranking and display.
7. **Spoilers.** `is_spoiler` classifications are excluded from discovery and hidden on work pages by default.
8. **Missing stays missing.** No row means not assessed. For advisories (below), "assessed and absent" is an
   explicit 0.
9. **Versioned.** Terms are never deleted. A term removed from the file is marked `deprecated` and stops
   influencing ranking. Changing a definition substantively means a new term, not an edit.

## Dimensions

| Dimension | Kind | Purpose | Example terms |
| --- | --- | --- | --- |
| `genre` | categorical | Conventional labels for filtering, deliberately not the main signal | science-fiction, mystery, rpg, metroidvania, ambient, post-rock |
| `theme` | graded | What the work substantively engages with | language-communication, grief-loss, consciousness-ai, surveillance-authoritarianism, decay-impermanence |
| `mood` | graded | The felt experience | contemplative, melancholic, comforting, eerie, wonder, exhilarating |
| `pacing` | graded | Patience asked of the audience | slow-burn, brisk |
| `complexity` | graded | Attention and interpretation required | intellectually-demanding, accessible |
| `narrative` | graded | Structure and storytelling devices | nonlinear, time-loop, unreliable-narrator, puzzle-box, environmental-storytelling, meaningful-choices |
| `world` | graded | Setting and world-building | rich-worldbuilding, grounded-realism, space-setting, mythic |
| `style` | graded | Visual, sonic, prose or interactive craft | atmospheric, visually-striking, hand-drawn, minimalist, lyrical-prose |
| `advisory` | intensity | Content people may want to avoid | graphic-violence, body-horror, sexual-content, atrocity, jump-scares |

**Advisory intensity scale:** 0 = assessed and absent · ~0.3 = mild or brief · ~0.6 = notable · ~0.9 = graphic
or central. The parser maps "no X" to a hard exclusion at ≥ 0.4, and "very little / not too much X" to a hard
exclusion at ≥ 0.6 plus a ranking penalty from 0.2.

## How classifications are made

**Pilot (now):** AI-assisted drafts, all `unreviewed`, labelled "Interpretation" in the UI.

**Target workflow:**

1. Facts come from licensed or open sources (see [`SOURCES.md`](SOURCES.md)).
2. An LLM drafts classifications from permitted material: our own synopsis, licensed descriptions, and
   editorial notes. It is given the term definitions and must return only taxonomy keys, a strength, and a
   short evidence note.
3. An editor reviews each work's draft: accept, adjust strength, or reject. Reviewed claims are labelled
   "Reviewed".
4. Disagreement between drafts and reviews is tracked per term to find vague definitions. Terms with high
   adjustment rates get rewritten.

## Planned extensions

Not every requested axis needs a term on day one. Proposed for v0.2, prioritised by benchmark failures:
narrative continuity (standalone / requires prior entries / entry point to a series), production scale (studio /
independent / solo), visual technique (live action / stop-motion / CG / pixel art), audience (all ages / young
adult / adult), emotional intensity, humour type, cultural context, historical period, and setting geography.
