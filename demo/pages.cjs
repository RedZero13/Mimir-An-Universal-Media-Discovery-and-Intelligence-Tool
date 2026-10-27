// More static, crawlable pages with real URLs: franchises, tags, people, the Help centre and its guides, the tools, the days
// of the year and the About page. The app keeps its hash routes; each page here carries the same facts as plain HTML and links
// into the app ("/#route") for the interactive version. Nothing is invented: counts, orders and times are computed from the
// catalogue, and the copy for the tools restates what the app itself says each one does.
"use strict";
const fs = require("fs");
const path = require("path");
const help = require("./help.cjs");
const { HUBS, MEDIUM_NAME } = require("./seo.cjs");

const clip = (s, n) => (s.length > n ? `${s.slice(0, n - 1).replace(/\s+\S*$/, "")}…` : s);
const ld = (obj) => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, "\\u003c")}</script>`;
const PLURAL = { film: "films", series: "TV series", book: "books and manga", game: "games", album: "albums", online_video: "YouTube videos", channel: "YouTube channels" };
const MEDIA_ORDER = ["film", "series", "book", "game", "album", "channel", "online_video"];
const NOT_MEDIA = new Set(["channel", "online_video"]);
const hm = (m) => (m >= 60 ? `${Math.round(m / 60)}h${m % 60 && m < 600 ? ` ${m % 60}m` : ""}` : `${m}m`);
const list = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

// Franchises, series outside any franchise, and continuity families with at least two works.
function computeIps(cat) {
  const idx = new Map();
  for (const w of cat.works) for (const g of w.groups) {
    if (!idx.has(g.slug)) idx.set(g.slug, { slug: g.slug, name: g.name, kind: g.kind, members: [] });
    const e = idx.get(g.slug);
    if (!e.members.some((m) => m.slug === w.slug)) e.members.push({ slug: w.slug, position: g.position });
  }
  const covered = new Set([...idx.values()].filter((g) => g.kind === "franchise").flatMap((g) => g.members.map((m) => m.slug)));
  const ips = [...idx.values()].filter((g) => g.members.length >= 2 && (g.kind === "franchise" || !g.members.every((m) => covered.has(m.slug))));
  for (const g of cat.groups()) if (!idx.has(g.slug) && g.count >= 2) ips.push({ slug: g.slug, name: g.name, kind: "family", members: (cat.group(g.slug).works || []).map((w) => ({ slug: w.slug, position: null })) });
  return ips;
}

function writeSitePages(out, { cat, works, SITE_URL, staticPage, esc }) {
  const urls = [];
  const bySlug = new Map(works.map((w) => [w.slug, w]));
  const cardOf = new Map(cat.works.map((w) => [w.slug, w]));
  const timeCache = new Map();
  const minutesOf = (slug) => {
    if (!timeCache.has(slug)) { const t = (cat.work(slug) || {}).time; timeCache.set(slug, t && t.minutes ? t.minutes : 0); }
    return timeCache.get(slug);
  };
  const crumbs = (items) => ld({ "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: items.map(([name, item], i) => ({ "@type": "ListItem", position: i + 1, name, item })) });
  const T = (main) => `${clip(main, 52)} · Mimir`;
  // Structured data by section: index and listing pages are CollectionPages, About is an AboutPage, each tool is also a WebApplication.
  // Breadcrumbs are only added where the page does not already carry its own.
  const SECTION = { franchises: "Franchises", tags: "Tags", people: "People", days: "Days", help: "Help centre", tools: "Tools" };
  const schemaFor = (rel, title) => {
    const [sec, sub] = rel.split("/");
    const name = title.replace(/ · Mimir$/, "");
    if (sec === "about") return { pageType: "AboutPage", crumbs: [["Mimir", `${SITE_URL}/`], ["About", `${SITE_URL}/about/`]] };
    const secName = SECTION[sec] || name;
    const crumbs = sub ? null : [["Mimir", `${SITE_URL}/`], [secName, `${SITE_URL}/${sec}/`]];
    if (sec === "tools" && sub) return { pageType: "WebPage", crumbs, app: name.split(":")[0] };
    if (sec === "help" && sub && !help.HELP.some((a) => a[0] === sub)) return { pageType: "CollectionPage", crumbs };
    if (sec === "help" && sub) return { pageType: "WebPage", crumbs };
    return { pageType: sub && sec !== "days" && sec !== "franchises" && sec !== "tags" && sec !== "people" ? "WebPage" : "CollectionPage", crumbs };
  };
  const write = (rel, title, desc, body, extra = "", { index = true, priority = "0.5", lastmod = null } = {}) => {
    const dir = path.join(out, rel);
    fs.mkdirSync(dir, { recursive: true });
    const url = `${SITE_URL}/${rel}/`;
    fs.writeFileSync(path.join(dir, "index.html"), staticPage(title, clip(desc, 158), url, body, extra, { type: "website", index, ...schemaFor(rel, title) }));
    if (index) urls.push([url, lastmod, priority]);
    return url;
  };
  const head = (crumbHtml, h1, lede) => `<p class="eyebrow">${crumbHtml}</p><h1>${esc(h1)}</h1>${lede ? `<p class="lede">${esc(lede)}</p>` : ""}`;
  const workLi = (slug, extra = "") => {
    const w = cardOf.get(slug) || bySlug.get(slug);
    return w ? `<li><a href="/works/${esc(slug)}/">${esc(w.title)}</a>${w.year ? ` <span class="meta">(${esc(w.year)})</span>` : ""} <span class="meta">${esc(MEDIUM_NAME[w.medium] || w.medium)}${extra}</span></li>` : "";
  };
  const itemList = (name, slugs, url) => ld({ "@context": "https://schema.org", "@type": "ItemList", name, url, numberOfItems: slugs.length,
    itemListElement: slugs.slice(0, 100).map((s, i) => ({ "@type": "ListItem", position: i + 1, url: `${SITE_URL}/works/${s}/`, name: (cardOf.get(s) || {}).title })) });
  const appLink = (route, label) => `<p><a class="cta" href="/#${esc(route)}">${esc(label)}</a><a class="cta ghost" href="/">Ask Mimir for a pick</a></p>`;

  // ------------------------------------------------------------------ franchises and series: one page per IP
  const ips = computeIps(cat);
  const posNum = (p) => (p !== null && p !== undefined && !isNaN(Number(p)) ? Number(p) : 1e9);
  const ipPages = [];
  for (const g of ips) {
    const members = g.members.filter((m) => cardOf.has(m.slug)).map((m) => ({ ...cardOf.get(m.slug), position: m.position }))
      .sort((a, b) => posNum(a.position) - posNum(b.position) || (a.year || 9999) - (b.year || 9999) || a.title.localeCompare(b.title));
    if (members.length < 2) continue;
    const media = MEDIA_ORDER.filter((m) => members.some((w) => w.medium === m));
    const mins = members.reduce((a, w) => a + minutesOf(w.slug), 0), unknown = members.filter((w) => !minutesOf(w.slug)).length;
    const counts = media.map((m) => { const n = members.filter((w) => w.medium === m).length; return `${n} ${n === 1 ? ({ film: "film", series: "TV series", book: "book", game: "game", album: "album", channel: "YouTube channel", online_video: "YouTube video" })[m] : PLURAL[m]}`; });
    const mediaWords = list(media.map((m) => ({ film: "films", series: "shows", book: "books", game: "games", album: "music", channel: "channels", online_video: "videos" })[m]));
    const byRelease = [...members].sort((a, b) => (a.year || 9999) - (b.year || 9999) || a.title.localeCompare(b.title));
    const hasOrder = members.some((w) => w.position !== null && w.position !== undefined && g.kind === "series");
    const rel = `franchises/${g.slug}`;
    const kind = g.kind === "franchise" || media.length > 1 ? "franchise" : "series";
    const lede = `${g.name} is a ${kind} with ${members.length} works in Mimir's catalogue: ${list(counts)}. Here they are in release order${hasOrder ? ", with the series order where it is recorded" : ""}${mins ? `. Everything with a recorded length takes about ${hm(mins)}` : ""}${unknown ? ` (${unknown} ${unknown === 1 ? "work has" : "works have"} no recorded length)` : ""}.`;
    const section = (title, ws, note = "") => `<h2>${esc(title)}</h2>${note ? `<p class="meta">${esc(note)}</p>` : ""}<ol>${ws.map((w) => workLi(w.slug, w.position && g.kind === "series" ? ` · no. ${esc(w.position)}` : "")).join("")}</ol>`;
    const body = `${head(`<a href="/">Mimir</a> · <a href="/franchises/">Franchises &amp; series</a>`, `${g.name} in order`, lede)}
${section("Release order", byRelease, "Every work, oldest first.")}
${media.length > 1 ? media.map((m) => section(PLURAL[m][0].toUpperCase() + PLURAL[m].slice(1), members.filter((w) => w.medium === m), hasOrder ? "In series order where recorded, then by release." : "By release.")).join("") : ""}
${appLink(`group-${g.slug}`, `Open ${g.name} in Mimir`)}`;
    const url = write(rel, T(`${g.name} in order: ${mediaWords}`), `${g.name} in order: ${list(counts)}, with release order${mins ? ` and the time to finish (${hm(mins)})` : ""}. Parents' guides and reasons in Mimir.`,
      body, itemList(`${g.name} in order`, byRelease.map((w) => w.slug), `${SITE_URL}/${rel}/`) + crumbs([["Mimir", `${SITE_URL}/`], ["Franchises & series", `${SITE_URL}/franchises/`], [g.name, `${SITE_URL}/${rel}/`]]),
      { index: members.length >= 3, priority: members.length >= 6 ? "0.8" : "0.6" });
    ipPages.push({ g, members, url, media });
  }
  ipPages.sort((a, b) => b.members.length - a.members.length || a.g.name.localeCompare(b.g.name));
  write("franchises", "Franchises and series in order · Mimir", `Every franchise and series in the catalogue, from ${ipPages[0] ? ipPages[0].g.name : "the biggest"} down, each with its films, shows, books, games and music in order.`,
    `${head(`<a href="/">Mimir</a> · Catalogue`, "Franchises and series, in order", `${ipPages.length} franchises and series with two or more works, each as one page with every medium and the time to finish.`)}
<ul class="cols">${ipPages.map((p) => `<li><a href="/franchises/${esc(p.g.slug)}/">${esc(p.g.name)}</a> <span class="meta">${p.members.length}${p.media.length > 1 ? ` · ${p.media.length} media` : ""}</span></li>`).join("")}</ul>${appLink("series", "Open Sagas in Mimir")}`,
    crumbs([["Mimir", `${SITE_URL}/`], ["Franchises & series", `${SITE_URL}/franchises/`]]), { priority: "0.8" });

  // ------------------------------------------------------------------ tags: one page per genre, mood, theme and other quality
  const tagPages = [];
  const SKIP_DIM = new Set(["advisory"]);
  for (const dim of cat.tags()) {
    if (SKIP_DIM.has(dim.dimension)) continue;
    for (const t of dim.terms) {
      if (t.count < 8) continue;
      const full = cat.tag(t.key);
      if (!full) continue;
      const slug = t.key.replace(":", "-");
      const ws = full.works.filter((w) => !NOT_MEDIA.has(w.medium)).sort((a, b) => Number(!!b.summary) - Number(!!a.summary) || (a.title < b.title ? -1 : 1)).slice(0, 60);
      const mediaN = MEDIA_ORDER.filter((m) => !NOT_MEDIA.has(m)).map((m) => [m, full.works.filter((w) => w.medium === m).length]).filter(([, n]) => n);
      const dimWord = dim.dimension === "genre" ? "genre" : dim.dimension === "mood" ? "mood" : dim.dimension === "theme" ? "theme" : dim.dimension_label ? dim.label.toLowerCase() : dim.dimension;
      const lede = `${t.label} is a ${dimWord} in Mimir's catalogue: ${t.count.toLocaleString("en")} works across ${list(mediaN.map(([m, n]) => `${n} ${PLURAL[m]}`))}. ${full.definition || ""}`.trim();
      const body = `${head(`<a href="/">Mimir</a> · <a href="/tags/">Tags</a>`, `${t.label}: ${dimWord === "genre" ? "films, shows, books, games and music" : `works with a ${t.label.toLowerCase()} ${dimWord}`}`, lede)}
<p class="meta">Tags are an AI-assisted reading awaiting editorial review. ${ws.length < full.works.length ? `Showing ${ws.length} of ${t.count}.` : ""}</p>
<ol>${ws.map((w) => workLi(w.slug)).join("")}</ol>${appLink(`tag-${t.key.replace(":", ".")}`, `Browse ${t.label} in Mimir`)}`;
      write(`tags/${slug}`, T(`${t.label}: ${dimWord === "genre" ? "films, shows, books, games" : `${dimWord} picks`}`), `${t.label} ${dimWord}: ${t.count.toLocaleString("en")} works across ${list(mediaN.map(([m]) => PLURAL[m]))}. ${full.definition || ""}`, body,
        itemList(t.label, ws.map((w) => w.slug), `${SITE_URL}/tags/${slug}/`) + crumbs([["Mimir", `${SITE_URL}/`], ["Tags", `${SITE_URL}/tags/`], [t.label, `${SITE_URL}/tags/${slug}/`]]), { priority: dim.dimension === "genre" ? "0.6" : "0.5" });
      tagPages.push({ dim: dim.label, key: t.key, label: t.label, slug, count: t.count });
    }
  }
  write("tags", "Tags: genres, moods and themes · Mimir", `Browse the catalogue by genre, mood, theme and more: ${tagPages.length} tags, each with the works that carry it.`,
    `${head(`<a href="/">Mimir</a> · Catalogue`, "Tags: genres, moods and themes", "Every tag with at least eight works. Moods, themes and subgenres are AI-assisted readings awaiting editorial review.")}
${cat.tags().filter((d) => !SKIP_DIM.has(d.dimension)).map((d) => { const ts = tagPages.filter((t) => t.dim === d.label); return ts.length ? `<h2>${esc(d.label)}</h2><ul class="cols">${ts.map((t) => `<li><a href="/tags/${esc(t.slug)}/">${esc(t.label)}</a> <span class="meta">${t.count}</span></li>`).join("")}</ul>` : ""; }).join("")}
${appLink("tags", "Open Tags in Mimir")}`, crumbs([["Mimir", `${SITE_URL}/`], ["Tags", `${SITE_URL}/tags/`]]), { priority: "0.6" });

  // ------------------------------------------------------------------ people with several works
  const people = cat.people().filter((p) => p.count >= 5).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name)).slice(0, 400);
  for (const p of people) {
    const full = cat.person(p.slug);
    if (!full) continue;
    const ws = full.works.filter((w) => !NOT_MEDIA.has(w.medium)).sort((a, b) => (a.year || 9999) - (b.year || 9999)).slice(0, 80);
    if (ws.length < 5) continue;
    const roles = (p.roles || []).slice(0, 4).join(", ");
    const body = `${head(`<a href="/">Mimir</a> · <a href="/people/">People &amp; studios</a>`, p.name, `${p.name} is credited${roles ? ` as ${roles}` : ""} on ${p.count} works in Mimir's catalogue, listed here by release year.`)}
<ol>${ws.map((w) => workLi(w.slug)).join("")}</ol>${appLink(`person-${p.slug}`, `Open ${p.name} in Mimir`)}`;
    write(`people/${p.slug}`, T(`${p.name}: films, shows, books, games`), `${p.name}: ${p.count} works${roles ? ` as ${roles}` : ""}, by release year, with parents' guides and reasons in Mimir.`, body,
      itemList(p.name, ws.map((w) => w.slug), `${SITE_URL}/people/${p.slug}/`) + crumbs([["Mimir", `${SITE_URL}/`], ["People & studios", `${SITE_URL}/people/`], [p.name, `${SITE_URL}/people/${p.slug}/`]]), { priority: "0.3" });
  }
  write("people", "People and studios in the catalogue · Mimir", "Directors, authors, artists, developers and studios with five or more works in the Mimir catalogue.",
    `${head(`<a href="/">Mimir</a> · Catalogue`, "People and studios", `The ${people.length} people and studios credited on the most works, from the catalogue's open-data credits.`)}
<ul class="cols">${people.map((p) => `<li><a href="/people/${esc(p.slug)}/">${esc(p.name)}</a> <span class="meta">${p.count}</span></li>`).join("")}</ul>${appLink("people", "Open People in Mimir")}`,
    crumbs([["Mimir", `${SITE_URL}/`], ["People & studios", `${SITE_URL}/people/`]]), { priority: "0.4" });

  // ------------------------------------------------------------------ the Help centre
  const feedback = "mailto:hello@terratalesmedia.world?subject=Mimir%20feedback";
  const helpHref = (html) => html.replace(/\{\{feedback\}\}/g, feedback).replace(/href="#help-([a-z0-9-]+)"/g, 'href="/help/$1/"').replace(/href="#help"/g, 'href="/help/"')
    .replace(/href="#([^"]*)"/g, 'href="/#$1"').replace(/href="\/#"/g, 'href="/"');
  const catPage = (c) => `help/${c[0]}`;
  const faqLd = ld({ "@context": "https://schema.org", "@type": "FAQPage", mainEntity: help.HELP_FAQ.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) });
  write("help", "Help centre: how to use Mimir · Mimir", "Guides to every part of Mimir, answers to common questions and a short walkthrough video.",
    `${head(`<a href="/">Mimir</a>`, "Help centre", "Guides to every part of Mimir, answers to common questions and a short walkthrough video.")}
${help.HELP_CATS.map((c) => `<h2><a href="/${catPage(c)}/">${esc(c[1])}</a></h2><p class="meta">${esc(c[2])}</p><ul>${help.HELP.filter((a) => a[1] === c[0]).map((a) => `<li><a href="/help/${esc(a[0])}/">${esc(a[2])}</a>: ${esc(a[3])}</li>`).join("")}</ul>`).join("")}
<h2>Frequently asked questions</h2>${help.HELP_FAQ.map(([q, a]) => `<h3>${esc(q)}</h3><p>${esc(a)}</p>`).join("")}
<p><a class="cta" href="/#help">Open the Help centre in Mimir</a></p>`, faqLd + crumbs([["Mimir", `${SITE_URL}/`], ["Help centre", `${SITE_URL}/help/`]]), { priority: "0.7" });
  for (const c of help.HELP_CATS) {
    write(catPage(c), T(`${c[1]}: Mimir help`), c[2], `${head(`<a href="/">Mimir</a> · <a href="/help/">Help centre</a>`, c[1], c[2])}<ul>${help.HELP.filter((a) => a[1] === c[0]).map((a) => `<li><a href="/help/${esc(a[0])}/">${esc(a[2])}</a>: ${esc(a[3])}</li>`).join("")}</ul>`,
      crumbs([["Mimir", `${SITE_URL}/`], ["Help centre", `${SITE_URL}/help/`], [c[1], `${SITE_URL}/${catPage(c)}/`]]), { priority: "0.5" });
  }
  for (const a of help.HELP) {
    const c = help.HELP_CATS.find((x) => x[0] === a[1]);
    const more = help.HELP.filter((x) => x[1] === a[1] && x[0] !== a[0]);
    write(`help/${a[0]}`, T(a[2]), a[3], `${head(`<a href="/">Mimir</a> · <a href="/help/">Help centre</a> · <a href="/${catPage(c)}/">${esc(c[1])}</a>`, a[2], a[3])}
${helpHref(a[4])}${more.length ? `<h2>More in ${esc(c[1])}</h2><ul>${more.map((x) => `<li><a href="/help/${esc(x[0])}/">${esc(x[2])}</a></li>`).join("")}</ul>` : ""}
<p><a class="cta ghost" href="/#help-${esc(a[0])}">Open this guide in Mimir</a></p>`,
      crumbs([["Mimir", `${SITE_URL}/`], ["Help centre", `${SITE_URL}/help/`], [c[1], `${SITE_URL}/${catPage(c)}/`], [a[2], `${SITE_URL}/help/${a[0]}/`]]), { priority: "0.5" });
  }

  // ------------------------------------------------------------------ the tools: each restates what the app says it does
  const TOOLS = [
    ["decide", "decide", "Decide for me", "One pick, not a hundred", "Answer three quick questions and Mimir picks one thing for right now, with its reasons. Not feeling it? Say why and it picks again.",
      ["Say how much time you have and what you are in the mood for.", "Mimir returns one pick with the reasons it fits, marked as recorded fact or editorial reading.", "Not feeling it? Tell it why and it picks again."], "what to watch tonight"],
    ["swipe", "swipe", "Swipe", "Swipe to find your taste", "Right to like, up to love, left for not for me, down to skip what you haven't seen. Each swipe shapes your picks everywhere in Mimir. Arrow keys work too.",
      ["Go through cards of films, shows, books, games and music.", "Swipe right to like, up to love, left for not for me, or down to skip what you haven't seen.", "After a few cards, open For you to see picks built from your swipes."], "taste finder"],
    ["spin", "spin", "Spin a mood", "Pick a mood, we'll pick the title", "Right or Enter to spin, left to try another mood. The posters spin like a slot machine, land on one, and open it after a short countdown.",
      ["Choose a mood.", "Spin: the posters turn like a slot machine and land on one.", "Mimir opens that title after a short countdown."], "random picker"],
    ["craft", "craft", "Craft", "Mix and match your way to a recommendation", "Click or drag pieces onto the table, then drop one on another, or tap two and press Combine. Works, moods, genres and mediums blend into something new, and Mimir finds the pick that fits it best. Every blend you discover is kept, and can be combined again.",
      ["Click or drag pieces onto the table: works, moods, genres and mediums.", "Combine two pieces into a hybrid with its own name.", "Mimir finds the pick that fits the hybrid best. Every blend you discover is kept."], "mood mixer"],
    ["mix", "mix", "Mood mixer", "Mix the feeling you're after", "Tap a quality once to want it, twice to avoid it. \"Melancholic but comforting\", \"challenging without being bleak\": Mimir looks for works that hold every part of the mix.",
      ["Tap a quality once to want it, twice to avoid it.", "Combine as many as you like.", "Mimir looks for works that hold every part of the mix."], "feeling finder"],
    ["plan", "plan", "Plan my time", "A plan that fits the time you have", "Pick a time budget. Mimir fills it from what you've started and planned first, then from picks for you, and lays it out day by day. It all stays in this browser.",
      ["Pick a time budget.", "Mimir fills it with what you've started and planned, then picks for you.", "It lays the plan out day by day, kept in this browser."], "watch list planner"],
    ["together", "together", "Pick together", "Something everyone will enjoy", "Add each person and a few things they love, and tick what they'd rather avoid. Mimir favours picks that suit everyone over picks one person adores, and says where the compromise is. Nothing leaves this browser.",
      ["Add each person and a few things they love.", "Tick what anyone would rather avoid.", "Mimir favours picks that suit everyone and says where the compromise is."], "group movie night"],
    ["taste", "taste", "Your taste profile", "Your taste profile", "Worked out from the works you've rated or scored, and editable: ask for more or less of any quality, or never see it again. It all stays in this browser and shapes your picks.",
      ["Rate or score works you know.", "See which qualities Mimir reads in your taste, and edit them.", "Ask for more or less of any quality, or never see it again."], "taste profile"],
    ["compare", "compare", "Compare", "Compare two works", "Pick any work, in any medium. Mimir lines them up by length, scores, popularity, mood, themes, style and the parents' guide.",
      ["Pick a work, in any medium.", "Pick another to set beside it.", "See length, scores, popularity, mood, themes, style and the parents' guide side by side."], "compare films and books"],
  ];
  for (const [slug, route, name, h1, what, steps] of TOOLS) {
    write(`tools/${slug}`, T(`${name}: ${h1}`), what, `${head(`<a href="/">Mimir</a> · <a href="/tools/">Tools</a>`, name, what)}
<h2>How it works</h2><ol>${steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>
<p class="meta">Everything stays in your browser unless you create an account. Picks come from a catalogue of ${cat.works.length.toLocaleString("en")} works across films, TV, books, games and music, and every reason shown says whether it is a recorded fact or an editorial reading.</p>
${appLink(route, `Open ${name} in Mimir`)}`, crumbs([["Mimir", `${SITE_URL}/`], ["Tools", `${SITE_URL}/tools/`], [name, `${SITE_URL}/tools/${slug}/`]]), { priority: "0.7" });
  }
  write("tools", "Tools to pick what to watch, read or play · Mimir", "Decide for me, Swipe, Spin, Craft, the mood mixer, Plan my time, Pick together and more: ways to choose what to watch, read, play or listen to next.",
    `${head(`<a href="/">Mimir</a>`, "Tools to choose what's next", "Nine ways to get from \"I can't decide\" to a pick, in every medium.")}
<ul class="cards">${TOOLS.map(([slug, , name, , what]) => `<li><a href="/tools/${slug}/"><h2>${esc(name)}</h2><p>${esc(what)}</p></a></li>`).join("")}</ul>`, crumbs([["Mimir", `${SITE_URL}/`], ["Tools", `${SITE_URL}/tools/`]]), { priority: "0.8" });

  // ------------------------------------------------------------------ days of the year
  const obs = JSON.parse(fs.readFileSync(path.join(path.dirname(__filename), "..", "api", "mde", "catalogue", "observances.json"), "utf8")).days;
  const year = new Date().getUTCFullYear();
  const nth = (y, m, wd, n) => { const first = new Date(Date.UTC(y, m - 1, 1)); return new Date(Date.UTC(y, m - 1, 1 + ((wd - first.getUTCDay() + 7) % 7) + 7 * (n - 1))); };
  const dateOf = (o) => (o.nth ? nth(year, ...o.nth) : new Date(Date.UTC(year, Number(o.date.slice(0, 2)) - 1, Number(o.date.slice(3, 5)))));
  const dateText = (d) => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  const KIND = { un: "UN day", unesco: "UNESCO day", observed: "Widely observed", informal: "Popular, unofficial" };
  const pool = (o) => {
    const r = o.rule || {}, floor = r.min_strength !== undefined ? r.min_strength : 0.6;
    return works.filter((w) => {
      if (r.media ? !r.media.includes(w.medium) : NOT_MEDIA.has(w.medium)) return false;
      if (r.not_languages && (!w.language || r.not_languages.includes(w.language))) return false;
      if (r.year_max && !(w.year && w.year <= r.year_max)) return false;
      if (r.any_tags && !r.any_tags.some((k) => ((w.terms || {})[k] || 0) >= floor && (w.terms || {})[k] !== undefined)) return false;
      return !!w.summary;
    }).sort((a, b) => (a.popularity_tier || 5) - (b.popularity_tier || 5) || (a.title < b.title ? -1 : 1)).slice(0, 18);
  };
  const days = obs.map((o) => ({ ...o, on: dateOf(o) })).sort((a, b) => a.on - b.on || a.name.localeCompare(b.name));
  for (const o of days) {
    const picks = pool(o);
    const body = `${head(`<a href="/">Mimir</a> · <a href="/days/">Days of the year</a>`, o.name, `${o.about} ${o.why}`)}
<p class="meta">${esc(dateText(o.on))} ${year} · ${esc(KIND[o.kind] || "")}</p>
${o.tone === "reflective" ? `<p class="meta">A day of reflection: some picks deal with difficult subjects. Each work's page says what to expect where its parents' guide has been assessed.</p>` : ""}
${picks.length ? `<h2>Picks for ${esc(o.name)}</h2><ol>${picks.map((w) => workLi(w.slug)).join("")}</ol>` : ""}
<p class="meta">Chosen from the catalogue's own tags. Mimir's version of this page also shows something new to discover and picks drawn from your own ratings.</p>
${appLink(`day-${o.slug}?y=${year}`, `Open ${o.name} in Mimir`)}`;
    write(`days/${o.slug}`, T(`${o.name}: what to watch, read and play`), `${o.name} (${dateText(o.on)}): ${o.why}`, body,
      (picks.length ? itemList(o.name, picks.map((w) => w.slug), `${SITE_URL}/days/${o.slug}/`) : "") + crumbs([["Mimir", `${SITE_URL}/`], ["Days of the year", `${SITE_URL}/days/`], [o.name, `${SITE_URL}/days/${o.slug}/`]]), { priority: "0.4" });
  }
  write("days", `Days of the year ${year}: what to watch, read and play · Mimir`.replace(/^(.{0,62}).*( · Mimir)$/, "$1$2"), `${days.length} days of the year, from World Laughter Day to International Day of Education, each with films, shows, books and music to match.`,
    `${head(`<a href="/">Mimir</a> · Calendar`, `Days of the year, ${year}`, `${days.length} observances with something to watch, read, play or listen to for each. Dates follow the lists kept by the UN, UNESCO and the bodies that set each day; popular but unofficial days are marked.`)}
${MONTHS.map((m, i) => { const ds = days.filter((d) => d.on.getUTCMonth() === i); return ds.length ? `<h2>${m}</h2><ul>${ds.map((d) => `<li><a href="/days/${esc(d.slug)}/">${esc(d.name)}</a> <span class="meta">${esc(dateText(d.on))}${d.kind === "informal" ? " · unofficial" : ""}</span></li>`).join("")}</ul>` : ""; }).join("")}
${appLink(`days?y=${year}`, "Open Days of the year in Mimir")}`, crumbs([["Mimir", `${SITE_URL}/`], ["Days of the year", `${SITE_URL}/days/`]]), { priority: "0.6" });

  // ------------------------------------------------------------------ about
  const countries = new Set(works.flatMap((w) => w.countries || [])).size, languages = new Set(works.map((w) => w.language).filter(Boolean)).size;
  write("about", "About Mimir: a media discovery guide · Mimir", "What Mimir is, what the catalogue holds, where its facts come from and what is an AI-assisted reading.",
    `${head(`<a href="/">Mimir</a>`, "About Mimir", "Mimir is a free guide that helps you decide what to watch, read, play or listen to next, with the reason for every pick.")}
<h2>What it holds</h2><p>${works.length.toLocaleString("en")} works from ${countries} countries in ${languages} original languages: films, TV series, books and manga, games, albums and YouTube channels. Each has how long it takes, a parents' guide where one has been assessed, and where to find it.</p>
<h2>Where the facts come from</h2><p>Titles, years, creators and lengths come from open data such as Wikidata, Open Library and MusicBrainz where a source matches, and each page says which. Where nothing matches, facts are the editors' and unverified.</p>
<h2>What is an interpretation</h2><p>Moods, themes, subgenres and parents' guide levels are AI-assisted readings awaiting editorial review, and are labelled where they appear. "Not assessed" means no one has assessed it yet. Mimir finds its picks without a large language model: your request becomes inspectable constraints, ranked against the classified catalogue.</p>
<h2>Who makes it</h2><p>Mimir is a venture of <a href="https://terratalesmedia.world/">Terratales Media Entertainment</a>. It is in public beta. Your library stays in your browser unless you create an account, which is encrypted so Mimir cannot read it. See the <a href="/privacy/">privacy notice</a>.</p>
${appLink("about", "Open About in Mimir")}`, crumbs([["Mimir", `${SITE_URL}/`], ["About", `${SITE_URL}/about/`]]), { priority: "0.6" });

  return { urls, ips: ipPages.length, tags: tagPages.length, people: people.length, days: days.length, help: help.HELP.length };
}

module.exports = { writeSitePages, computeIps };
