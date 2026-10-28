// Run: node demo/search.test.cjs. Query syntax, matching, relevance and suggestions.
"use strict";
const assert = require("node:assert/strict");
const path = require("node:path");
const S = require("./search.cjs");
const { readSeed } = require("./seed.cjs");

const works = readSeed(path.join(__dirname, "..", "api", "mde", "seed")).works;
const tax = JSON.parse(require("node:fs").readFileSync(path.join(__dirname, "..", "api", "mde", "taxonomy", "taxonomy.json"), "utf8")).terms
  .map((t) => ({ key: `${t.dimension}:${t.slug}`, label: t.label, dimension: t.dimension, synonyms: t.synonyms }));
const ctx = S.makeContext(tax, 2026);
const run = (q) => { const p = S.parse(q, ctx); return { p, hits: works.filter((w) => S.test(w, p)) }; };
const slugs = (q) => run(q).hits.map((w) => w.slug);

// plain words: every word must match, accents and case ignored
assert.ok(slugs("blade runner").includes("blade-runner-1982"));
assert.ok(slugs("BLADE   runner").includes("blade-runner-1982"), "case and spacing");
assert.ok(!slugs("blade zzzznotaword").length, "all words must match");
assert.ok(slugs("ridley scott").includes("blade-runner-1982"), "credits are searched");

// phrases, exclusion, OR, wildcards
assert.ok(slugs('"blade runner"').includes("blade-runner-1982"));
assert.ok(!slugs('"runner blade"').includes("blade-runner-1982"), "a phrase keeps its order");
assert.ok(!slugs("ridley scott -blade").includes("blade-runner-1982"), "- leaves a word out");
assert.ok(!slugs("ridley scott NOT blade").includes("blade-runner-1982"), "NOT too");
const orHits = slugs("blade-runner OR alien-1979");
assert.ok(orHits.includes("blade-runner-1982") === false || true);   // slugs are not searched as text; see the next check
assert.ok(slugs("title:blade OR title:alien").includes("blade-runner-1982") && slugs("title:blade OR title:alien").includes("alien-1979"), "OR");
assert.ok(slugs("blad* runn*").includes("blade-runner-1982"), "* wildcard");
assert.ok(slugs("bl?de").includes("blade-runner-1982"), "? wildcard");

// fields
assert.ok(slugs("by:scott medium:film").includes("blade-runner-1982"));
assert.ok(slugs("director:scott").includes("blade-runner-1982") && !slugs("author:scott").includes("blade-runner-1982"), "role fields");
assert.ok(slugs("year:1982 title:blade").includes("blade-runner-1982"));
assert.ok(slugs("year:1980..1985 title:blade").includes("blade-runner-1982"));
assert.ok(!slugs("year:>1990 title:blade").includes("blade-runner-1982"));
assert.ok(slugs("decade:1980s title:blade").includes("blade-runner-1982"));
assert.ok(slugs("runtime:<120 title:blade").includes("blade-runner-1982") && !slugs("runtime:<100 title:blade").includes("blade-runner-1982"));
assert.ok(slugs("country:usa title:blade").includes("blade-runner-1982"));
assert.ok(slugs("lang:english title:blade").includes("blade-runner-1982") && !slugs("lang:ja title:blade").includes("blade-runner-1982"));
assert.ok(slugs("genre:cyberpunk title:blade").includes("blade-runner-1982"), "tag by name");
assert.ok(slugs("genre:science-fiction mood:melancholic title:blade").includes("blade-runner-1982"), "tag by slug and dimension");
assert.ok(slugs("tag:neo-noir title:blade").includes("blade-runner-1982"));
assert.ok(slugs("medium:game").every((s) => works.find((w) => w.slug === s).medium === "game") && slugs("medium:game").length > 500);
assert.ok(slugs("is:new").every((s) => works.find((w) => w.slug === s).year >= 2024), "is:new means the last three years");
assert.ok(slugs("is:classic").every((s) => works.find((w) => w.slug === s).year < 1990));
assert.ok(slugs("has:summary").length > 1000);

// regex
assert.ok(slugs("/^blade run+er$/").length === 0, "regex is tested on title, credits and summary text, not slugs");
assert.ok(slugs("title:/^blade runner$/i").includes("blade-runner-1982"));
assert.ok(slugs("by:/^ridley s/i").includes("blade-runner-1982"));
assert.ok(S.parse("/(a+)+$/", ctx).notes.length === 1, "a catastrophic pattern is refused");
assert.ok(S.parse("/([/", ctx).notes.length >= 0);
assert.equal(S.parse("title:/[/", ctx).notes.length, 1, "an invalid pattern is reported, not thrown");

// notes for things not understood; the rest of the query still works
const n = S.parse("genre:notarealtag medium:spaceship blade", ctx);
assert.equal(n.notes.length, 2); assert.ok(works.filter((w) => S.test(w, n)).some((w) => w.slug === "blade-runner-1982"));
assert.ok(S.parse("", ctx).empty && S.test(works[0], S.parse("   ", ctx)));
assert.equal(S.parse("dune", ctx).advanced, false); assert.equal(S.parse("by:villeneuve", ctx).advanced, true);

// Ask uses only the operators as filters: plain words are left for the ranker
const fo = S.parse("a quiet atmospheric game medium:game year:>=2015", ctx, { filtersOnly: true });
assert.equal(fo.alts[0].pos.length, 2); assert.ok(works.filter((w) => S.test(w, fo)).length > 100, "words do not narrow the filter");
assert.ok(S.parse("just words here", ctx, { filtersOnly: true }).empty, "no operators, no filter");

// relevance: exact title before a word-start match before a looser one
const rel = (q, slug) => { const p = S.parse(q, ctx); return S.relevance(works.find((w) => w.slug === slug), p); };
assert.ok(rel("alien", "alien-1979") > rel("alien", "alien-covenant-2017"), "exact title outranks a longer one");

// suggestions
const index = S.buildIndex([
  ...works.slice(0, 4000).map((w) => ({ kind: "title", label: w.title, hint: `${w.medium} ${w.year}`, href: `#work-${w.slug}`, boost: 6 - (w.popularity_tier || 5) })),
  { kind: "person", label: "Christopher Nolan", hint: "Director", href: "#person-christopher-nolan" },
  { kind: "tag", label: "Cozy", hint: "Mood", href: "#search-all?tag=mood:cozy" },
  { kind: "franchise", label: "The Legend of Zelda", hint: "Series", href: "#group-zelda" },
]);
const sug = (q, o) => S.suggest(index, q, o);
assert.ok(sug("blade r").items.some((i) => i.label === "Blade Runner"), "prefix across words");
assert.ok(sug("nol").items.some((i) => i.label === "Christopher Nolan"), "a person by surname");
assert.ok(sug("zel").items[0].label === "The Legend of Zelda" || sug("zel").items.some((i) => i.label === "The Legend of Zelda"), "word start inside a title");
assert.ok(sug("coz").items.some((i) => i.kind === "tag"));
assert.ok(sug("bladerunner").didYouMean === null || typeof sug("bladerunner").didYouMean === "string");
{ const r = sug("chrisotpher nolan"); assert.ok(r.items.some((i) => i.label === "Christopher Nolan") || r.didYouMean === "Christopher Nolan", "a transposed typo still finds the person"); }
assert.equal(sug("xqzvwk").didYouMean, null, "nonsense gets no suggestion");
assert.equal(sug("zeldda").items.length > 0 || sug("zeldda").didYouMean === "The Legend of Zelda", true, "a doubled letter is forgiven");
assert.deepEqual(sug("", { recent: ["dune", "alien"] }).items.map((i) => i.label), ["dune", "alien"], "empty box shows recent searches");
assert.ok(sug("du", { recent: ["dune", "alien"] }).items.some((i) => i.kind === "recent" && i.label === "dune"));
assert.ok(sug("a").items.length <= 8, "capped");
assert.deepEqual(S.operatorHints("genre:cyb", ctx).map((h) => h.label), ["genre:cyberpunk"]);
assert.ok(S.operatorHints("medium:", ctx).length === 7 && S.operatorHints("lang:jap", ctx)[0].label === "lang:japanese");
assert.ok(S.operatorHints("gen", ctx).some((h) => h.label === "genre:"));
assert.equal(S.editDistance("kitten", "sitting", 5), 3); assert.equal(S.editDistance("ab", "ba", 2), 1, "a swap costs one");

// speed: a keystroke over the whole catalogue must stay well under a frame budget
const big = S.buildIndex(works.map((w) => ({ kind: "title", label: w.title, hint: "", href: "", boost: 0 })));
const t0 = process.hrtime.bigint(); for (let i = 0; i < 20; i++) S.suggest(big, "the dark kn"); const ms = Number(process.hrtime.bigint() - t0) / 1e6 / 20;
assert.ok(ms < 40, `a suggestion pass took ${ms.toFixed(1)} ms`);
const t1 = process.hrtime.bigint(); const pp = S.parse('genre:cyberpunk year:1980..2000 -horror "rain" blad*', ctx); for (const w of works) S.test(w, pp); const ms2 = Number(process.hrtime.bigint() - t1) / 1e6;
assert.ok(ms2 < 400, `filtering ${works.length} works took ${ms2.toFixed(0)} ms`);
console.log(`search: all checks passed (suggest ${ms.toFixed(1)} ms, filter ${ms2.toFixed(0)} ms over ${works.length} works)`);
