// Mimir search: the query syntax, matching, relevance and autocomplete. Pure and dependency-free, so the app and the tests share it.
//
// Syntax (everything is optional; plain words still just work):
//   dune arrakis            all words must match a title, credit, franchise or tag      "a rainy day"   an exact phrase
//   -horror  NOT horror     leave out matches                                           dune OR alien   either side
//   dune*  bl?de            wildcards (* any letters, ? one letter) on a word           /^the .* of/i   a regular expression
//   title:  by:  cast:  director:  author:  artist:  developer:  studio:   (by: matches any credit)
//   year:2019  year:2015..2020  year:>=2010  decade:1990s  runtime:<120  runtime:90..150
//   medium:film|tv|book|game|album|video|channel   lang:ja   country:india   rating:PG-13   franchise:zelda
//   genre:  tag:  mood:  theme:  style:  pacing:  (a tag name or its slug)    is:assessed|unassessed|new|classic|popular|obscure
//   has:summary|score|guide|cover   tier:1..5   title:/regex/   summary:/regex/
// Anything that cannot be understood is reported in `notes` and treated as plain text, never as an error page.
"use strict";
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MimirSearch = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  const norm = (s) => String(s == null ? "" : s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/&/g, " and ").replace(/[^a-z0-9]+/g, " ").trim();
  const words = (s) => (norm(s) ? norm(s).split(" ") : []);

  const MEDIA = { film: "film", films: "film", movie: "film", movies: "film", tv: "series", series: "series", show: "series", shows: "series", television: "series",
    book: "book", books: "book", manga: "book", novel: "book", game: "game", games: "game", album: "album", albums: "album", music: "album",
    video: "online_video", videos: "online_video", youtube: "online_video", channel: "channel", channels: "channel" };
  const ROLE_FIELDS = { director: ["director"], author: ["author"], artist: ["artist"], developer: ["developer"], dev: ["developer"], creator: ["creator"],
    starring: ["actor"], cast: ["actor"], actor: ["actor"] };
  const FIELDS = ["title", "t", "by", "person", "studio", ...Object.keys(ROLE_FIELDS), "year", "y", "decade", "medium", "type", "in", "lang", "language", "country",
    "rating", "franchise", "universe", "genre", "tag", "mood", "theme", "style", "pacing", "world", "narrative", "complexity", "runtime", "length", "minutes",
    "is", "has", "tier", "summary"];
  const DIMENSION_FIELDS = new Set(["genre", "mood", "theme", "style", "pacing", "world", "narrative", "complexity"]);
  const LANGUAGES = { english: "en", hindi: "hi", tamil: "ta", telugu: "te", malayalam: "ml", kannada: "kn", bengali: "bn", marathi: "mr", punjabi: "pa", urdu: "ur",
    japanese: "ja", korean: "ko", chinese: "zh", mandarin: "zh", cantonese: "yue", french: "fr", german: "de", spanish: "es", italian: "it", portuguese: "pt",
    russian: "ru", turkish: "tr", arabic: "ar", persian: "fa", swedish: "sv", danish: "da", norwegian: "no", finnish: "fi", polish: "pl", dutch: "nl", thai: "th",
    indonesian: "id", greek: "el", hebrew: "he", czech: "cs", hungarian: "hu", icelandic: "is", ukrainian: "uk", vietnamese: "vi" };
  const COUNTRIES = { usa: "US", america: "US", american: "US", uk: "GB", britain: "GB", british: "GB", england: "GB", india: "IN", indian: "IN", japan: "JP", japanese: "JP",
    korea: "KR", "south korea": "KR", korean: "KR", china: "CN", chinese: "CN", france: "FR", french: "FR", germany: "DE", german: "DE", italy: "IT", italian: "IT",
    spain: "ES", spanish: "ES", canada: "CA", canadian: "CA", australia: "AU", mexico: "MX", brazil: "BR", russia: "RU", sweden: "SE", denmark: "DK", norway: "NO",
    ireland: "IE", nigeria: "NG", turkey: "TR", iran: "IR", argentina: "AR", poland: "PL", thailand: "TH", "hong kong": "HK", taiwan: "TW", "new zealand": "NZ" };
  const TAG_MIN = 0.5;

  // ---------------------------------------------------------------- tokenising
  function tokenise(text) {
    const out = [];
    let i = 0;
    const s = String(text || "");
    while (i < s.length) {
      if (/\s/.test(s[i])) { i++; continue; }
      let neg = false;
      if (s[i] === "-" && i + 1 < s.length && !/\s/.test(s[i + 1])) { neg = true; i++; }
      let field = null;
      const m = /^([A-Za-z]+):/.exec(s.slice(i));
      if (m && FIELDS.includes(m[1].toLowerCase())) { field = m[1].toLowerCase(); i += m[0].length; }
      let value = "", kind = "word";
      if (s[i] === '"') {
        const j = s.indexOf('"', i + 1);
        value = s.slice(i + 1, j < 0 ? s.length : j); i = j < 0 ? s.length : j + 1; kind = "phrase";
      } else if (s[i] === "/") {
        let j = i + 1;
        while (j < s.length && (s[j] !== "/" || s[j - 1] === "\\")) j++;
        if (j < s.length) {
          const fm = /^[a-z]*/.exec(s.slice(j + 1))[0];
          value = s.slice(i + 1, j); kind = "regex"; i = j + 1 + fm.length; out.push({ neg, field, kind, value, flags: fm }); continue;
        }
        const k = /\S*/.exec(s.slice(i))[0]; value = k; i += k.length;
      } else {
        const k = /\S*/.exec(s.slice(i))[0]; value = k; i += k.length;
      }
      if (kind === "word" && /^(or|\|)$/i.test(value) && !field) { out.push({ kind: "or" }); continue; }
      if (kind === "word" && /^not$/i.test(value) && !field) { out.push({ kind: "not" }); continue; }
      out.push({ neg, field, kind, value });
    }
    // NOT word  ->  -word
    for (let k = 0; k < out.length - 1; k++) if (out[k].kind === "not") { out[k + 1].neg = true; out[k] = { kind: "skip" }; }
    return out.filter((t) => t.kind !== "skip");
  }

  const DANGEROUS = /\([^)]*[+*][^)]*\)[+*{]|\\\d|\(\?[=!<]/;   // nested quantifiers, backreferences and lookarounds: refuse rather than risk a stuck page
  function compileRegex(source, flags, notes) {
    if (source.length > 120 || DANGEROUS.test(source)) { notes.push(`The pattern /${source.slice(0, 40)}/ is too complex and was ignored.`); return null; }
    try { return new RegExp(source, [...new Set((flags || "").replace(/[^imsu]/g, "").split(""))].join("") || "i"); }
    catch { notes.push(`/${source.slice(0, 40)}/ is not a valid pattern and was ignored.`); return null; }
  }

  // ---------------------------------------------------------------- numbers
  function numberTest(value) {
    const v = String(value).trim();
    let m;
    if ((m = /^(\d+)\.\.(\d+)$/.exec(v))) return (n) => n >= +m[1] && n <= +m[2];
    if ((m = /^(\d+)\.\.$/.exec(v))) return (n) => n >= +m[1];
    if ((m = /^\.\.(\d+)$/.exec(v))) return (n) => n <= +m[1];
    if ((m = /^(>=|<=|>|<|=)?(\d+)$/.exec(v))) {
      const k = +m[2];
      return { ">=": (n) => n >= k, "<=": (n) => n <= k, ">": (n) => n > k, "<": (n) => n < k }[m[1]] || ((n) => n === k);
    }
    return null;
  }

  // ---------------------------------------------------------------- context
  // ctx: { tags: [{key,label,dimension,synonyms?}], now: year }
  function makeContext(tags, now = new Date().getFullYear()) {
    const byName = new Map();
    for (const t of tags || []) {
      const slug = t.key.split(":")[1];
      for (const n of [slug, t.label, ...(t.synonyms || [])]) { const k = norm(n); if (k && !byName.has(k + "|" + t.dimension)) byName.set(k + "|" + t.dimension, t.key); if (k && !byName.has(k)) byName.set(k, t.key); }
    }
    return { tags: tags || [], tagByName: byName, now };
  }
  function resolveTag(ctx, name, dimension) {
    const k = norm(name);
    if (!k) return null;
    if (dimension && ctx.tagByName.has(k + "|" + dimension)) return ctx.tagByName.get(k + "|" + dimension);
    if (!dimension && ctx.tagByName.has(k)) return ctx.tagByName.get(k);
    const pool = (ctx.tags || []).filter((t) => !dimension || t.dimension === dimension);
    const starts = pool.filter((t) => norm(t.label).startsWith(k) || norm(t.key.split(":")[1]).startsWith(k));
    return starts.length === 1 ? starts[0].key : null;
  }

  // ---------------------------------------------------------------- compile one token to a test on a work
  function creditNames(w, roles) {
    return (w.credits || []).filter((c) => !roles || roles.includes(c[0])).map((c) => c[1]);
  }
  function hay(w) {
    if (w._hay) return w._hay;
    const f = (w.attributes && (w.attributes.franchises || [])) || [];
    const parts = [w.title, w.original_title, ...creditNames(w), ...f, w.attributes && w.attributes.series];
    return (w._hay = " " + norm(parts.filter(Boolean).join(" ")) + " ");
  }
  const textOf = (w) => [w.title, w.original_title, ...creditNames(w), w.summary].filter(Boolean).join(" \n ");
  const strength = (w, key) => Number((w.terms || {})[key]) || 0;
  const isAssessed = (w) => !!(w.advisories && Object.values(w.advisories).some((v) => (Array.isArray(v) ? v[0] : v) > 0)) || !!(w.ratings && w.ratings.length);

  function compileToken(t, ctx, notes) {
    const f = t.field, v = t.value;
    if (t.kind === "regex") {
      const re = compileRegex(v, t.flags, notes);
      if (!re) return null;
      const target = f === "summary" ? (w) => w.summary || "" : f === "title" || f === "t" ? (w) => w.title : f === "by" || f === "person" || f in ROLE_FIELDS ? (w) => creditNames(w, ROLE_FIELDS[f]).join(" \n ") : textOf;
      return (w) => re.test(target(w).slice(0, 1500));
    }
    if (!f) {
      if (t.kind === "phrase") { const p = " " + norm(v) + " "; return p.trim() ? (w) => hay(w).includes(p) : null; }
      if (/[*?]/.test(v)) {
        const body = v.toLowerCase().replace(/[^a-z0-9*?]/g, "").replace(/\*/g, "[a-z0-9]*").replace(/\?/g, "[a-z0-9]");
        if (!body) return null;
        const rx = new RegExp("(?:^| )" + body + "(?: |$)");
        return (w) => rx.test(hay(w));
      }
      const n = norm(v);
      if (!n) return null;
      const parts = n.split(" ");
      return (w) => parts.every((p) => (p.length < 3 ? hay(w).includes(" " + p) : hay(w).includes(p)));
    }
    const n = norm(v);
    switch (f) {
      case "title": case "t": return t.kind === "phrase" || n.includes(" ") ? (w) => norm(w.title).includes(n) : (w) => norm(w.title).split(" ").some((x) => x.startsWith(n)) || norm(w.title).includes(n);
      case "summary": return (w) => norm(w.summary).includes(n);
      case "by": case "person": case "studio": case "director": case "author": case "artist": case "developer": case "dev": case "creator": case "starring": case "cast": case "actor": {
        const roles = ROLE_FIELDS[f];
        return (w) => creditNames(w, roles).some((c) => norm(c).includes(n));
      }
      case "year": case "y": { const test = numberTest(v); if (!test) { notes.push(`year:${v} was not understood.`); return null; } return (w) => w.year != null && test(w.year); }
      case "decade": { const m = /^(\d{3})0?s?$/.exec(v) || /^(\d{2})s$/.exec(v); if (!m) { notes.push(`decade:${v} was not understood.`); return null; }
        const d = m[1].length === 3 ? +m[1] * 10 : (+m[1] < 30 ? 2000 : 1900) + +m[1]; return (w) => w.year != null && w.year >= d && w.year < d + 10; }
      case "medium": case "type": case "in": {
        const m = MEDIA[n]; if (!m) { if (f === "in") return (w) => hay(w).includes(n); notes.push(`"${v}" is not a medium: try film, tv, book, game, album, video or channel.`); return null; }
        return (w) => w.medium === m; }
      case "lang": case "language": {
        const code = LANGUAGES[n] || (/^[a-z]{2,3}$/.test(n) ? n : null); if (!code) { notes.push(`"${v}" is not a language Mimir knows.`); return null; }
        return (w) => w.language === code; }
      case "country": {
        const code = COUNTRIES[n] || (/^[a-z]{2}$/.test(n) ? n.toUpperCase() : null); if (!code) { notes.push(`"${v}" is not a country Mimir knows.`); return null; }
        return (w) => (w.countries || []).includes(code); }
      case "rating": { const r = String(v).toLowerCase(); return (w) => (w.ratings || []).some((x) => String(x[1] || x.rating || "").toLowerCase() === r); }
      case "franchise": case "universe": return (w) => norm(((w.attributes && w.attributes.franchises) || []).concat([w.attributes && w.attributes.series].filter(Boolean)).join(" ")).includes(n);
      case "genre": case "mood": case "theme": case "style": case "pacing": case "world": case "narrative": case "complexity": case "tag": {
        const key = resolveTag(ctx, v, DIMENSION_FIELDS.has(f) ? f : null);
        if (!key) { notes.push(`No tag called "${v}"${DIMENSION_FIELDS.has(f) ? ` in ${f}` : ""}.`); return null; }
        return (w) => strength(w, key) >= TAG_MIN; }
      case "runtime": case "length": case "minutes": {
        const test = numberTest(v); if (!test) { notes.push(`${f}:${v} was not understood.`); return null; }
        return (w) => { const m = w.runtime_minutes != null ? w.runtime_minutes : null; return m != null && test(m); }; }
      case "tier": { const test = numberTest(v); if (!test) return null; return (w) => test(w.popularity_tier || 5); }
      case "is": {
        const k = n;
        const map = { assessed: isAssessed, unassessed: (w) => !isAssessed(w), new: (w) => w.year != null && w.year >= ctx.now - 2, recent: (w) => w.year != null && w.year >= ctx.now - 2,
          classic: (w) => w.year != null && w.year < 1990, popular: (w) => (w.popularity_tier || 5) <= 2, obscure: (w) => (w.popularity_tier || 5) >= 4 };
        if (!map[k]) { notes.push(`is:${v} is not known: try assessed, unassessed, new, classic, popular or obscure.`); return null; }
        return map[k]; }
      case "has": {
        const map = { summary: (w) => !!w.summary, score: (w) => !!(w.scores && w.scores.length), guide: isAssessed, cover: (w) => !!w.image };
        if (!map[n]) { notes.push(`has:${v} is not known: try summary, score, guide or cover.`); return null; }
        return map[n]; }
      default: return null;
    }
  }

  // ---------------------------------------------------------------- parse
  // Returns { alts: [{ pos: [fn], neg: [fn] }], notes, plain, advanced }. `plain` is the free text left once operators are removed.
  function parse(text, ctx, { filtersOnly = false } = {}) {
    ctx = ctx || makeContext([]);
    const notes = [];
    const toks = tokenise(text);
    const alts = [{ pos: [], neg: [], words: [] }];
    let advanced = false;
    for (const t of toks) {
      if (t.kind === "or") { alts.push({ pos: [], neg: [], words: [] }); advanced = true; continue; }
      if (filtersOnly && !t.field && t.kind === "word" && !t.neg && !/[*?]/.test(t.value)) continue;   // Ask: plain words go to the ranker, not the filter
      const fn = compileToken(t, ctx, notes);
      if (t.field || t.kind !== "word" || t.neg || /[*?]/.test(t.value)) advanced = true;
      if (!fn) continue;
      const cur = alts[alts.length - 1];
      (t.neg ? cur.neg : cur.pos).push(fn);
      if (!t.field && t.kind === "word" && !t.neg && !/[*?]/.test(t.value)) cur.words.push(norm(t.value));
    }
    const live = alts.filter((a) => a.pos.length || a.neg.length);
    return { alts: live, notes, advanced, empty: !live.length, plain: alts[0].words.join(" "), tokens: toks };
  }

  function test(work, parsed) {
    if (parsed.empty) return true;
    return parsed.alts.some((a) => a.pos.every((fn) => fn(work)) && !a.neg.some((fn) => fn(work)));
  }

  // Relevance for ordering: title matches first (exact, prefix, word start), then credits, then everything else; best known breaks ties.
  function relevance(work, parsed) {
    const q = parsed.plain;
    if (!q) return 0;
    const t = norm(work.title);
    let s = 0;
    if (t === q) s = 100;
    else if (t.startsWith(q)) s = 80;
    else if (t.includes(" " + q)) s = 60;
    else if (t.includes(q)) s = 40;
    else if (q.split(" ").every((p) => t.includes(p))) s = 30;
    else s = 10;
    return s + (6 - Math.min(5, work.popularity_tier || 5));
  }

  // ---------------------------------------------------------------- suggestions
  const KIND_ORDER = ["recent", "title", "franchise", "person", "tag"];
  function editDistance(a, b, max) {
    if (Math.abs(a.length - b.length) > max) return max + 1;
    const dp = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) {
      dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) dp[i][j] = Math.min(dp[i][j], dp[i - 2][j - 2] + 1);
    }
    return dp[a.length][b.length];
  }

  // entries: [{ kind, label, hint, href, boost }]; the index keeps normalised keys so a keystroke is a cheap scan.
  function buildIndex(entries) {
    return entries.map((e) => { const key = norm(e.label); return { ...e, key, ws: key.split(" "), boost: e.boost || 0 }; });
  }
  function scoreEntry(e, q, qw) {
    if (e.key === q) return 100 + e.boost;
    if (e.key.startsWith(q)) return 80 + e.boost;
    if (e.ws.some((w) => w.startsWith(q))) return 60 + e.boost;
    if (qw.length > 1 && qw.every((p) => e.ws.some((w) => w.startsWith(p)))) return 55 + e.boost;
    if (q.length >= 3 && e.key.includes(q)) return 30 + e.boost;
    if (q.length >= 4) {
      const fz = e.ws.some((w) => w.length >= 4 && editDistance(w.slice(0, q.length + 1), q, 1) <= 1) || editDistance(e.key.slice(0, q.length + 1), q, 1) <= 1;
      if (fz) return 15 + e.boost;
    }
    return 0;
  }
  // Returns { items: [{ kind, label, hint, href, score }], didYouMean: label|null } with at most `limit` items spread across kinds.
  function suggest(index, text, { limit = 8, recent = [], perKind = { title: 5, franchise: 2, person: 3, tag: 3, recent: 4 } } = {}) {
    const q = norm(text);
    if (!q) {
      return { items: recent.slice(0, perKind.recent).map((r) => ({ kind: "recent", label: r, hint: "Recent", href: null, score: 1 })), didYouMean: null };
    }
    const qw = q.split(" ");
    const picked = { recent: [], title: [], franchise: [], person: [], tag: [] };
    for (const r of recent) { const k = norm(r); if (k.startsWith(q) && k !== q) picked.recent.push({ kind: "recent", label: r, hint: "Recent", href: null, score: 90 }); }
    for (const e of index) {
      const s = scoreEntry(e, q, qw);
      if (s > 0 && picked[e.kind]) picked[e.kind].push({ kind: e.kind, label: e.label, hint: e.hint, href: e.href, score: s, extra: e.extra });
    }
    const items = [];
    for (const kind of KIND_ORDER) {
      const list = picked[kind].sort((a, b) => b.score - a.score || a.label.length - b.label.length || a.label.localeCompare(b.label)).slice(0, perKind[kind]);
      items.push(...list);
    }
    // best overall first within the cap, but keep the group order stable for the reader
    const keep = new Set([...items].sort((a, b) => b.score - a.score).slice(0, limit));
    const out = items.filter((i) => keep.has(i));
    let didYouMean = null;
    if (!out.length && q.length >= 4) {
      let best = null;
      for (const e of index) if (e.kind === "title" || e.kind === "person" || e.kind === "franchise") {
        const d = Math.min(editDistance(e.key, q, 2), ...e.ws.map((w) => editDistance(w, q, 2)));
        if (d <= 2 && (!best || d < best.d || (d === best.d && e.boost > best.e.boost))) best = { d, e };
      }
      if (best) didYouMean = best.e.label;
    }
    return { items: out, didYouMean };
  }

  // Completions for an operator being typed ("genre:co", "lang:", "medium:g").
  function operatorHints(text, ctx) {
    const m = /(?:^|\s)-?([A-Za-z]+):(\S*)$/.exec(text || "");
    if (!m) {
      const w = /(?:^|\s)-?([A-Za-z]{2,})$/.exec(text || "");
      return w ? FIELDS.filter((f) => f.startsWith(w[1].toLowerCase()) && f.length > 2).slice(0, 5).map((f) => ({ label: f + ":", insert: f + ":", hint: "Filter" })) : [];
    }
    const f = m[1].toLowerCase(), v = norm(m[2]);
    const pick = (list) => list.filter((x) => !v || norm(x).startsWith(v)).slice(0, 8);
    let values = [];
    if (f === "medium" || f === "type") values = pick(["film", "tv", "book", "game", "album", "video", "channel"]);
    else if (f === "lang" || f === "language") values = pick(Object.keys(LANGUAGES));
    else if (f === "country") values = pick(Object.keys(COUNTRIES));
    else if (f === "is") values = pick(["assessed", "unassessed", "new", "classic", "popular", "obscure"]);
    else if (f === "has") values = pick(["summary", "score", "guide", "cover"]);
    else if (f === "decade") values = pick(["1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]);
    else if (DIMENSION_FIELDS.has(f) || f === "tag") values = (ctx.tags || []).filter((t) => (f === "tag" || t.dimension === f) && (!v || norm(t.label).startsWith(v) || norm(t.key.split(":")[1]).startsWith(v))).slice(0, 8).map((t) => t.key.split(":")[1]);
    const head = text.slice(0, text.length - m[2].length);
    return values.map((x) => ({ label: `${f}:${x}`, insert: head + x + " ", hint: "Filter" }));
  }

  return { norm, tokenise, parse, test, relevance, makeContext, resolveTag, buildIndex, suggest, operatorHints, editDistance, FIELDS, MEDIA };
});
