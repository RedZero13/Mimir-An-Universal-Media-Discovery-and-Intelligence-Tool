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

  // Compiled once per phrase: the parser checks ~700 synonyms per query. Global regexes are only used with
  // replace() and matchAll(), which don't carry lastIndex between calls.
  const phraseCache = new Map();
  function phraseRe(phrase, plural = false, flags = "gu") {
    const key = `${flags}|${plural ? 1 : 0}|${phrase}`;
    if (!phraseCache.has(key)) {
      const suffix = plural && /\p{L}$/u.test(phrase) ? "(?:s|es)?" : "";
      phraseCache.set(key, new RegExp(`(?<!${W}|-)` + escapeRe(phrase) + suffix + `(?!${W}|-)`, flags));
    }
    return phraseCache.get(key);
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

  // Memoised: titles and names are slugified for every card the page draws.
  const slugCache = new Map();
  function slugify(text) {
    let slug = slugCache.get(text);
    if (slug === undefined) {
      slug = text
        .normalize("NFKD")
        .replace(/[^\x00-\x7f]/g, "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      slugCache.set(text, slug);
    }
    return slug;
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
    online_video: ["youtube video", "youtube videos", "a youtube", "on youtube", "video essay", "video essays", "a video"],
    channel: ["youtuber", "youtubers", "youtube channel", "youtube channels"],
    series: ["tv show", "tv shows", "tv series", "series", "show to watch", "miniseries", "mini-series", "limited series",
      "web series", "k-drama", "k-dramas", "kdrama", "kdramas", "to binge", "binge-watch", "binge watch",
      "something to binge", "a show", "the show", "shows", "a tv", "on tv", "an anime", "anime series", "a sitcom", "a drama series", "episodes"],
  };
  const WATCH_WORDS = ["to watch", "watch tonight", "something to watch", "watch"];
  const LANGUAGE_WORDS = {
    japanese: "ja", korean: "ko", french: "fr", german: "de", italian: "it", russian: "ru",
    polish: "pl", spanish: "es", english: "en", "english-language": "en", belarusian: "be", finnish: "fi",
    hindi: "hi", tamil: "ta", telugu: "te", malayalam: "ml", bengali: "bn", kannada: "kn",
    marathi: "mr", punjabi: "pa", urdu: "ur", mandarin: "zh", chinese: "zh", cantonese: "yue",
    portuguese: "pt", swedish: "sv", danish: "da", norwegian: "no", persian: "fa", farsi: "fa",
    arabic: "ar", icelandic: "is", indonesian: "id", dutch: "nl", hebrew: "he",
  };
  const LANGUAGE_HINTS = {
    "k-pop": "ko", kpop: "ko", "k-drama": "ko", kdrama: "ko", "k-dramas": "ko", kdramas: "ko",
    "j-pop": "ja", anime: "ja", manga: "ja", bollywood: "hi", tollywood: "te", kollywood: "ta",
    mollywood: "ml",
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
    "a weekend": { film: 300, game: 900, album: 180, book: 900, series: 900 },
    "one weekend": { film: 300, game: 900, album: 180, book: 900, series: 900 },
    "one evening": { film: 150, game: 240, album: 90, book: 300, series: 180 },
    "an evening": { film: 150, game: 240, album: 90, book: 300, series: 180 },
    "one sitting": { film: 150, game: 240, album: 90, book: 240, series: 150 },
    "short evening": { film: 110, game: 180, album: 60, book: 180, series: 120 },
    "something short": { film: 100, game: 240, album: 45, book: 240, series: 300 },
    short: { film: 100, game: 240, album: 45, book: 240, series: 300 },
    quick: { film: 100, game: 180, album: 45, book: 180, series: 240 },
    "bite-sized": { film: 60, game: 120, album: 30, book: 120, series: 120 },
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
stories recommends recommend everyone people ambitious strong real deep lot
finish finished binge binged through will watching reading playing listening start show shows`.split(/\s+/).filter(Boolean));
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
    // Built on the first query rather than at start-up: compiling ~700 regexes is the page's costliest set-up step.
    let synonymList = null;
    const synonymsOf = () => {
      if (!synonymList) {
        synonymList = [];
        for (const t of tax.terms.values()) for (const syn of t.synonyms) synonymList.push([syn, t.key, phraseRe(syn, true)]);
        synonymList.sort((a, b) => b[0].length - a[0].length);
      }
      return synonymList;
    };

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
      const original = " " + intent.query.toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim() + " ";
      for (const [word, code] of Object.entries(LANGUAGE_HINTS)) {
        if (contains(original, word) && !intent.languages.includes(code)) intent.languages.push(code);
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
        for (const [syn, key, pattern] of synonymsOf()) {
          if (!clause.includes(syn)) continue;   // cheap pre-check: a match needs the literal phrase
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
    w.runtime_minutes !== null ? w.runtime_minutes : w.playtime_hours !== null ? pyRound(w.playtime_hours * 60) : seriesMinutes(w);
  const forMedium = (length, medium) => (has(length.per_medium, medium) ? length.per_medium[medium] : length.max_minutes);

  function lengthLabel(w) {
    const approx = w.length_is_estimate ? "about " : "";
    if (w.runtime_minutes !== null) return `${approx}${w.runtime_minutes} min`;
    if (w.playtime_hours !== null) return `${approx}${fmtG(w.playtime_hours)} hours to finish`;
    if (seriesMinutes(w) !== null) return `${w.attributes.episodes} episodes of about ${fmtG(w.attributes.episode_minutes)} min`;
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

  const SIMILARITY_WEIGHTS = { theme: 1.0, mood: 0.9, narrative: 0.8, world: 0.8, style: 0.7, pacing: 0.6, genre: 0.5, complexity: 0.4 };

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
      const simWeight = (k) => { const d = k.split(":")[0]; return has(SIMILARITY_WEIGHTS, d) ? SIMILARITY_WEIGHTS[d] : 1.0; };
      const denom = vec.reduce((a, [k, v]) => a + v * simWeight(k), 0) || 1.0;
      let shared = 0.0;
      for (const [k, rv] of vec) {
        const ev = w.terms.get(k);
        if (ev && ev.strength >= WEIGHTS.match_threshold) {
          shared += Math.min(rv, ev.strength) * simWeight(k);
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
    kept.sort((a, b) => b.score - a.score || (a.work.popularity_tier || 5) - (b.work.popularity_tier || 5)
      || (a.work.title < b.work.title ? -1 : a.work.title > b.work.title ? 1 : 0));
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
    return seriesLengthText(w);
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
    track_of: ["is a track on", "includes the track", true],
    remix_of: ["is a remix of", "was remixed as", true],
    spin_off_of: ["is a spin-off of", "spun off", true],
    soundtrack_of: ["is the soundtrack of", "has the soundtrack", true],
  };
  const PRIMARY_ROLES = ["director", "creator", "author", "developer", "artist"];
  const isInt = (v) => typeof v === "number" && Number.isInteger(v);
  function seriesMinutes(w) {
    if (w.medium !== "series") return null;
    const eps = w.attributes.episodes, mins = w.attributes.episode_minutes;
    return isInt(eps) && typeof mins === "number" ? pyRound(eps * mins) : null;
  }
  function seriesLengthText(w) {
    if (w.medium !== "series" || !isInt(w.attributes.episodes)) return null;
    const seasons = w.attributes.seasons, eps = w.attributes.episodes;
    return isInt(seasons) ? `${seasons} season${seasons === 1 ? "" : "s"}, ${eps} ep` : `${eps} ep`;
  }
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

  // ------------------------------------------------------------------ enrichment merge (mirrors enrich.py)
  const SOURCE_ORDER = ["wikidata", "openlibrary", "musicbrainz", "tmdb", "publisher", "youtube"];
  const IMAGE_PREFERENCE = { poster: 0, cover: 1, still: 2, logo: 3 };
  const LINK_ORDER = ["listen:spotify", "listen:youtube-music", "watch:youtube", "watch:justwatch", "buy:steam", "buy:amazon", "info:publisher", "reactions:letterboxd",
    "reactions:rotten-tomatoes", "reactions:metacritic", "reactions:goodreads", "reactions:storygraph",
    "reactions:reddit", "reactions:youtube", "info:imdb", "info:openlibrary", "info:musicbrainz", "info:wikipedia"];
  const rankIn = (order, item) => (order.includes(item) ? order.indexOf(item) : order.length);
  const FACT_ATTR = { release_year: "year", runtime_minutes: "runtime_minutes", page_count: "page_count" };

  function editorialGroups(w) {
    const out = [];
    const series = w.attributes.series;
    if (series) {
      const pos = w.attributes.series_position;
      out.push({ slug: slugify(series), name: series, kind: "series", position: pos !== undefined && pos !== null ? String(pos) : null, source: "editorial" });
    }
    // Franchises (James Bond, Middle-earth, the MCU…): umbrella groups a work belongs to alongside its series.
    for (const name of w.attributes.franchises || []) {
      if (!out.some((g) => g.slug === slugify(name))) out.push({ slug: slugify(name), name, kind: "franchise", position: null, source: "editorial" });
    }
    return out;
  }

  function setFact(w, field, value, source) {
    const attr = FACT_ATTR[field];
    const current = w[attr];
    if (has(w.fact_sources, field)) w.fact_sources[field] = { source, seed: w.fact_sources[field].seed };
    else if (current !== value) w.fact_sources[field] = { source, seed: current };
    w[attr] = value;
  }

  function normaliseOrder(w) {
    const src = (s) => rankIn(["editorial", ...SOURCE_ORDER], s);
    const pref = (k) => (has(IMAGE_PREFERENCE, k) ? IMAGE_PREFERENCE[k] : 9);
    w.images.sort((a, b) => cmp([pref(a.kind), src(a.source)], [pref(b.kind), src(b.source)]));
    w.scores.sort((a, b) => cmp([src(a.source), a.publisher, a.metric], [src(b.source), b.publisher, b.metric]));
    w.box_office.sort((a, b) => cmp([src(a.source), -a.amount], [src(b.source), -b.amount]));
    w.groups.sort((a, b) => cmp([src(a.source), a.slug], [src(b.source), b.slug]));
    w.links.sort((a, b) => cmp([rankIn(LINK_ORDER, a.kind), a.kind], [rankIn(LINK_ORDER, b.kind), b.kind]));
  }

  function applyEnrichment(works, enrichment) {
    const bySlug = new Map(works.map((w) => [w.slug, w]));
    for (const w of works) w.groups.push(...editorialGroups(w));
    for (const source of SOURCE_ORDER) {
      const data = enrichment[source];
      if (!data) continue;
      for (const [slug, rec] of Object.entries(data.works || {})) {
        const w = bySlug.get(slug);
        if (!w || !rec.match) {
          if (w && rec.links && rec.links.length) w.links = rec.links.map((l) => ({ ...l }));
          continue;
        }
        for (const [field, value] of Object.entries(rec.facts || {})) {
          if (has(FACT_ATTR, field) && value !== null) setFact(w, field, value, source);
        }
        for (const img of rec.images || []) {
          if (!img.url) continue;
          w.images = w.images.filter((i) => !(i.kind === img.kind && i.source === source));
          w.images.push({ kind: img.kind, url: img.url, source, licence: has(img, "licence") ? img.licence : "see source",
            attribution: has(img, "attribution") ? img.attribution : null });
        }
        for (const sc of rec.scores || []) {
          if (/^Q\d+$/.test(sc.publisher)) continue;   // a publisher Wikidata couldn't name (mirrors enrich.py)
          w.scores.push({ publisher: sc.publisher, metric: sc.metric, value: Number(sc.value), scale_max: Number(sc.scale_max),
            votes: has(sc, "votes") ? sc.votes : null, as_of: has(sc, "as_of") ? sc.as_of : null, source });
        }
        for (const b of rec.box_office || []) w.box_office.push({ ...b, source });
        for (const g of rec.series || []) {
          const gslug = slugify(g.name);
          if (!w.groups.some((x) => x.slug === gslug)) w.groups.push({ slug: gslug, name: g.name, kind: "series", position: has(g, "position") ? g.position : null, source });
        }
        Object.assign(w.ids, rec.ids || {});
        if (rec.links && rec.links.length) w.links = rec.links.map((l) => ({ ...l }));
        if (rec.tracks && rec.tracks.length) w.tracks = rec.tracks.map((t) => ({ ...t }));
        if (source === "openlibrary" && rec.key && !has(w.ids, "openlibrary")) w.ids.openlibrary = rec.key.split("/").pop();
        if (source === "musicbrainz" && rec.match.mbid && !has(w.ids, "musicbrainz_release_group")) w.ids.musicbrainz_release_group = rec.match.mbid;
      }
    }
    for (const w of works) normaliseOrder(w);
    return works;
  }

  // ------------------------------------------------------------------ catalogue views (mirrors browse.py)
  const TAG_DIMENSIONS = ["genre", "theme", "mood", "pacing", "complexity", "narrative", "world", "style"];
  const TAG_THRESHOLD = 0.4;
  const SUITABLE_BELOW = 0.45;
  const TIME_BUCKETS = [[45, "quick-bite", "Quick bite"], [150, "one-sitting", "One sitting"],
    [360, "evening-or-two", "An evening or two"], [900, "weekend", "A weekend"], [2400, "season", "A season"]];
  const LONG_HAUL = ["long-haul", "A long haul"];
  const READING_MINUTES_PER_PAGE = 1.7;
  const NOVELLA_MINUTES = 150;
  const CHAIN_TYPES = ["sequel_of", "spin_off_of", "same_universe", "remake_of"];
  // Python's urllib.parse.quote(s, safe=""): encodeURIComponent plus !'()*
  const pyQuote = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
  const spotifySearch = (...parts) => "https://open.spotify.com/search/" + pyQuote(parts.filter(Boolean).join(" "));

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
    w.runtime_minutes !== null ? w.runtime_minutes : w.playtime_hours !== null ? pyRound(w.playtime_hours * 60) : seriesMinutes(w);

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
      if (f.exclude.some((t) => strengthOf(w, t) >= TAG_THRESHOLD)) return false;
      if (f.year_min !== null && (w.year === null || w.year < f.year_min)) return false;
      if (f.year_max !== null && (w.year === null || w.year > f.year_max)) return false;
      if (f.language && w.language !== f.language) return false;
      if (f.country && !w.countries.includes(f.country)) return false;
      const len = lengthMinutesOf(w);
      if (f.max_minutes !== null && (len === null || len > f.max_minutes)) return false;
      for (const key of f.avoid) {
        if (!w.terms.has(key) || w.terms.get(key).strength >= SUITABLE_BELOW) return false;
      }
      if (f.q) {
        const needle = f.q.trim().toLowerCase();
        const haystack = [w.title, w.original_title || "", ...w.credits.map((c) => c.name), ...w.groups.map((g) => g.name)];
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
        exclude: [], year_min: null, year_max: null, sort: "popular", ...filters };
      // Each key once, then sort (stable, so the order is exactly that of sorting on the keys directly).
      const hits = works.filter((w) => matches(w, f)).map((w) => [sortKey(w, f), w]).sort((a, b) => cmp(a[0], b[0])).map((x) => x[1]);
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
      const ctx = context(works);
      return { total: hits.length, results: hits.map((w) => richCard(w, ctx)), facets };
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
      const ctx = context(works);
      const tagged = works.filter((w) => strengthOf(w, key) >= TAG_THRESHOLD)
        .sort((a, b) => cmp([-strengthOf(a, key), normaliseTitle(a.title)], [-strengthOf(b, key), normaliseTitle(b.title)]));
      const related = new Map();
      for (const w of tagged) for (const [k] of tagsOf(w, TAG_DIMENSIONS)) if (k !== key) bump(related, k);
      return {
        key, label: term.label, definition: term.definition, dimension: term.dimension,
        dimension_label: tax.dimensions[term.dimension].label, applies_to: [...term.applies_to],
        works: tagged.map((w) => ({ ...richCard(w, ctx), strength: strengthOf(w, key) })),
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
      const ctx = context(works);
      const roles = [...new Set(credited.flatMap(([, rs]) => rs))].sort();
      const themes = new Map();
      for (const [w] of credited) for (const [k] of tagsOf(w, ["theme", "mood"])) bump(themes, k);
      return {
        slug, name, kind, roles,
        works: credited.map(([w, rs]) => ({ ...richCard(w, ctx), roles: rs })),
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
      const bySlug = slugIndex(works);   // cached per list: building it per page made a full pass O(n²)
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
        page_count: w.page_count, length_is_estimate: w.length_is_estimate, popularity_tier: w.popularity_tier,
        attributes: w.attributes,
        credits: w.credits.map((c) => ({ role: c.role, name: c.name, kind: c.kind, slug: slugify(c.name) })),
        tags, parents_guide: parentsGuide(w), relationships,
        time: timeInvestment(w),
        continuity: continuity(w, works),
        images: w.images.map((i) => ({ kind: i.kind, url: i.url, source: i.source, licence: i.licence, attribution: i.attribution })),
        scores: w.scores.map((s) => ({ publisher: s.publisher, metric: s.metric, value: s.value, scale_max: s.scale_max,
          votes: s.votes, as_of: s.as_of, source: s.source })),
        box_office: w.box_office.map((b) => ({ ...b })),
        links: w.links.map((l) => ({ ...l })),
        tracks: w.medium === "album" ? trackItems(w) : [],
        spotify: w.medium === "album" ? spotifySearch(w.creators.length ? w.creators[0] : "", w.title) : null,
        fact_sources: Object.fromEntries(Object.entries(w.fact_sources).map(([k, v]) => [k, { ...v }])),
        ids: { ...w.ids },
      };
    }

    // ---------------------------------------------------------------- time, continuity, shelves, music
    function timeInvestment(w) {
      let minutes, basis, estimate;
      if (w.runtime_minutes) [minutes, basis, estimate] = [w.runtime_minutes, "runtime", w.length_is_estimate];
      else if (w.playtime_hours) [minutes, basis, estimate] = [lengthMinutesOf(w), "playtime", w.length_is_estimate];
      else if (w.medium === "series" && lengthMinutesOf(w)) [minutes, basis, estimate] = [lengthMinutesOf(w), "episodes", true];
      else if (w.medium === "book" && w.page_count) [minutes, basis, estimate] = [pyRound(w.page_count * READING_MINUTES_PER_PAGE), "pages", true];
      else if (w.medium === "book" && w.attributes.form === "novella") [minutes, basis, estimate] = [NOVELLA_MINUTES, "form", true];
      else return null;
      let [bucket, label] = LONG_HAUL;
      for (const [limit, slug, name] of TIME_BUCKETS) {
        if (minutes <= limit) { [bucket, label] = [slug, name]; break; }
      }
      return { minutes, bucket, label, estimate, basis };
    }

    const isForward = (r) => r.label === RELATIONSHIP_TYPES[r.type][0];
    const positionKey = (p) => (p !== null && p !== undefined && /^\s*[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?\s*$/.test(p) ? Number(p) : 1e9);

    // Lookups shared by every continuity() call on the same list (otherwise each card would rescan the catalogue).
    const slugIndexCache = new WeakMap(), groupIndexCache = new WeakMap();
    const slugIndex = (works) => {
      if (!slugIndexCache.has(works)) slugIndexCache.set(works, new Map(works.map((x) => [x.slug, x])));
      return slugIndexCache.get(works);
    };
    const groupIndex = (works) => {
      if (!groupIndexCache.has(works)) {
        const idx = new Map();
        for (const x of works) for (const slug of new Set(x.groups.map((xg) => xg.slug))) (idx.get(slug) || idx.set(slug, []).get(slug)).push(x);
        groupIndexCache.set(works, idx);
      }
      return groupIndexCache.get(works);
    };

    function continuity(w, works) {
      const bySlug = slugIndex(works);
      const ref = (r) => ({ slug: r.other_slug, title: r.other_title, medium: r.other_medium });
      const out = { kind: "standalone", group: null, position: null, members: [],
        adapted_from: w.relations.filter((r) => r.type === "adaptation_of" && isForward(r)).map(ref),
        adapted_as: w.relations.filter((r) => r.type === "adaptation_of" && !isForward(r)).map(ref) };
      let series = null;
      if (w.groups.length) {
        const g = w.groups[0];
        const members = (groupIndex(works).get(g.slug) || []).slice();
        const pos = new Map(members.map((x) => [x.slug, x.groups.find((xg) => xg.slug === g.slug).position]));
        members.sort((a, b) => cmp([positionKey(pos.get(a.slug)), a.year || 9999, normaliseTitle(a.title)],
          [positionKey(pos.get(b.slug)), b.year || 9999, normaliseTitle(b.title)]));
        series = { kind: g.kind, group: { slug: g.slug, name: g.name }, position: g.position,
          members: members.map((x) => ({ slug: x.slug, title: x.title, year: x.year, medium: x.medium, position: pos.get(x.slug) })) };
        if (members.length > 1) return Object.assign(out, series);
      }
      const seen = new Set([w.slug]);
      const queue = [w.slug];
      while (queue.length) {
        const cur = bySlug.get(queue.pop());
        for (const r of cur ? cur.relations : []) {
          if (CHAIN_TYPES.includes(r.type) && !seen.has(r.other_slug) && bySlug.has(r.other_slug)) {
            seen.add(r.other_slug);
            queue.push(r.other_slug);
          }
        }
      }
      if (seen.size > 1) {
        const members = [...seen].map((s) => bySlug.get(s))
          .sort((a, b) => cmp([a.year || 9999, normaliseTitle(a.title)], [b.year || 9999, normaliseTitle(b.title)]));
        const root = members[0];
        Object.assign(out, { kind: "franchise", group: { slug: `franchise-${root.slug}`, name: root.title },
          members: members.map((x) => ({ slug: x.slug, title: x.title, year: x.year, medium: x.medium, position: null })) });
      } else if (series) Object.assign(out, series);
      return out;
    }

    // The catalogue doesn't change while the page is open, so each list's continuity is worked out once.
    const contextCache = new WeakMap();
    const context = (works) => {
      if (!contextCache.has(works)) contextCache.set(works, new Map(works.map((w) => [w.slug, continuity(w, works)])));
      return contextCache.get(works);
    };

    // Cards depend only on the work and its list's continuity context, so each is built once per context;
    // callers get a shallow copy, so adding fields to one never leaks into another view.
    const cardCache = new WeakMap();
    function richCard(w, ctx) {
      if (!cardCache.has(ctx)) cardCache.set(ctx, new Map());
      const cache = cardCache.get(ctx);
      if (!cache.has(w.slug)) cache.set(w.slug, buildRichCard(w, ctx));
      return { ...cache.get(w.slug) };
    }
    function buildRichCard(w, ctx) {
      // Only real artwork becomes a cover (mirrors browse.py COVER_KINDS).
      const img = w.images.find((i) => i.kind === "cover" || i.kind === "poster") || null;
      const c = ctx.get(w.slug);
      return { ...card(w),
        image: img ? { url: img.url, kind: img.kind, licence: img.licence, attribution: img.attribution, source: img.source } : null,
        time: timeInvestment(w),
        continuity: { kind: c.kind, group: c.group, position: c.position, count: c.members.length },
        scores: w.scores.map((s) => ({ publisher: s.publisher, metric: s.metric, value: s.value, scale_max: s.scale_max })) };
    }

    function shelfMatch(w, rule, ctx) {
      if (rule.media && rule.media.length && !rule.media.includes(w.medium)) return false;
      if (rule.languages && rule.languages.length && !rule.languages.includes(w.language)) return false;
      if (rule.not_languages && rule.not_languages.length && rule.not_languages.includes(w.language)) return false;
      if (rule.forms && rule.forms.length && !rule.forms.includes((w.attributes || {}).form)) return false;
      const floor = has(rule, "min_strength") ? rule.min_strength : 0.5;
      if (rule.all_tags && rule.all_tags.length && rule.all_tags.some((t) => strengthOf(w, t) < floor)) return false;
      if (rule.any_tags && rule.any_tags.length && rule.any_tags.every((t) => strengthOf(w, t) < floor)) return false;
      const tier = w.popularity_tier;
      if (has(rule, "popularity_min") && (tier === null || tier < rule.popularity_min)) return false;
      if (has(rule, "popularity_max") && (tier === null || tier > rule.popularity_max)) return false;
      if (rule.relation_child && rule.relation_child.length && !w.relations.some((r) => rule.relation_child.includes(r.type) && isForward(r))) return false;
      if (rule.continuity && rule.continuity.length && !rule.continuity.includes(ctx.get(w.slug).kind)) return false;
      if (has(rule, "score_max")) {
        // Mean of every score, out of 100; works with no score never qualify.
        const vals = w.scores.filter((s) => s.scale_max).map((s) => (s.value / s.scale_max) * 100);
        if (!vals.length || vals.reduce((a, b) => a + b, 0) / vals.length > rule.score_max) return false;
      }
      if (has(rule, "max_minutes") || has(rule, "min_minutes")) {
        const t = timeInvestment(w);
        if (t === null) return false;
        if (has(rule, "max_minutes") && t.minutes > rule.max_minutes) return false;
        if (has(rule, "min_minutes") && t.minutes < rule.min_minutes) return false;
      }
      return true;
    }

    // 1 for a work read only for genre (an imported entry awaiting moods and themes), else 0 (mirrors browse.py _unclassified).
    const unclassified = (w) => ([...w.terms].some(([k, ev]) => !["genre", "advisory"].includes(k.split(":")[0]) && ev.strength > 0) ? 0 : 1);
    function shelfKey(w, rule) {
      const title = normaliseTitle(w.title);
      const sort = has(rule, "sort") ? rule.sort : "popular";
      if (sort === "strength") {
        const tags = [...(rule.any_tags || []), ...(rule.all_tags || [])];
        return [-Math.max(...(tags.length ? tags.map((t) => strengthOf(w, t)) : [0])), unclassified(w), w.popularity_tier || 5, title];
      }
      if (sort === "obscure") return [unclassified(w), -(w.popularity_tier || 0), title];
      if (sort === "shortest" || sort === "longest") {
        const t = timeInvestment(w);
        const m = t ? t.minutes : 1e9;
        return [sort === "shortest" ? m : -m, title];
      }
      return [unclassified(w), w.popularity_tier || 5, title];
    }

    function shelfHits(works, rule, ctx) {
      return works.filter((w) => shelfMatch(w, rule, ctx)).map((w) => [shelfKey(w, rule), w]).sort((a, b) => cmp(a[0], b[0])).map((x) => x[1]);
    }

    function shelves(works, spec, limit = 12) {
      const ctx = context(works);
      const out = [];
      for (const s of spec.shelves) {
        const hits = shelfHits(works, s.rule, ctx);
        if (hits.length >= (has(spec, "min_works") ? spec.min_works : 3)) {
          out.push({ slug: s.slug, name: s.name, tagline: s.tagline, description: s.description || "", total: hits.length, works: hits.slice(0, limit).map((w) => richCard(w, ctx)) });
        }
      }
      return out;
    }

    function shelf(works, spec, slug) {
      const s = spec.shelves.find((x) => x.slug === slug);
      if (!s) return null;
      const ctx = context(works);
      const hits = shelfHits(works, s.rule, ctx);
      return { slug: s.slug, name: s.name, tagline: s.tagline, description: s.description || "", rule: s.rule, total: hits.length, works: hits.map((w) => richCard(w, ctx)) };
    }

    // ---------------------------------------------------------------- social calendar (catalogue/calendar.json)
    // A programme is a dated window (fixed, a movable feast, or the nth weekday of a month) plus a shelf rule.
    const iso = (d) => d.toISOString().slice(0, 10);
    function programmeDates(p, spec, year) {
      const w = p.when;
      let start;
      if (w.start) { const [m, d] = w.start.split("-").map(Number); start = new Date(Date.UTC(year, m - 1, d)); }
      else if (w.movable) {
        const md = ((spec.movable || {})[w.movable] || {})[String(year)];
        if (!md) return null;   // no date on file for that year
        const [m, d] = md.split("-").map(Number);
        start = new Date(Date.UTC(year, m - 1, d + (w.offset || 0)));
      } else if (w.nth) {
        const first = new Date(Date.UTC(year, w.nth.month - 1, 1));
        const shift = (w.nth.weekday - first.getUTCDay() + 7) % 7;
        start = new Date(Date.UTC(year, w.nth.month - 1, 1 + shift + 7 * (w.nth.n - 1) + (w.offset || 0)));
      } else return null;
      const end = new Date(start.getTime() + (w.days - 1) * 86400000);
      return { start: iso(start), end: iso(end), days: w.days };
    }

    // How intense a work is, for "gentle" ordering: scares, violence and gore (unassessed counts as middling).
    function intensity(w) {
      return ["advisory:jump-scares", "advisory:graphic-violence", "advisory:body-horror"].reduce((a, k) => {
        const ev = w.terms.get(k);
        return a + (ev ? ev.strength : 0.5);
      }, 0);
    }

    function programmePicks(works, p, ctx) {
      const rule = p.rule;
      const tags = [...(rule.any_tags || []), ...(rule.all_tags || [])];
      const fit = (w) => (tags.length ? Math.max(...tags.map((t) => strengthOf(w, t))) : 0.5)
        + 0.5 * (p.prefer_tags || []).reduce((a, t) => a + strengthOf(w, t), 0) - 0.04 * ((w.popularity_tier || 5) - 1);
      // Editorial exclusions: tags at or above exclude_min (default 0.6), or named works.
      const excluded = (w) => (p.exclude_slugs || []).includes(w.slug)
        || (p.exclude_tags || []).some((t) => strengthOf(w, t) >= (has(p, "exclude_min") ? p.exclude_min : 0.6));
      const pool = (media) => works.filter((w) => shelfMatch(w, { ...rule, media }, ctx) && !excluded(w));
      let hits = pool(rule.media || []);
      if (rule.media && rule.media.length && hits.length < p.when.days && p.fallback_media) {
        const extra = pool(p.fallback_media).sort((a, b) => cmp([-fit(a), normaliseTitle(a.title)], [-fit(b), normaliseTitle(b.title)]));
        hits = [...hits, ...extra.slice(0, p.when.days - hits.length)];
      }
      const key = { strength: (w) => [-fit(w), w.popularity_tier || 5, normaliseTitle(w.title)],
        popular: (w) => [w.popularity_tier || 5, -fit(w), normaliseTitle(w.title)],
        chronological: (w) => [w.year || 9999, normaliseTitle(w.title)],
        gentle: (w) => [intensity(w), normaliseTitle(w.title)] }[p.order] || ((w) => [-fit(w), normaliseTitle(w.title)]);
      // Choose the strongest matches first, at most two per creator, then put them in the programme's order.
      const chosen = [], perCreator = new Map();
      for (const w of [...hits].sort((a, b) => cmp([-fit(a), w2t(a)], [-fit(b), w2t(b)]))) {
        const c = w.creators[0] || w.slug;
        if ((perCreator.get(c) || 0) >= 2) continue;
        perCreator.set(c, (perCreator.get(c) || 0) + 1);
        chosen.push(w);
        if (chosen.length >= p.when.days) break;
      }
      chosen.sort((a, b) => cmp(key(a), key(b)));
      // A named finale (Halloween on Halloween night) takes the last day if it qualified.
      const fin = p.finale_slug ? chosen.findIndex((w) => w.slug === p.finale_slug) : -1;
      if (fin >= 0) chosen.push(...chosen.splice(fin, 1));
      return { picks: chosen, matches: hits.length };
    }
    const w2t = (w) => normaliseTitle(w.title);

    function calendar(works, spec, year) {
      return spec.programmes.map((p) => {
        const dates = programmeDates(p, spec, year);
        return dates && { slug: p.slug, name: p.name, kind: p.kind, tagline: p.tagline, ...dates };
      }).filter(Boolean).sort((a, b) => cmp([a.start, a.name], [b.start, b.name]));
    }

    function programme(works, spec, slug, year) {
      const p = spec.programmes.find((x) => x.slug === slug);
      if (!p) return null;
      const dates = programmeDates(p, spec, year);
      if (!dates) return null;
      const ctx = context(works);
      const { picks, matches } = programmePicks(works, p, ctx);
      const n = picks.length, startMs = Date.parse(dates.start + "T00:00:00Z");
      // One a day when there are enough; otherwise spread across the window, keeping the last day for the finale.
      const dayOf = (i) => (n >= p.when.days || n < 2 ? i + 1 : Math.round(1 + (i * (p.when.days - 1)) / (n - 1)));
      const tagKeys = [...(p.rule.any_tags || []), ...(p.rule.all_tags || []), ...(p.prefer_tags || [])];
      return { slug: p.slug, name: p.name, kind: p.kind, tagline: p.tagline, finale: p.finale || null, ...dates, matches,
        picks: picks.map((w, i) => ({ day: dayOf(i), date: iso(new Date(startMs + (dayOf(i) - 1) * 86400000)),
          why: tagKeys.filter((k) => strengthOf(w, k) >= 0.5).map((k) => tax.get(k).label), work: richCard(w, ctx) })) };
    }

    function groupsIndex(works) {
      const seen = new Map();
      for (const w of works) {
        const c = continuity(w, works);
        if (c.group && !seen.has(c.group.slug)) seen.set(c.group.slug, { slug: c.group.slug, name: c.group.name, kind: c.kind, count: c.members.length });
      }
      return [...seen.values()].sort((a, b) => cmp([a.kind, normaliseTitle(a.name)], [b.kind, normaliseTitle(b.name)]));
    }

    function groupPage(works, slug) {
      const ctx = context(works);
      const owner = works.find((w) => ctx.get(w.slug).group && ctx.get(w.slug).group.slug === slug);
      if (!owner) return null;
      const c = ctx.get(owner.slug);
      const bySlug = new Map(works.map((w) => [w.slug, w]));
      const members = c.members.map((m) => bySlug.get(m.slug));
      const times = members.map(timeInvestment);
      return { slug, name: c.group.name, kind: c.kind,
        works: members.map((m, i) => ({ ...richCard(m, ctx), position: c.members[i].position })),
        total_minutes: times.reduce((a, t) => a + (t ? t.minutes : 0), 0), unknown_length: times.filter((t) => !t).length };
    }

    function trackItems(album) {
      const artist = album.creators.length ? album.creators[0] : "";
      return album.tracks.map((t) => ({ title: t.title, seconds: has(t, "seconds") ? t.seconds : null, album: album.slug,
        album_title: album.title, artist, spotify: spotifySearch(artist, t.title),
        remixes: (t.remixes || []).map((r) => ({ ...r, spotify: spotifySearch(r.artist || "", r.title || "") })) }));
    }

    function moodRings(works, spec) {
      const ctx = context(works);
      const out = [];
      for (const ring of spec.mood_rings) {
        const albums = works.filter((w) => w.medium === "album" && ring.tags.every((t) => strengthOf(w, t) >= 0.6))
          .sort((a, b) => cmp([-ring.tags.reduce((s, t) => s + strengthOf(a, t), 0), normaliseTitle(a.title)],
            [-ring.tags.reduce((s, t) => s + strengthOf(b, t), 0), normaliseTitle(b.title)]));
        if (albums.length) {
          out.push({ slug: ring.slug, name: ring.name, tagline: ring.tagline,
            albums: albums.map((a) => ({ ...richCard(a, ctx), spotify: spotifySearch(a.creators.length ? a.creators[0] : "", a.title) })),
            tracks: albums.flatMap(trackItems), mood_basis: "album" });
        }
      }
      return out;
    }

    const remixRack = (works) => works.filter((w) => w.medium === "album").flatMap(trackItems).filter((t) => t.remixes.length);

    // ---------------------------------------------------------------- taste profile and "for you" (mirrors browse.recommend)
    const TASTE_WEIGHTS = { loved: 2.0, liked: 1.0, disliked: -1.5 };
    const simWeightOf = (k) => { const d = k.split(":")[0]; return has(SIMILARITY_WEIGHTS, d) ? SIMILARITY_WEIGHTS[d] : 1.0; };
    const byKey = (m) => [...m.keys()].sort();

    function tasteVector(w) {
      const out = new Map();
      for (const [k, ev] of w.terms) {
        if (!k.startsWith("advisory:") && ev.strength >= TAG_THRESHOLD) out.set(k, ev.strength * simWeightOf(k));
      }
      return out;
    }

    function cosine(a, b) {
      let dot = 0, na = 0, nb = 0;
      for (const k of byKey(a)) if (b.has(k)) dot += a.get(k) * b.get(k);
      for (const k of byKey(a)) na += a.get(k) * a.get(k);
      for (const k of byKey(b)) nb += b.get(k) * b.get(k);
      na = Math.sqrt(na); nb = Math.sqrt(nb);
      return na && nb ? dot / (na * nb) : 0.0;
    }

    function tasteProfile(works, ratings) {
      const bySlug = new Map(works.map((w) => [w.slug, w]));
      const profile = new Map();
      for (const slug of Object.keys(ratings).sort()) {
        const weight = has(TASTE_WEIGHTS, ratings[slug]) ? TASTE_WEIGHTS[ratings[slug]] : null;
        const w = bySlug.get(slug);
        if (weight === null || !w) continue;
        const vec = tasteVector(w);
        for (const k of byKey(vec)) profile.set(k, (profile.has(k) ? profile.get(k) : 0.0) + weight * vec.get(k));
      }
      return profile;
    }

    function recommend(works, ratings, limit = 12, medium = null) {
      const profile = tasteProfile(works, ratings);
      const bySlug = new Map(works.map((w) => [w.slug, w]));
      const liked = Object.keys(ratings).filter((s) => (has(TASTE_WEIGHTS, ratings[s]) ? TASTE_WEIGHTS[ratings[s]] : 0) > 0).sort();
      const likedVecs = liked.filter((s) => bySlug.has(s)).map((s) => [s, tasteVector(bySlug.get(s))]);
      const topTerms = [...profile.keys()].filter((k) => profile.get(k) > 0)
        .sort((a, b) => cmp([-pyRound(profile.get(a), 6), a], [-pyRound(profile.get(b), 6), b]));
      const out = { profile: topTerms.slice(0, 8).map((k) => ({ key: k, label: tax.get(k).label, weight: pyRound(profile.get(k), 3) })),
        rated: Object.keys(ratings).filter((s) => bySlug.has(s)).length, results: [] };
      if (!likedVecs.length) return out;
      const ctx = context(works);
      const scored = [];
      for (const w of works) {
        if (has(ratings, w.slug) || (medium && w.medium !== medium)) continue;
        const vec = tasteVector(w);
        const score = pyRound(cosine(profile, vec), 6);
        if (score <= 0) continue;
        let because = null, best = -Infinity;
        for (const [s, lv] of likedVecs) {
          const c = pyRound(cosine(lv, vec), 6);
          if (c > best) { best = c; because = s; }
        }
        const shared = [...vec.keys()].filter((k) => (profile.has(k) ? profile.get(k) : 0) > 0)
          .sort((a, b) => cmp([-pyRound(profile.get(a) * vec.get(a), 6), a], [-pyRound(profile.get(b) * vec.get(b), 6), b])).slice(0, 3);
        scored.push([score, w, because, shared]);
      }
      scored.sort((a, b) => cmp([-a[0], a[1].popularity_tier || 5, normaliseTitle(a[1].title)], [-b[0], b[1].popularity_tier || 5, normaliseTitle(b[1].title)]));
      out.results = scored.slice(0, limit).map(([score, w, b, shared]) => ({ ...richCard(w, ctx), score: pyRound(score, 4),
        because: { slug: b, title: bySlug.get(b).title }, shared: shared.map((k) => ({ key: k, label: tax.get(k).label })) }));
      return out;
    }

    return { browse, tagIndex, tagPage, peopleIndex, personPage, workPage, shelves, shelf, groupsIndex, groupPage, calendar, programme,
      moodRings, remixRack, recommend, timeInvestment, continuity, context, richCard };
  }

  function stem(word) {
    for (const suffix of ["ing", "es", "ed", "s"]) {
      if (word.length > suffix.length + 3 && word.endsWith(suffix)) return word.slice(0, -suffix.length);
    }
    return word;
  }
  const words = (text) => new Set(((text || "").toLowerCase().match(/[a-z0-9]+/g) || []).map(stem));

  // ------------------------------------------------------------------ where to watch / listen / read / play (mirrors providers.py)
  function itemOf(w) {
    const platforms = w.attributes.platforms;
    return { medium: w.medium, title: w.title, creator: w.creators.length ? w.creators[0] : "", year: w.year,
      platforms: Array.isArray(platforms) ? [...platforms] : [], ids: { ...w.ids } };
  }

  function whereFor(item, region, spec) {
    const media = spec.media[item.medium];
    if (!media) return null;
    region = has(spec.regions, region) ? region : spec.default_region;
    const fields = spec.regions[region];
    const platforms = item.platforms || [];
    const ids = item.ids || {};
    const out = [];
    for (const p of media.providers) {
      if (has(p, "regions") && !p.regions.includes(region)) continue;
      if (has(p, "platforms") && platforms.length && !p.platforms.some((x) => platforms.includes(x))) continue;
      const exact = has(p, "exact") && ids[p.exact.id] ? p.exact : null;
      let url;
      if (exact) url = exact.url.replace("{id}", pyQuote(String(ids[exact.id])));
      else {
        let q = p.q;
        for (const key of ["title", "creator", "year"]) {
          const value = item[key];
          q = q.split(`{${key}}`).join(value === null || value === undefined ? "" : String(value));
        }
        q = q.replace(/\s+/g, " ").trim();
        url = p.url;
        for (const [key, value] of Object.entries(fields)) url = url.split(`{${key}}`).join(value);
        const encoded = pyQuote(q);
        url = url.split("{q}").join(p.enc === "query" ? encoded.replace(/%20/g, "+") : encoded);
      }
      out.push({ id: p.id, name: p.name, verb: has(p, "verb") ? p.verb : media.verb, url, exact: !!exact });
    }
    const dflt = out.some((p) => p.id === media.default) ? media.default : out.length ? out[0].id : null;
    return { medium: item.medium, verb: media.verb, region, default: dflt, providers: out };
  }

  function createCatalogue(data, taxonomyData, enrichment = {}, shelfSpec = { shelves: [], mood_rings: [] }, providerSpec = null, calendarSpec = { programmes: [] }) {
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
        page_count: null, images: [], scores: [], box_office: [], groups: [], links: [], ids: {}, tracks: [], fact_sources: {},
      });
    }
    for (const [aSlug, type, bSlug, note, confidence] of data.relationships || []) {
      const [label, inverse, factual] = RELATIONSHIP_TYPES[type];
      const origin = factual ? "editorial" : "ai_assisted";
      const a = works.get(aSlug), b = works.get(bSlug);
      a.relations.push({ other_slug: b.slug, other_title: b.title, other_medium: b.medium, type, label, note, confidence, origin, factual });
      b.relations.push({ other_slug: a.slug, other_title: a.title, other_medium: a.medium, type, label: inverse, note, confidence, origin, factual });
    }
    const list = applyEnrichment([...works.values()], enrichment);
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
      // Best-known first; then the work with a written summary; then the slug (mirrors memory.py and repository.py).
      const rank = (w) => [w.popularity_tier || 5, w.summary ? 0 : 1, w.slug];
      const best = hits.reduce((a, h) => (cmp(rank(h), rank(a)) < 0 ? h : a));
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
        message: results.length ? null : "Nothing in the catalogue matches this well enough to recommend. The beta " +
          "catalogue is still growing; try describing the experience you want rather than a specific subject.",
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
      shelves: () => views.shelves(list, shelfSpec),
      shelf: (slug) => views.shelf(list, shelfSpec, slug),
      groups: () => views.groupsIndex(list),
      group: (slug) => views.groupPage(list, slug),
      moodRings: () => views.moodRings(list, shelfSpec),
      remixRack: () => views.remixRack(list),
      recommend: (ratings, limit = 12, medium = null) => views.recommend(list, ratings, limit, medium),
      calendar: (year) => views.calendar(list, calendarSpec, year),
      programme: (slug, year) => views.programme(list, calendarSpec, slug, year),
      where: (slug, region) => { const w = list.find((x) => x.slug === slug); return w && providerSpec ? whereFor(itemOf(w), region, providerSpec) : null; },
      whereFor: (item, region) => (providerSpec ? whereFor(item, region, providerSpec) : null),
      regions: () => (providerSpec ? Object.entries(providerSpec.regions).map(([code, r]) => ({ code, name: r.name })) : []),
    };
  }

  return { createCatalogue };
})();

if (typeof module !== "undefined" && module.exports) module.exports = MDE;
