/*
 * JavaScript port of the pure discovery pipeline, for the in-browser demo.
 *
 * Source of truth is the Python package (api/mde): discovery/intent.py, discovery/rank.py, discovery/explain.py
 * and catalogue/memory.py. This file mirrors them function by function. api/tests/test_demo_parity.py runs both on
 * every benchmark query plus extra cases and requires identical output, so a change to one without the other
 * fails CI.
 */
"use strict";

const MDE = (() => {
  // ------------------------------------------------------------------ helpers mirroring Python semantics
  const W = "[\\p{L}\\p{N}_]"; // Python's Unicode \w

  function pyRound(x, digits = 0) {
    // Python's round(): decided on the exact binary value of x (toFixed(100) prints it exactly for the
    // magnitudes used here), with exact ties going to the even digit.
    if (!Number.isFinite(x) || x === 0) return x;
    const sign = x < 0 ? -1 : 1;
    const [intPart, frac] = Math.abs(x).toFixed(100).split(".");
    const kept = frac.slice(0, digits), rest = frac.slice(digits);
    const base = Number(digits ? `${intPart}.${kept}` : intPart);
    const lastDigit = Number((digits ? kept : intPart).slice(-1));
    let up;
    if (rest[0] > "5") up = true;
    else if (rest[0] < "5") up = false;
    else up = /[1-9]/.test(rest.slice(1)) || lastDigit % 2 === 1;
    const value = up ? Number((base + 10 ** -digits).toFixed(digits)) : base;
    return sign * value;
  }

  const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\\/]/g, "\\$&");
  const has = (obj, key) => Object.hasOwn(obj, key);

  function phraseRe(phrase, plural = false, flags = "gu") {
    const suffix = plural && /\p{L}$/u.test(phrase) ? "(?:s|es)?" : "";
    return new RegExp(`(?<!${W}|-)` + escapeRe(phrase) + suffix + `(?!${W}|-)`, flags);
  }
  const contains = (text, phrase) => phraseRe(phrase, false, "u").test(text);
  const sub = (re, repl, text) => text.replace(re, repl);
  const pyStrip = (s, chars) => {
    let a = 0, b = s.length;
    while (a < b && chars.includes(s[a])) a++;
    while (b > a && chars.includes(s[b - 1])) b--;
    return s.slice(a, b);
  };
  const pySplit = (s) => s.split(/\s+/).filter(Boolean);
  const capitalize = (s) => (s ? s[0].toUpperCase() + s.slice(1).toLowerCase() : s);
  const fmtG = (n) => String(Number(n)); // Python's :g for the values we format

  function slugify(text) {
    return text
      .normalize("NFKD")
      .replace(/[^\x00-\x7f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }
  const normaliseTitle = (t) => slugify(t).replace(/^(the|a|an)-/, "");

  // ------------------------------------------------------------------ taxonomy
  function parseTaxonomy(data) {
    const dimensions = {};
    for (const d of data.dimensions) dimensions[d.slug] = d;
    const terms = new Map();
    for (const raw of data.terms) {
      const key = `${raw.dimension}:${raw.slug}`;
      terms.set(key, {
        key, dimension: raw.dimension, slug: raw.slug, label: raw.label, definition: raw.definition,
        applies_to: raw.applies_to || ["*"], synonyms: (raw.synonyms || []).map((s) => s.toLowerCase()),
        group: raw.group ?? null,
      });
    }
    return {
      version: data.version, dimensions, terms,
      guideGroups: (data.guide_groups || []).map((g) => [g.slug, g.label]),
      get(key) {
        const t = terms.get(key);
        if (!t) throw new Error(`unknown taxonomy term ${key}`);
        return t;
      },
      inDimension: (dim) => [...terms.values()].filter((t) => t.dimension === dim),
    };
  }

  // ------------------------------------------------------------------ intent (mirrors intent.py)
  const MEDIUM_WORDS = {
    film: ["film", "films", "movie", "movies", "cinema", "flick"],
    book: ["book", "books", "novel", "novels", "novella", "novellas", "something to read", "a read", "reading"],
    game: ["game", "games", "video game", "video games", "videogame", "something to play", "to play", "gaming"],
    album: ["album", "albums", "record", "records", "music", "something to listen to", "listen to", "listening"],
    series: ["tv show", "tv series", "series", "show to watch"],
  };
  const WATCH_WORDS = ["to watch", "watch tonight", "something to watch", "watch"];
  const LANGUAGE_WORDS = {
    japanese: "ja", korean: "ko", french: "fr", german: "de", italian: "it", russian: "ru",
    polish: "pl", spanish: "es", english: "en", "english-language": "en", belarusian: "be",
  };
  const NON_ENGLISH = ["foreign language", "foreign-language", "non-english", "not in english", "subtitled",
    "world cinema", "international"];
  const NUMBER_WORDS = { a: 1, an: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6,
    ninety: 90, forty: 40, thirty: 30, twenty: 20, fifty: 50, sixty: 60 };
  const LENGTH_RE = new RegExp(
    "\\b(?<cue>under|less than|no more than|at most|max(?:imum)?(?: of)?|shorter than|within|up to|below|no longer than)\\s+" +
    "(?<num>\\d+(?:\\.\\d+)?|an?|one|two|three|four|five|six|twenty|thirty|forty|fifty|sixty|ninety)\\s*" +
    "(?<half>and a half\\s+)?(?<unit>hours?|hrs?|h|minutes?|mins?|m)\\b");
  const SOFT_CUES = ["ideally", "preferably", "if possible", "roughly", "around", "or so", "-ish", "ish",
    "would be nice", "would be great", "would be good", "if it can be", "not essential", "doesn't have to be", "bonus"];
  const HARD_CUES = ["must", "strictly", "has to be", "need it", "absolutely", "at most", "no more than", "no longer than"];
  const VAGUE_LENGTHS = {
    "one evening": { film: 150, game: 240, album: 90, book: 300 },
    "an evening": { film: 150, game: 240, album: 90, book: 300 },
    "one sitting": { film: 150, game: 240, album: 90, book: 240 },
    "short evening": { film: 110, game: 180, album: 60, book: 180 },
    "something short": { film: 100, game: 240, album: 45, book: 240 },
    short: { film: 100, game: 240, album: 45, book: 240 },
    quick: { film: 100, game: 180, album: 45, book: 180 },
    "bite-sized": { film: 60, game: 120, album: 30, book: 120 },
  };
  const OBSCURE_CUES = ["not something obvious", "not obvious", "nothing obvious", "underrated", "hidden gem",
    "hidden gems", "lesser-known", "lesser known", "overlooked", "obscure", "deep cut", "not mainstream",
    "everyone recommends", "haven't heard of", "off the beaten", "under the radar", "little-known",
    "little known", "not the usual"];
  const POPULAR_CUES = ["popular", "crowd-pleaser", "crowd pleaser", "blockbuster", "mainstream", "well-known",
    "well known", "everyone has seen", "must-see", "must see", "essential"];
  const REFERENCE_CUES = ["similar to", "something like", "anything like", "more like", "in the vein of",
    "reminds me of", "same vibe as", "same feeling as", "if i loved", "if i liked", "if you loved", "if you liked",
    "fans of", "fan of", "i loved", "i liked", "i enjoyed", "like"];
  const OTHER_MEDIUM_CUES = ["different medium", "another medium", "other medium", "not the same medium",
    "different format", "in another format", "but not a", "other than a"];
  const STRICT_NEGATION = ["no", "without", "avoid", "avoiding", "nothing", "zero", "free of", "none", "not",
    "don't want", "do not want", "skip", "never", "please no", "can't handle", "cannot handle", "hate"];
  const GENTLE_NEGATION = ["very little", "little", "minimal", "not too", "not overly", "not much", "light on",
    "low on", "not a lot of", "limited", "too much", "too many", "too"];
  const INTENSIFIERS = { very: 1.3, really: 1.3, deeply: 1.3, truly: 1.2, extremely: 1.4, "lots of": 1.3,
    strong: 1.3, ambitious: 1.2, real: 1.1, properly: 1.2 };
  const SOFTENERS = { "a bit": 0.6, slightly: 0.6, somewhat: 0.6, "a little": 0.6, "a touch of": 0.6, some: 0.8,
    maybe: 0.6, ideally: 0.8 };
  const STOPWORDS = new Set(`
a an the and or but if i me my we you your it its is are was be been being to of in on for with at by from as
that this these those something anything some any want wanted would like love loved need looking look find
give recommend recommendation please tonight evening today really very just about into than what which who
whom whose there their them they then so not no can could should might may maybe ideally want'd i'm im i've
ive also kind sort bit lot lots more most much one ones get got have has had do does did make makes made feel
feeling mood vibe something's thing things stuff good great nice after before questions question story
stories recommends recommend everyone people ambitious strong real deep lot`.split(/\s+/).filter(Boolean));
  const DECADE_RE = /\b(?:the\s+)?(?:(19|20)(\d)0s|'?(\d)0s)\b/;
  const BEFORE_RE = /\b(?:before|pre|older than|prior to)\s+((?:19|20)\d\d)\b/;
  const AFTER_RE = /\b(?:after|since|post|newer than|from)\s+((?:19|20)\d\d)\b/;
  const CURRENT_YEAR = 2026;
  const CLAUSE_SPLIT_RE = /[,.;!?]|\s(?:but|though|although|however|while)\s/;
  const byLenDesc = (arr) => [...arr].sort((a, b) => b.length - a.length);

  function newIntent(query) {
    return {
      query, media: [], excluded_media: [], preferences: [], avoid: [], length: null, languages: [],
      excluded_languages: [], year_min: null, year_max: null, year_hard: true, novelty: null,
      reference_phrase: null, reference_slug: null, reference_other_medium: false, keywords: [], notes: [],
    };
  }

  function createParser(tax, resolveTitle) {
    resolveTitle = resolveTitle || (() => null);
    const synonyms = [];
    for (const t of tax.terms.values()) for (const syn of t.synonyms) synonyms.push([syn, t.key, phraseRe(syn, true)]);
    synonyms.sort((a, b) => b[0].length - a[0].length);

    function extractReference(text, intent) {
      const quoted = text.match(/["“]([^"”]{2,80})["”]/);
      if (quoted) {
        const phrase = quoted[1].trim();
        const slug = resolveTitle(phrase);
        intent.reference_phrase = phrase;
        intent.reference_slug = slug;
        text = text.split(quoted[0]).join(" ");
        if (slug === null) intent.notes.push(`Couldn't find '${phrase}' in the catalogue.`);
      } else {
        outer: for (const cue of REFERENCE_CUES) {
          for (const m of text.matchAll(phraseRe(cue))) {
            const words = pySplit(text.slice(m.index + m[0].length)).slice(0, 8);
            for (let n = words.length; n > 0; n--) {
              const phrase = pyStrip(words.slice(0, n).join(" "), ",.;!?");
              const slug = resolveTitle(phrase);
              if (slug) {
                intent.reference_phrase = phrase;
                intent.reference_slug = slug;
                const span = new RegExp(escapeRe(cue) + "\\s+" + words.slice(0, n).map(escapeRe).join("\\s+"), "u");
                text = text.replace(span, " ");
                break outer;
              }
            }
          }
        }
      }
      if (intent.reference_slug) {
        intent.notes.push(`Using '${intent.reference_phrase}' as a reference point.`);
        if (OTHER_MEDIUM_CUES.some((c) => contains(text, c))) {
          intent.reference_other_medium = true;
          intent.notes.push("Looking in other media than the reference.");
          for (const c of OTHER_MEDIUM_CUES) text = sub(phraseRe(c), " ", text);
        }
      }
      return text;
    }

    function extractNovelty(text, intent) {
      for (const [cues, kind, note] of [[OBSCURE_CUES, "obscure", "favouring less widely known works."],
        [POPULAR_CUES, "popular", "favouring widely known works."]]) {
        for (const cue of cues) {
          if (contains(text, cue)) {
            intent.novelty = kind;
            intent.notes.push(`'${cue}': ${note}`);
            return sub(phraseRe(cue), " ", text);
          }
        }
      }
      return text;
    }

    function extractLength(text, intent) {
      const m = text.match(LENGTH_RE);
      if (m) {
        const raw = m.groups.num;
        let num = /^\d/.test(raw) ? parseFloat(raw) : NUMBER_WORDS[raw];
        if (m.groups.half) num += 0.5;
        const minutes = m.groups.unit.startsWith("h") ? num * 60 : num;
        const start = m.index, end = m.index + m[0].length;
        const window = text.slice(Math.max(0, start - 30), end + 25);
        let hard = !SOFT_CUES.some((c) => contains(window, c) || window.includes(c));
        if (HARD_CUES.some((c) => contains(window, c))) hard = true;
        const phrase = m[0].trim();
        intent.length = { max_minutes: pyRound(minutes), hard, phrase, per_medium: {} };
        const kind = hard ? "a firm limit" : "a preference, not a cut-off";
        intent.notes.push(`'${phrase}': treated as ${kind} (${pyRound(minutes)} min).`);
        text = text.slice(0, start) + " " + text.slice(end);
        for (const c of [...SOFT_CUES, ...HARD_CUES]) text = sub(phraseRe(c), " ", text);
        return text;
      }
      for (const [w, limits] of Object.entries(VAGUE_LENGTHS)) {
        if (contains(text, w)) {
          intent.length = { max_minutes: limits.film, hard: false, phrase: w, per_medium: { ...limits } };
          intent.notes.push(`'${w}': preferring roughly ${limits.film} min for films, ` +
            `${Math.floor(limits.game / 60)} hours for games, ${limits.album} min for albums.`);
          for (const other of Object.keys(VAGUE_LENGTHS)) text = sub(phraseRe(other), " ", text);
          return text;
        }
      }
      return text;
    }

    function extractMedia(text, intent) {
      const found = [], excluded = [];
      for (const [medium, words] of Object.entries(MEDIUM_WORDS)) {
        for (const w of byLenDesc(words)) {
          for (const m of [...text.matchAll(phraseRe(w))]) {
            const before = text.slice(Math.max(0, m.index - 16), m.index);
            if (/(not an?|no|other than an?|except|but not an?|anything but an?)\s*$/.test(before)) excluded.push(medium);
            else found.push(medium);
          }
          text = sub(phraseRe(w), " ", text);
        }
      }
      let media = found;
      if (!found.length && WATCH_WORDS.some((w) => contains(text, w))) {
        media = ["film", "series"];
        intent.notes.push("'watch': limiting to films and series.");
      }
      for (const w of WATCH_WORDS) text = sub(phraseRe(w), " ", text);
      for (const p of ["across any medium", "across all media", "across media", "any medium", "any format",
        "any media", "anything at all", "in any form", "any form"]) text = sub(phraseRe(p), " ", text);
      const ex = new Set(excluded);
      intent.media = [...new Set(media)].filter((m) => !ex.has(m)).sort();
      intent.excluded_media = [...ex].sort();
      return text;
    }

    function extractLanguage(text, intent) {
      for (const phrase of NON_ENGLISH) {
        if (contains(text, phrase)) {
          intent.excluded_languages = ["en"];
          intent.notes.push(`'${phrase}': excluding works originally in English.`);
          text = sub(phraseRe(phrase), " ", text);
        }
      }
      for (const [word, code] of Object.entries(LANGUAGE_WORDS)) {
        if (contains(text, word)) {
          intent.languages.push(code);
          text = sub(phraseRe(word), " ", text);
        }
      }
      if (intent.languages.length) intent.notes.push(`Original language: ${intent.languages.join(", ")}.`);
      return text;
    }

    function extractYears(text, intent) {
      let m = text.match(DECADE_RE);
      if (m) {
        let start;
        if (m[1]) start = parseInt(m[1] + m[2] + "0", 10);
        else {
          const d = parseInt(m[3], 10);
          start = d >= 3 ? 1900 + d * 10 : 2000 + d * 10;
        }
        intent.year_min = start;
        intent.year_max = start + 9;
        text = text.slice(0, m.index) + " " + text.slice(m.index + m[0].length);
      }
      if ((m = text.match(BEFORE_RE))) {
        intent.year_max = parseInt(m[1], 10) - 1;
        text = text.slice(0, m.index) + " " + text.slice(m.index + m[0].length);
      }
      if ((m = text.match(AFTER_RE))) {
        intent.year_min = parseInt(m[1], 10) + (m[0].startsWith("from") || m[0].includes("since") ? 0 : 1);
        text = text.slice(0, m.index) + " " + text.slice(m.index + m[0].length);
      }
      for (const w of ["recent", "newer", "latest"]) {
        if (contains(text, w) && intent.year_min === null) {
          intent.year_min = CURRENT_YEAR - 10;
          intent.year_hard = false;
          text = sub(phraseRe(w), " ", text);
        }
      }
      if (intent.year_min || intent.year_max) {
        intent.notes.push(`Release years: ${intent.year_min || "…"}–${intent.year_max || "…"}` +
          (intent.year_hard ? "" : " (preference)") + ".");
      }
      return text;
    }

    function negationIn(seg) {
      for (const cue of byLenDesc(GENTLE_NEGATION)) if (contains(seg, cue)) return [true, 0.6];
      for (const cue of byLenDesc(STRICT_NEGATION)) if (contains(seg, cue)) return [true, 0.4];
      return null;
    }

    function stripNegations(seg) {
      for (const cue of byLenDesc([...GENTLE_NEGATION, ...STRICT_NEGATION])) seg = sub(phraseRe(cue), " ", seg);
      return seg;
    }

    function extractTerms(text, intent) {
      const prefs = new Map(), avoids = new Map(), leftover = [];
      const weightWords = Object.entries({ ...INTENSIFIERS, ...SOFTENERS });
      for (let clause of text.split(CLAUSE_SPLIT_RE)) {
        clause = " " + clause + " ";
        // Work in UTF-16 indices like the regex engine; Python indexes code points. Queries are BMP text in
        // practice, so the two agree.
        const taken = new Array(clause.length).fill(false);
        const matches = [];
        for (const [syn, key, pattern] of synonyms) {
          pattern.lastIndex = 0;
          for (const m of clause.matchAll(pattern)) {
            const s = m.index, e = m.index + m[0].length;
            if (taken.slice(s, e).some(Boolean)) continue;
            for (let i = s; i < e; i++) taken[i] = true;
            matches.push([s, e, syn, key]);
          }
        }
        matches.sort((a, b) => a[0] - b[0] || a[1] - b[1] || (a[2] < b[2] ? -1 : a[2] > b[2] ? 1 : 0) ||
          (a[3] < b[3] ? -1 : a[3] > b[3] ? 1 : 0));
        let prevEnd = 0, prevNeg = null;
        for (const [start, end, syn, key] of matches) {
          const gap = " " + clause.slice(prevEnd, start) + " ";
          let negation = negationIn(gap);
          if (negation === null && prevNeg !== null && /^\s*(?:,|and|or|nor)\s*(?:(?:any|other)\s+)*$/.test(gap)) {
            negation = prevNeg;
          }
          if (negation !== null) {
            const [hard, threshold] = negation;
            const isHard = hard && key.startsWith("advisory:");
            const prev = avoids.get(key);
            if (!prev || (isHard && !prev.hard)) avoids.set(key, { term: key, hard: isHard, threshold, phrase: syn });
          } else {
            let weight = 1.0;
            for (const [word, w] of weightWords) {
              if (new RegExp(`(?<!${W}|-)` + escapeRe(word) + `\\s+(?:(?:${W}|-)+\\s+)?$`, "u").test(gap)) {
                weight = w;
                break;
              }
            }
            if (key.startsWith("genre:")) weight *= 1.2;
            if (!prefs.has(key) || prefs.get(key).weight < weight) {
              prefs.set(key, { term: key, weight: pyRound(weight, 2), phrase: syn });
            }
          }
          prevEnd = end;
          prevNeg = negation;
        }
        let remaining = "";
        for (let i = 0; i < clause.length; i++) remaining += taken[i] ? " " : clause[i];
        leftover.push(stripNegations(remaining));
      }
      for (const key of avoids.keys()) prefs.delete(key);
      intent.preferences = [...prefs.values()];
      intent.avoid = [...avoids.values()];
      for (const a of intent.avoid) {
        const label = tax.get(a.term).label.toLowerCase();
        intent.notes.push(a.hard ? `Excluding works with notable ${label} (intensity ≥ ${a.threshold}).`
          : `Ranking down works that are ${label}.`);
      }
      return leftover.join(" ");
    }

    return {
      name: "rules-v1",
      parse(query) {
        const intent = newIntent(query);
        let text = " " + query.toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim() + " ";
        text = extractReference(text, intent);
        text = extractNovelty(text, intent);
        text = extractLength(text, intent);
        text = extractMedia(text, intent);
        text = extractLanguage(text, intent);
        text = extractYears(text, intent);
        text = extractTerms(text, intent);
        intent.keywords = [...text.matchAll(/[a-z][a-z-]{2,}(?!')/g)].map((m) => m[0])
          .filter((w) => !STOPWORDS.has(w) && !has(INTENSIFIERS, w));
        if (intent.keywords.length) {
          intent.notes.push(`Also searching titles and descriptions for: ${intent.keywords.join(", ")}.`);
        }
        return intent;
      },
    };
  }

  // ------------------------------------------------------------------ rank (mirrors rank.py)
  const RANKER_VERSION = "transparent-v1";
  const WEIGHTS = {
    reference_weight_alone: 1.0, reference_weight_with_prefs: 0.7, keyword_weight_alone: 1.0,
    keyword_weight_with_others: 0.25, relation_boost: 0.2, obscure_bonus: 0.15, popular_bonus: 0.1,
    soft_avoid_penalty: 0.3, near_threshold_penalty: 0.15, unknown_advisory_penalty: 0.08,
    over_length_penalty_per_hour: 0.25, max_over_length_penalty: 0.3, unknown_length_penalty: 0.06,
    out_of_era_penalty: 0.1, min_relevance: 0.12, same_medium_diversity: 0.04, same_creator_diversity: 0.08,
    match_threshold: 0.4,
  };

  const lengthMinutes = (w) =>
    w.runtime_minutes !== null ? w.runtime_minutes : w.playtime_hours !== null ? pyRound(w.playtime_hours * 60) : null;
  const forMedium = (length, medium) => (has(length.per_medium, medium) ? length.per_medium[medium] : length.max_minutes);

  function lengthLabel(w) {
    const approx = w.length_is_estimate ? "about " : "";
    if (w.runtime_minutes !== null) return `${approx}${w.runtime_minutes} min`;
    if (w.playtime_hours !== null) return `${approx}${fmtG(w.playtime_hours)} hours to finish`;
    return "length unknown";
  }

  function hardExclusion(intent, w, ref) {
    if (intent.media.length && !intent.media.includes(w.medium)) return "different medium";
    if (intent.excluded_media.includes(w.medium)) return "excluded medium";
    if (ref && intent.reference_other_medium && w.medium === ref.medium) return "same medium as the reference";
    if (intent.languages.length && !intent.languages.includes(w.language)) return "different original language";
    if (intent.excluded_languages.length && intent.excluded_languages.includes(w.language)) return "excluded original language";
    if (intent.year_hard && w.year !== null) {
      if (intent.year_min && w.year < intent.year_min) return "outside the requested years";
      if (intent.year_max && w.year > intent.year_max) return "outside the requested years";
    }
    for (const a of intent.avoid) {
      if (a.hard && w.terms.has(a.term) && w.terms.get(a.term).strength >= a.threshold) return "content you asked to avoid";
    }
    const len = lengthMinutes(w);
    if (intent.length && intent.length.hard && len !== null && len > forMedium(intent.length, w.medium)) {
      return "longer than your limit";
    }
    return null;
  }

  function score(intent, w, ref, refVec, kwScores) {
    const s = { work: w, score: 0, relevance: 0, breakdown: {}, matched: [], unmatched: [], relation: null,
      caveats: [], constraint_notes: [] };
    const components = [];

    if (intent.preferences.length) {
      const total = intent.preferences.reduce((a, p) => a + p.weight, 0);
      let got = 0.0;
      for (const p of intent.preferences) {
        const ev = w.terms.get(p.term);
        if (ev && ev.strength > 0) {
          got += p.weight * ev.strength * (0.5 + 0.5 * ev.confidence);
          if (ev.strength >= WEIGHTS.match_threshold) {
            s.matched.push({ term: p.term, weight: p.weight, strength: ev.strength, confidence: ev.confidence,
              is_interpretation: ev.is_interpretation, review_status: ev.review_status, source: "request" });
          } else s.unmatched.push(p.term);
        } else s.unmatched.push(p.term);
      }
      const explicit = got / total;
      s.breakdown.request_match = pyRound(explicit, 3);
      components.push([explicit, 1.0]);
    }

    if (ref) {
      const vec = [...refVec].filter(([k]) => w.medium === ref.medium || !k.startsWith("genre:"));
      const denom = vec.reduce((a, [, v]) => a + v, 0) || 1.0;
      let shared = 0.0;
      for (const [k, rv] of vec) {
        const ev = w.terms.get(k);
        if (ev && ev.strength >= WEIGHTS.match_threshold) {
          shared += Math.min(rv, ev.strength);
          if (!s.matched.some((m) => m.term === k)) {
            s.matched.push({ term: k, weight: rv, strength: ev.strength, confidence: ev.confidence,
              is_interpretation: ev.is_interpretation, review_status: ev.review_status, source: "reference" });
          }
        }
      }
      const similarity = shared / denom;
      s.breakdown.reference_similarity = pyRound(similarity, 3);
      components.push([similarity, intent.preferences.length ? WEIGHTS.reference_weight_with_prefs : WEIGHTS.reference_weight_alone]);
      const rel = w.relations.find((r) => r.other_slug === ref.slug);
      if (rel) {
        s.relation = rel;
        s.breakdown.relationship = pyRound(WEIGHTS.relation_boost * rel.confidence, 3);
      }
    }

    if (intent.keywords.length) {
      const kw = has(kwScores, w.slug) ? kwScores[w.slug] : 0.0;
      s.breakdown.keyword_match = pyRound(kw, 3);
      const others = intent.preferences.length > 0 || !!ref;
      components.push([kw, others ? WEIGHTS.keyword_weight_with_others : WEIGHTS.keyword_weight_alone]);
    }

    s.relevance = components.length
      ? components.reduce((a, [v, wt]) => a + v * wt, 0) / components.reduce((a, [, wt]) => a + wt, 0)
      : 0.5;
    let penalty = 0.0;

    for (const a of intent.avoid) {
      const ev = w.terms.get(a.term);
      if (!ev) {
        if (a.hard) {
          if (a.term.startsWith("advisory:")) {
            s.caveats.push(`Not yet assessed for ${a.term.split(":")[1].replace(/-/g, " ")}.`);
          }
          penalty += WEIGHTS.unknown_advisory_penalty;
        }
        continue;
      }
      if (a.hard) {
        if (ev.strength >= 0.2) penalty += WEIGHTS.near_threshold_penalty * ev.strength;
      } else if (ev.strength >= a.threshold * 0.5) {
        penalty += WEIGHTS.soft_avoid_penalty * ev.strength;
      }
    }
    if (intent.avoid.length) s.breakdown.avoid_penalty = pyRound(-penalty, 3);

    if (intent.length) {
      const limit = forMedium(intent.length, w.medium);
      const length = lengthMinutes(w);
      if (length === null) {
        const p = WEIGHTS.unknown_length_penalty * (intent.length.hard ? 2 : 1);
        penalty += p;
        s.breakdown.length_penalty = pyRound(-p, 3);
        s.caveats.push(w.medium !== "book" ? "Length isn't recorded, so it couldn't be checked against your limit."
          : "Reading length isn't tracked yet.");
      } else if (length <= limit) {
        s.constraint_notes.push(`${lengthLabel(w)}: fits your ${limit}-minute limit.`);
      } else {
        const over = length - limit;
        const p = Math.min(WEIGHTS.max_over_length_penalty, (WEIGHTS.over_length_penalty_per_hour * over) / 60);
        penalty += p;
        s.breakdown.length_penalty = pyRound(-p, 3);
        s.caveats.push(`${lengthLabel(w)}: ${over} min over your preferred ${limit}.`);
      }
    }

    if (!intent.year_hard && w.year !== null && intent.year_min && w.year < intent.year_min) {
      penalty += WEIGHTS.out_of_era_penalty;
    }

    let novelty = 0.0;
    const tier = w.popularity_tier;
    if (tier !== null && intent.novelty === "obscure") novelty = (WEIGHTS.obscure_bonus * (tier - 1)) / 3;
    else if (tier !== null && intent.novelty === "popular") novelty = (WEIGHTS.popular_bonus * (4 - tier)) / 3;
    if (novelty) s.breakdown.novelty = pyRound(novelty, 3);

    s.score = pyRound(s.relevance + (s.breakdown.relationship || 0.0) + novelty - penalty, 4);
    s.breakdown.relevance = pyRound(s.relevance, 3);
    s.breakdown.total = s.score;
    return s;
  }

  function diversify(ranked, intent, limit) {
    const pool = ranked.slice(0, limit * 3);
    const chosen = [];
    const media = {}, creators = {};
    while (pool.length && chosen.length < limit) {
      const adjusted = (c) => {
        let adj = c.score;
        if (!intent.media.length) adj -= WEIGHTS.same_medium_diversity * (media[c.work.medium] || 0);
        adj -= WEIGHTS.same_creator_diversity * c.work.creators.reduce((a, n) => a + (creators[n] || 0), 0);
        return adj;
      };
      let best = 0;
      for (let i = 1; i < pool.length; i++) if (adjusted(pool[i]) > adjusted(pool[best])) best = i;
      const [b] = pool.splice(best, 1);
      chosen.push(b);
      media[b.work.medium] = (media[b.work.medium] || 0) + 1;
      for (const n of b.work.creators) creators[n] = (creators[n] || 0) + 1;
    }
    return chosen;
  }

  function rank(intent, works, kwScores, limit) {
    const bySlug = new Map(works.map((w) => [w.slug, w]));
    const ref = intent.reference_slug ? bySlug.get(intent.reference_slug) || null : null;
    const refVec = ref ? [...ref.terms].filter(([k, ev]) => !k.startsWith("advisory:") && ev.strength >= 0.4)
      .map(([k, ev]) => [k, ev.strength]) : [];
    const excluded = {};
    const candidates = [];
    for (const w of works) {
      if (ref && w.slug === ref.slug) continue;
      const reason = hardExclusion(intent, w, ref);
      if (reason) {
        excluded[reason] = (excluded[reason] || 0) + 1;
        continue;
      }
      candidates.push(score(intent, w, ref, refVec, kwScores));
    }
    const hasSignal = intent.preferences.length > 0 || !!ref || intent.keywords.length > 0;
    const weak = new Set(candidates.filter((c) => c.relation === null && hasSignal && (
      c.relevance < WEIGHTS.min_relevance ||
      (intent.preferences.length && !ref && (c.breakdown.request_match || 0) < 0.05))));
    const kept = candidates.filter((c) => !weak.has(c));
    kept.sort((a, b) => b.score - a.score || (a.work.title < b.work.title ? -1 : a.work.title > b.work.title ? 1 : 0));
    return { results: diversify(kept, intent, limit), considered: works.length, excluded, weak_dropped: weak.size, reference: ref };
  }

  // ------------------------------------------------------------------ explain (mirrors explain.py)
  const DIMENSION_ORDER = ["genre", "theme", "mood", "complexity", "narrative", "world", "style", "pacing"];
  const degree = (s) => (s >= 0.8 ? "strongly" : s >= 0.55 ? "clearly" : "partly");
  const basis = (interp, status) => (!interp ? "catalogue" : status !== "reviewed" ? "interpretation" : "reviewed_interpretation");
  const upperFirst = (s) => s[0].toUpperCase() + s.slice(1);

  function lengthText(w) {
    const approx = w.length_is_estimate ? "~" : "";
    if (w.runtime_minutes) return `${approx}${w.runtime_minutes} min`;
    if (w.playtime_hours) return `${approx}${fmtG(w.playtime_hours)} h`;
    return null;
  }

  function headline(s, tax) {
    const top = [...s.matched].sort((a, b) => b.strength * b.weight - a.strength * a.weight)
      .filter((m) => !m.term.startsWith("genre:")).slice(0, 3);
    if (s.relation && s.relation.factual) {
      const lead = `${upperFirst(s.relation.label)} ${s.relation.other_title}`;
      return top.length ? lead + "; " + top.map((m) => tax.get(m.term).label.toLowerCase()).join(", ") + "." : lead + ".";
    }
    if (!top.length) return s.breakdown.keyword_match ? "Matches your search terms." : "A broad match for your request.";
    const labels = top.map((m) => tax.get(m.term).label.toLowerCase());
    if (labels.length === 1) return `${capitalize(labels[0])}.`;
    return `${capitalize(labels.slice(0, -1).join(", "))} and ${labels[labels.length - 1]}.`;
  }

  function explain(s, tax) {
    const w = s.work;
    const reasons = [];
    if (s.relation) {
      const r = s.relation;
      let text = `${upperFirst(r.label)} ${r.other_title}`;
      if (r.note) text += `: ${r.note}`;
      reasons.push({ kind: "relationship", text, basis: r.factual ? "catalogue" : "interpretation", confidence: r.confidence });
    }
    const dimIdx = (m) => {
      const i = DIMENSION_ORDER.indexOf(m.term.split(":")[0]);
      return i === -1 ? 99 : i;
    };
    const matched = [...s.matched].sort((a, b) => dimIdx(a) - dimIdx(b) || b.strength - a.strength);
    for (const m of matched) {
      const term = tax.get(m.term);
      const dim = tax.dimensions[term.dimension].label;
      const via = m.source === "request" ? "you asked for" : "shared with your reference";
      reasons.push({ kind: "match", text: `${dim}: ${degree(m.strength)} ${term.label.toLowerCase()} (${via})`,
        term: m.term, definition: term.definition, strength: m.strength, confidence: m.confidence,
        basis: basis(m.is_interpretation, m.review_status) });
    }
    for (const note of s.constraint_notes) reasons.push({ kind: "constraint", text: note, basis: "catalogue" });
    if (has(s.breakdown, "novelty") && w.popularity_tier && w.popularity_tier >= 3) {
      reasons.push({ kind: "novelty", text: "Less widely known, by our editorial popularity estimate.", basis: "interpretation" });
    }
    const caveats = [...s.caveats];
    if (s.unmatched.length) {
      caveats.push(`Not a match for: ${s.unmatched.map((t) => tax.get(t).label.toLowerCase()).join(", ")}.`);
    }
    return {
      slug: w.slug, title: w.title, original_title: w.original_title, medium: w.medium, year: w.year,
      creators: w.creators, length: lengthText(w), summary: w.summary, headline: headline(s, tax),
      reasons, caveats, score: s.score, score_breakdown: s.breakdown,
    };
  }

  // ------------------------------------------------------------------ in-memory catalogue (mirrors memory.py)
  const RELATIONSHIP_TYPES = {
    adaptation_of: ["is an adaptation of", "was adapted as", true],
    sequel_of: ["is a sequel to", "is followed by", true],
    remake_of: ["is a remake of", "was remade as", true],
    same_universe: ["shares a fictional universe with", "shares a fictional universe with", true],
    same_creator: ["shares a creator with", "shares a creator with", true],
    influenced_by: ["was influenced by", "influenced", false],
    thematic_kin: ["explores similar questions to", "explores similar questions to", false],
    similar_experience: ["offers a similar experience to", "offers a similar experience to", false],
    contrasting_take: ["offers a contrasting take on the themes of", "offers a contrasting take on the themes of", false],
  };
  const PRIMARY_ROLES = ["director", "author", "developer", "artist"];
  const ORGANISATION_ROLES = ["developer", "publisher", "studio", "label", "distributor"];

  function parseAdvisory(value) {
    if (Array.isArray(value)) return [Number(value[0]), value.length > 1 ? value[1] : null, value.length > 2 ? value[2] : null];
    return [Number(value), null, null];
  }

  function severity(level) {
    if (level <= 0) return "None";
    if (level < 0.45) return "Mild";
    if (level < 0.75) return "Moderate";
    return "Severe";
  }

  // ------------------------------------------------------------------ catalogue views (mirrors browse.py)
  const TAG_DIMENSIONS = ["genre", "theme", "mood", "pacing", "complexity", "narrative", "world", "style"];
  const TAG_THRESHOLD = 0.4;
  const SUITABLE_BELOW = 0.45;

  function cmp(a, b) {
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return 1;
    }
    return 0;
  }
  const strengthOf = (w, key) => (w.terms.has(key) ? w.terms.get(key).strength : 0.0);
  const decadeOf = (year) => Math.floor(year / 10) * 10;
  const lengthMinutesOf = (w) =>
    w.runtime_minutes !== null ? w.runtime_minutes : w.playtime_hours !== null ? pyRound(w.playtime_hours * 60) : null;

  function tagsOf(w, dimensions) {
    const found = [...w.terms].filter(([k, ev]) => dimensions.includes(k.split(":")[0]) && ev.strength >= TAG_THRESHOLD)
      .map(([k, ev]) => [k, ev.strength]);
    return found.sort((a, b) => cmp([-a[1], a[0]], [-b[1], b[0]]));
  }

  function createViews(tax) {
    const basisOf = (interp, status) => (!interp ? "catalogue" : status !== "reviewed" ? "interpretation" : "reviewed_interpretation");

    function guideFlags(w) {
      const flags = [];
      for (const [group, label] of tax.guideGroups) {
        const levels = [...w.terms].filter(([k]) => k.startsWith("advisory:") && tax.get(k).group === group).map(([, ev]) => ev.strength);
        if (levels.length && Math.max(...levels) >= SUITABLE_BELOW) flags.push({ group, label, severity: severity(Math.max(...levels)) });
      }
      return flags;
    }

    function card(w) {
      return {
        slug: w.slug, title: w.title, original_title: w.original_title, medium: w.medium, year: w.year,
        length: lengthText(w), creators: w.creators, summary: w.summary,
        genres: tagsOf(w, ["genre"]).map(([k]) => ({ key: k, label: tax.get(k).label })),
        tags: tagsOf(w, TAG_DIMENSIONS.slice(1)).slice(0, 4).map(([k]) => ({ key: k, label: tax.get(k).label })),
        ratings: w.ratings.map((r) => ({ system: r.system, rating: r.rating })),
        guide_flags: guideFlags(w),
      };
    }

    function matches(w, f) {
      if (f.media.length && !f.media.includes(w.medium)) return false;
      if (f.tags.some((t) => strengthOf(w, t) < TAG_THRESHOLD)) return false;
      if (f.decade !== null && (w.year === null || decadeOf(w.year) !== f.decade)) return false;
      if (f.language && w.language !== f.language) return false;
      if (f.country && !w.countries.includes(f.country)) return false;
      const len = lengthMinutesOf(w);
      if (f.max_minutes !== null && (len === null || len > f.max_minutes)) return false;
      for (const key of f.avoid) {
        if (!w.terms.has(key) || w.terms.get(key).strength >= SUITABLE_BELOW) return false;
      }
      if (f.q) {
        const needle = f.q.trim().toLowerCase();
        const haystack = [w.title, w.original_title || "", ...w.credits.map((c) => c.name)];
        if (!haystack.some((h) => h.toLowerCase().includes(needle))) return false;
      }
      return true;
    }

    function sortKey(w, f) {
      const title = normaliseTitle(w.title);
      if (f.sort === "title") return [title];
      if (f.sort === "newest") return [-(w.year || 0), title];
      if (f.sort === "oldest") return [w.year || 9999, title];
      if (f.sort === "shortest") {
        const len = lengthMinutesOf(w);
        return [len !== null ? len : 10 ** 9, title];
      }
      if (f.tags.length) return [-pyRound(f.tags.reduce((a, t) => a + strengthOf(w, t), 0), 6), w.popularity_tier || 5, title];
      return [w.popularity_tier || 5, title];
    }

    function facet(counts, label) {
      return [...counts].map(([value, count]) => ({ value, label: label(value), count }))
        .sort((a, b) => cmp([-a.count, String(a.label)], [-b.count, String(b.label)]));
    }
    const bump = (m, k) => m.set(k, (m.get(k) || 0) + 1);

    function browse(works, filters) {
      const f = { media: [], tags: [], decade: null, language: null, country: null, max_minutes: null, avoid: [], q: "",
        sort: "popular", ...filters };
      const hits = works.filter((w) => matches(w, f)).sort((a, b) => cmp(sortKey(a, f), sortKey(b, f)));
      const media = new Map(), decades = new Map(), languages = new Map();
      const byDim = { genre: new Map(), theme: new Map(), mood: new Map() };
      for (const w of hits) {
        bump(media, w.medium);
        if (w.year !== null) bump(decades, decadeOf(w.year));
        if (w.language) bump(languages, w.language);
        for (const [k] of tagsOf(w, Object.keys(byDim))) bump(byDim[k.split(":")[0]], k);
      }
      const facets = {
        medium: facet(media, (v) => v),
        decade: [...decades].map(([d, n]) => ({ value: d, label: `${d}s`, count: n })).sort((a, b) => b.value - a.value),
        language: facet(languages, (v) => v),
      };
      for (const [d, c] of Object.entries(byDim)) facets[d] = facet(c, (v) => tax.get(v).label).slice(0, 12);
      return { total: hits.length, results: hits.map(card), facets };
    }

    function tagIndex(works) {
      const counts = new Map();
      for (const w of works) for (const [k] of tagsOf(w, TAG_DIMENSIONS)) bump(counts, k);
      const out = [];
      for (const d of TAG_DIMENSIONS) {
        const terms = tax.inDimension(d).filter((t) => counts.get(t.key))
          .map((t) => ({ key: t.key, label: t.label, count: counts.get(t.key) }))
          .sort((a, b) => cmp([-a.count, a.label], [-b.count, b.label]));
        if (terms.length) out.push({ dimension: d, label: tax.dimensions[d].label, terms });
      }
      return out;
    }

    function tagPage(works, key) {
      if (!tax.terms.has(key)) return null;
      const term = tax.get(key);
      const tagged = works.filter((w) => strengthOf(w, key) >= TAG_THRESHOLD)
        .sort((a, b) => cmp([-strengthOf(a, key), normaliseTitle(a.title)], [-strengthOf(b, key), normaliseTitle(b.title)]));
      const related = new Map();
      for (const w of tagged) for (const [k] of tagsOf(w, TAG_DIMENSIONS)) if (k !== key) bump(related, k);
      return {
        key, label: term.label, definition: term.definition, dimension: term.dimension,
        dimension_label: tax.dimensions[term.dimension].label, applies_to: [...term.applies_to],
        works: tagged.map((w) => ({ ...card(w), strength: strengthOf(w, key) })),
        related: [...related].sort((a, b) => cmp([-a[1], tax.get(a[0]).label], [-b[1], tax.get(b[0]).label])).slice(0, 10)
          .map(([k, n]) => ({ key: k, label: tax.get(k).label, count: n })),
      };
    }

    function peopleIndex(works) {
      const people = new Map();
      for (const w of works) {
        for (const c of w.credits) {
          const slug = slugify(c.name);
          if (!people.has(slug)) people.set(slug, { slug, name: c.name, kind: c.kind, roles: [], count: 0, _works: new Set() });
          const p = people.get(slug);
          if (!p.roles.includes(c.role)) p.roles.push(c.role);
          p._works.add(w.slug);
        }
      }
      const out = [...people.values()].map(({ _works, ...p }) => ({ ...p, count: _works.size, roles: [...p.roles].sort() }));
      return out.sort((a, b) => cmp([-a.count, a.name], [-b.count, b.name]));
    }

    function personPage(works, slug) {
      const credited = [];
      let name = null, kind = null;
      for (const w of works) {
        const roles = w.credits.filter((c) => slugify(c.name) === slug).map((c) => c.role);
        if (roles.length) {
          const c = w.credits.find((x) => slugify(x.name) === slug);
          name = c.name;
          kind = c.kind;
          credited.push([w, roles]);
        }
      }
      if (!credited.length) return null;
      credited.sort((a, b) => cmp([-(a[0].year || 0), normaliseTitle(a[0].title)], [-(b[0].year || 0), normaliseTitle(b[0].title)]));
      const roles = [...new Set(credited.flatMap(([, rs]) => rs))].sort();
      const themes = new Map();
      for (const [w] of credited) for (const [k] of tagsOf(w, ["theme", "mood"])) bump(themes, k);
      return {
        slug, name, kind, roles,
        works: credited.map(([w, rs]) => ({ ...card(w), roles: rs })),
        recurring_tags: [...themes].sort((a, b) => cmp([-a[1], tax.get(a[0]).label], [-b[1], tax.get(b[0]).label]))
          .filter(([, n]) => n > 1).slice(0, 8).map(([k, n]) => ({ key: k, label: tax.get(k).label, count: n })),
      };
    }

    function parentsGuide(w) {
      const groups = [];
      for (const [group, label] of tax.guideGroups) {
        const items = tax.inDimension("advisory").filter((t) => t.group === group).map((t) => {
          const ev = w.terms.get(t.key);
          return {
            key: t.key, label: t.label, definition: t.definition, assessed: !!ev,
            level: ev ? ev.strength : null, severity: ev ? severity(ev.strength) : "Not assessed",
            note: ev ? ev.note ?? null : null, spoiler_note: ev ? ev.spoiler_note ?? null : null,
            basis: ev ? basisOf(ev.is_interpretation, ev.review_status) : null,
          };
        });
        const assessed = items.filter((i) => i.assessed);
        groups.push({
          slug: group, label,
          severity: assessed.length ? severity(Math.max(...assessed.map((i) => i.level))) : "Not assessed",
          partial: assessed.length > 0 && assessed.length < items.length,
          items,
        });
      }
      return {
        ratings: w.ratings.map((r) => ({ system: r.system, rating: r.rating, reason: r.reason })),
        assessed: groups.some((g) => g.severity !== "Not assessed"),
        groups,
      };
    }

    function workPage(w, works) {
      const bySlug = new Map(works.map((x) => [x.slug, x]));
      const tags = [];
      for (const d of TAG_DIMENSIONS) {
        const terms = [...w.terms].filter(([k, ev]) => k.split(":")[0] === d && ev.strength > 0)
          .map(([k, ev]) => ({ key: k, label: tax.get(k).label, definition: tax.get(k).definition, strength: ev.strength,
            confidence: ev.confidence, basis: basisOf(ev.is_interpretation, ev.review_status) }))
          .sort((a, b) => cmp([-a.strength, a.key], [-b.strength, b.key]));
        if (terms.length) tags.push({ dimension: d, label: tax.dimensions[d].label, terms });
      }
      const relationships = w.relations.map((r) => ({ label: r.label, type: r.type, factual: r.factual, slug: r.other_slug,
        title: r.other_title, medium: r.other_medium, year: bySlug.has(r.other_slug) ? bySlug.get(r.other_slug).year : null,
        note: r.note, confidence: r.confidence }))
        .sort((a, b) => cmp([a.factual ? 0 : 1, -a.confidence, a.title], [b.factual ? 0 : 1, -b.confidence, b.title]));
      return {
        slug: w.slug, medium: w.medium, title: w.title, original_title: w.original_title,
        original_language: w.language, countries: w.countries, year: w.year, summary: w.summary,
        length: lengthText(w), runtime_minutes: w.runtime_minutes, playtime_hours: w.playtime_hours,
        length_is_estimate: w.length_is_estimate, popularity_tier: w.popularity_tier, attributes: w.attributes,
        credits: w.credits.map((c) => ({ role: c.role, name: c.name, kind: c.kind, slug: slugify(c.name) })),
        tags, parents_guide: parentsGuide(w), relationships,
      };
    }

    return { browse, tagIndex, tagPage, peopleIndex, personPage, workPage };
  }

  function stem(word) {
    for (const suffix of ["ing", "es", "ed", "s"]) {
      if (word.length > suffix.length + 3 && word.endsWith(suffix)) return word.slice(0, -suffix.length);
    }
    return word;
  }
  const words = (text) => new Set(((text || "").toLowerCase().match(/[a-z0-9]+/g) || []).map(stem));

  function createCatalogue(data, taxonomyData) {
    const tax = parseTaxonomy(taxonomyData);
    const d = { genre_confidence: 0.9, term_confidence: 0.7, advisory_confidence: 0.75, ...(data.defaults || {}) };
    const works = new Map();
    for (const w of data.works) {
      const terms = new Map();
      for (const [key, strength] of Object.entries(w.terms || {})) {
        const conf = key.startsWith("genre:") ? d.genre_confidence : d.term_confidence;
        terms.set(key, { strength, confidence: conf, origin: "ai_assisted", review_status: "unreviewed", is_interpretation: true });
      }
      for (const [slug, value] of Object.entries(w.advisories || {})) {
        const [level, note, spoiler] = parseAdvisory(value);
        terms.set(`advisory:${slug}`, { strength: level, confidence: d.advisory_confidence, origin: "ai_assisted",
          review_status: "unreviewed", is_interpretation: true, note, spoiler_note: spoiler });
      }
      works.set(w.slug, {
        id: w.slug, slug: w.slug, medium: w.medium, title: w.title, original_title: w.original_title ?? null,
        year: w.year ?? null, language: w.language ?? null, countries: w.countries || [], summary: w.summary ?? null,
        runtime_minutes: w.runtime_minutes ?? null, playtime_hours: w.playtime_hours ?? null,
        length_is_estimate: !!w.length_is_estimate, popularity_tier: w.popularity_tier ?? null,
        advisories_assessed: Object.keys(w.advisories || {}).length > 0,
        creators: (w.credits || []).filter((c) => PRIMARY_ROLES.includes(c[0])).map((c) => c[1]),
        terms, relations: [],
        credits: (w.credits || []).map((c) => ({ role: c[0], name: c[1],
          kind: c.length === 3 ? c[2] : ORGANISATION_ROLES.includes(c[0]) ? "organisation" : "person" })),
        ratings: (w.ratings || []).map(([system, rating, reason]) => ({ system, rating, reason })),
        attributes: w.attributes || {},
      });
    }
    for (const [aSlug, type, bSlug, note, confidence] of data.relationships || []) {
      const [label, inverse, factual] = RELATIONSHIP_TYPES[type];
      const origin = factual ? "editorial" : "ai_assisted";
      const a = works.get(aSlug), b = works.get(bSlug);
      a.relations.push({ other_slug: b.slug, other_title: b.title, other_medium: b.medium, type, label, note, confidence, origin, factual });
      b.relations.push({ other_slug: a.slug, other_title: a.title, other_medium: a.medium, type, label: inverse, note, confidence, origin, factual });
    }
    const list = [...works.values()];
    const titles = new Map(list.map((w) => [w.slug, new Set([w.title, w.original_title].filter(Boolean).map(normaliseTitle))]));
    const index = new Map(list.map((w) => [w.slug, [words(`${w.title} ${w.original_title || ""}`), words(w.summary)]]));

    function keywordScores(keywords) {
      const stems = new Set(keywords.map((k) => stem(k.toLowerCase())));
      const raw = {};
      let top = 0;
      for (const [slug, [title, summary]] of index) {
        let n = 0;
        for (const s of stems) n += (title.has(s) ? 2 : 0) + (summary.has(s) ? 1 : 0);
        raw[slug] = n;
        top = Math.max(top, n);
      }
      if (!top) return {};
      const out = {};
      for (const [slug, n] of Object.entries(raw)) if (n) out[slug] = n / top;
      return out;
    }

    function resolveTitle(phrase) {
      const target = normaliseTitle(phrase);
      const hits = list.filter((w) => target && titles.get(w.slug).has(target));
      if (!hits.length) return null;
      let best = hits[0];
      for (const h of hits) if ((h.popularity_tier || 5) < (best.popularity_tier || 5)) best = h;
      return best.slug;
    }

    const parser = createParser(tax, resolveTitle);

    function discover(query, limit = 8) {
      const intent = parser.parse(query);
      const ranked = rank(intent, list, keywordScores(intent.keywords), limit);
      const ref = ranked.reference;
      const results = ranked.results.map((s) => explain(s, tax));
      return {
        event_id: null, interpretation: intent, results, excluded: ranked.excluded,
        weak_matches_hidden: ranked.weak_dropped, considered: ranked.considered,
        reference: ref ? { slug: ref.slug, title: ref.title, medium: ref.medium } : null,
        parser: parser.name, ranker: RANKER_VERSION,
        message: results.length ? null : "Nothing in the catalogue matches this well enough to recommend. The pilot " +
          "catalogue is small; try describing the experience you want rather than a specific subject.",
      };
    }

    const views = createViews(tax);
    const work = (slug) => (works.has(slug) ? views.workPage(works.get(slug), list) : null);
    return {
      discover, work, works: list, taxonomy: tax,
      browse: (filters) => views.browse(list, filters || {}),
      tags: () => views.tagIndex(list),
      tag: (key) => views.tagPage(list, key),
      people: () => views.peopleIndex(list),
      person: (slug) => views.personPage(list, slug),
    };
  }

  return { createCatalogue };
})();

if (typeof module !== "undefined" && module.exports) module.exports = MDE;
