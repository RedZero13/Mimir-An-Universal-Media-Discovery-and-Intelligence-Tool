// Static, crawlable pages for the catalogue: one per work, one per medium and one per shelf. The app lives at
// "/" behind hash routes, which search engines and link previews can't follow; these pages carry the same facts as
// plain HTML with structured data, and each links into the app ("/#work-<slug>") for the full experience.
"use strict";
const fs = require("fs");
const path = require("path");

const HUBS = [
  { slug: "films", media: ["film"], name: "Films", app: "#films", blurb: "Films from every industry and era, with what each one feels like, how long it takes and a parents' guide." },
  { slug: "tv", media: ["series"], name: "TV shows", app: "#tv", blurb: "Series to binge or savour, with seasons, total watch time, moods and a parents' guide." },
  { slug: "books", media: ["book"], name: "Books & manga", app: "#books", blurb: "Novels, non-fiction, manga and manhwa, with reading time, themes and audiobook lengths." },
  { slug: "games", media: ["game"], name: "Games", app: "#games", blurb: "Games by how they play and how long they last, from one-evening stories to hundred-hour worlds." },
  { slug: "music", media: ["album"], name: "Albums", app: "#albums", blurb: "Albums by mood and moment: for focus, for a long drive, for a rainy window." },
  { slug: "youtube", media: ["channel", "online_video"], name: "YouTube", app: "#youtube", blurb: "Channels and videos worth your time, with what each one makes and what a video covers." },
];
const HUB_OF = Object.fromEntries(HUBS.flatMap((h) => h.media.map((m) => [m, h])));
const MEDIUM_NAME = { film: "Film", series: "TV series", book: "Book", game: "Game", album: "Album", online_video: "YouTube video", channel: "YouTube channel" };
const SCHEMA_TYPE = { film: "Movie", series: "TVSeries", book: "Book", game: "VideoGame", album: "MusicAlbum", online_video: "VideoObject", channel: "CreativeWorkSeries" };
const CREATOR_PROP = { film: "director", series: "creator", book: "author", game: "author", album: "byArtist", online_video: "author", channel: "author" };
const LEAD_ROLES = ["director", "creator", "author", "artist", "developer", "studio", "channel", "host"];

const NOT_MEDIA = new Set(["channel", "online_video"]);
const isCover = (i) => ["cover", "poster", "logo"].includes(i.kind);
const unifiedScore = (w) => (w.scores.length ? Math.round((w.scores.reduce((a, x) => a + x.value / x.scale_max, 0) / w.scores.length) * 100) : null);
const ld = (obj) => `<script type="application/ld+json">${JSON.stringify(obj).replace(/</g, "\\u003c")}</script>`;
// A size near what's shown (the same hosts and sizes the app asks for).
const sized = (url) => url.replace(/(covers\.openlibrary\.org\/.*)-L\.jpg$/, "$1-M.jpg").replace(/\/960px-/, "/500px-").replace("=s900", "=s480");
const clip = (s, n) => (s.length > n ? `${s.slice(0, n - 1).replace(/\s+\S*$/, "")}…` : s);

function writeCatalogPages(out, { cat, works, SITE_URL, staticPage, esc, ipMap = new Map() }) {
  const cardOf = new Map(cat.works.map((c) => [c.slug, c]));
  const urls = [];
  const workUrl = (slug) => `${SITE_URL}/works/${slug}/`;
  const bySlug = new Map(works.map((w) => [w.slug, w]));
  const leads = (w) => {
    const lead = w.credits.filter((c) => LEAD_ROLES.includes(c.role));
    return (lead.length ? lead : w.credits).slice(0, 3);
  };
  const crumbs = (items) => ld({ "@context": "https://schema.org", "@type": "BreadcrumbList",
    itemListElement: items.map(([name, item], i) => ({ "@type": "ListItem", position: i + 1, name, item })) });
  const workLink = (x) => `<a href="/works/${esc(x.slug)}/">${esc(x.title)}</a>${x.year ? ` <span class="meta">(${esc(x.year)})</span>` : ""}`;

  // ------------------------------------------------------------------ similarity: works that share qualities with each other
  // A page with only a summary is thin; "more like this" and the parents' guide are unique to each work and link the catalogue together.
  const QUALITY = /^(genre|mood|theme|narrative|style|world|pacing):/;
  const qualities = (w) => Object.entries(w.terms || {}).filter(([k, v]) => QUALITY.test(k) && v >= 0.6).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([k]) => k);
  const byTerm = new Map(), qOf = new Map();
  for (const w of works) {
    if (!w.summary || NOT_MEDIA.has(w.medium)) continue;
    const q = qualities(w);
    qOf.set(w.slug, q);
    for (const k of q) { if (!byTerm.has(k)) byTerm.set(k, []); byTerm.get(k).push(w); }
  }
  for (const list of byTerm.values()) list.sort((a, b) => (a.popularity_tier || 5) - (b.popularity_tier || 5) || (a.slug < b.slug ? -1 : 1));
  const termWord = (k) => k.split(":")[1].replace(/-/g, " ");
  const similar = (w) => {
    const mine = qOf.get(w.slug);
    if (!mine || mine.length < 2) return { same: [], other: [] };
    const score = new Map();
    for (const k of mine) for (const c of (byTerm.get(k) || []).slice(0, 300)) if (c.slug !== w.slug) score.set(c.slug, (score.get(c.slug) || 0) + (k.startsWith("genre:") ? 1 : 1.5));
    const ranked = [...score].filter(([, n]) => n >= 3).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).map(([slug, n]) => ({ w: bySlug.get(slug), n }));
    const shared = (c) => mine.filter((k) => (qOf.get(c.w.slug) || []).includes(k)).slice(0, 3).map(termWord);
    const pick = (f, n) => ranked.filter(f).slice(0, n).map((c) => ({ ...c.w, shared: shared(c) }));
    return { same: pick((c) => c.w.medium === w.medium, 4), other: pick((c) => c.w.medium !== w.medium, 4) };
  };

  // ------------------------------------------------------------------ one page per work
  for (const card of works) {
    const w = cat.work(card.slug);
    const hub = HUB_OF[w.medium];
    const url = workUrl(w.slug);
    const people = leads(w);
    const cover = w.images.find(isCover) || w.images[0] || null;
    const score = unifiedScore(w);
    const terms = w.tags.flatMap((d) => d.terms.map((t) => ({ ...t, dimension: d.dimension }))).filter((t) => t.strength >= 0.5);
    const genres = terms.filter((t) => t.dimension === "genre").map((t) => t.label);
    const moods = terms.filter((t) => ["mood", "theme"].includes(t.dimension)).slice(0, 8).map((t) => t.label);
    const ratings = (w.parents_guide && w.parents_guide.ratings) || [];
    const kind = MEDIUM_NAME[w.medium] || w.medium;
    const ip = ((cardOf.get(card.slug) || {}).groups || []).map((g) => ({ slug: g.slug, ...ipMap.get(g.slug) })).filter((g) => g.name).sort((a, b) => b.count - a.count)[0];
    const byline = people.map((c) => c.name).join(", ");
    // Search results show about 60 characters of title: put the phrase people search for first, and drop the byline, then the
    // type, before cutting the name itself. "Parents' guide" is promised only where one has been assessed.
    const assessed = !!(w.parents_guide && w.parents_guide.assessed);
    const head = `${w.title}${w.year ? ` (${w.year})` : ""}`;
    const plural = { film: "films", series: "shows", book: "books", game: "games", album: "albums", online_video: "videos", channel: "channels" }[w.medium] || "works";
    // Pages kept out of search (no summary yet) do not advertise a guide in their title either.
    const promise = assessed && !!w.summary && !NOT_MEDIA.has(w.medium);
    const title = (promise
      ? [`${head}: similar ${plural}, parents' guide · Mimir`, `${head}: parents' guide · Mimir`]
      : [`${head} · ${kind}${byline ? ` by ${byline}` : ""} · Mimir`, `${head} · ${kind} · Mimir`]).concat([`${head} · Mimir`]).find((t) => t.length <= 70) || `${clip(head, 61)} · Mimir`;
    const lead = w.summary || `${w.title}${w.year ? ` (${w.year})` : ""} is ${/^[aeiou]/i.test(kind) ? "an" : "a"} ${kind.toLowerCase()}${byline ? ` by ${byline}` : ""}.`;
    const tail = [w.length, genres.slice(0, 3).join(", "), promise ? "Parents' guide and similar picks" : ""].filter(Boolean).join(" · ");
    const desc = clip(`${lead} ${tail}`.trim(), 158);
    const related = [
      ...w.relationships.map((r) => ({ slug: r.slug, title: r.title, year: r.year, label: r.label })),
      ...(w.continuity.members || []).filter((m) => m.slug !== w.slug).map((m) => ({ slug: m.slug, title: m.title, year: m.year, label: w.continuity.group ? `also in ${w.continuity.group.name}:` : "connected:" })),
    ].filter((r, i, all) => bySlug.has(r.slug) && all.findIndex((x) => x.slug === r.slug) === i).slice(0, 12);
    const sameAs = w.links.filter((l) => /^(info|reactions):/.test(l.kind) && /^https:\/\/(en\.wikipedia\.org|www\.imdb\.com|letterboxd\.com|musicbrainz\.org|openlibrary\.org)/.test(l.url)).map((l) => l.url);
    const schema = { "@context": "https://schema.org", "@type": SCHEMA_TYPE[w.medium] || "CreativeWork", name: w.title, url,
      description: w.summary || undefined, inLanguage: w.original_language || undefined,
      datePublished: w.year ? String(w.year) : undefined, image: cover ? cover.url : undefined,
      genre: genres.length ? genres : undefined, keywords: moods.length ? moods.join(", ") : undefined,
      sameAs: sameAs.length ? sameAs : undefined,
      contentRating: ratings.length ? `${ratings[0].system} ${ratings[0].rating}` : undefined };
    if (people.length) schema[CREATOR_PROP[w.medium] || "creator"] = people.map((c) => ({ "@type": c.kind === "organisation" ? "Organization" : "Person", name: c.name }));
    if (w.medium === "film" && w.runtime_minutes) schema.duration = `PT${w.runtime_minutes}M`;
    if (w.medium === "book" && w.page_count) schema.numberOfPages = w.page_count;
    const facts = [
      ["Type", kind],
      w.year && ["Released", w.year],
      byline && [people[0].role ? people[0].role[0].toUpperCase() + people[0].role.slice(1) : "By", byline],
      w.length && ["Length", `${w.length}${w.time && w.time.label ? ` · ${w.time.label}` : ""}`],
      w.original_title && w.original_title !== w.title && ["Original title", w.original_title],
      ratings.length && ["Rated", ratings.map((r) => `${r.system} ${r.rating}`).join(" · ")],
      score !== null && ["Critics' average", `${score}/100 across ${w.scores.length} published score${w.scores.length > 1 ? "s" : ""}`],
    ].filter(Boolean);
    const body = `<p class="eyebrow"><a href="/">Mimir</a> · <a href="/${hub.slug}/">${esc(hub.name)}</a></p>
<h1>${esc(w.title)}</h1>
<p class="meta">${esc([kind, w.year, byline].filter(Boolean).join(" · "))}</p>
${cover ? `<img class="cover" src="${esc(sized(cover.url))}" alt="${esc(w.title)}: ${esc(cover.kind)}" loading="eager" decoding="async" width="240">` : ""}
${w.summary ? `<p class="lede">${esc(w.summary)}</p>` : ""}
<dl class="facts">${facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
${(() => {
      if (NOT_MEDIA.has(w.medium)) return "";
      const pg = w.parents_guide;
      if (!pg || !pg.assessed) return `<h2>Parents' guide</h2><p class="meta">Not assessed yet: nobody has reviewed this ${esc(kind.toLowerCase())} for violence, language, sex or other content, so it should not be treated as suitable for any age.</p>`;
      const rows = pg.groups.filter((g) => g.severity !== "Not assessed");
      return `<h2>Parents' guide</h2>${pg.ratings && pg.ratings.length ? `<p>Rated ${pg.ratings.map((r) => `${esc(r.system)} ${esc(r.rating)}${r.reason ? ` (${esc(r.reason)})` : ""}`).join("; ")}.</p>` : ""}<ul>${rows.map((g) => `<li><strong>${esc(g.label)}:</strong> ${esc(g.severity)}</li>`).join("")}</ul><p class="meta">Levels are an AI-assisted reading awaiting editorial review.</p>`;
    })()}
${(() => {
      const sim = similar(w);
      const li = (x) => `<li><a href="/works/${esc(x.slug)}/">${esc(x.title)}</a>${x.year ? ` <span class="meta">(${esc(x.year)})</span>` : ""} <span class="meta">${esc(MEDIUM_NAME[x.medium] || x.medium)}${x.shared.length ? ` · shares ${esc(x.shared.join(", "))}` : ""}</span></li>`;
      return (sim.same.length ? `<h2>More ${esc(plural)} like ${esc(w.title)}</h2><ul>${sim.same.map(li).join("")}</ul>` : "") + (sim.other.length ? `<h2>In other media</h2><ul>${sim.other.map(li).join("")}</ul>` : "");
    })()}
${ip ? `<p>Part of <a href="/franchises/${esc(ip.slug)}/">${esc(ip.name)} in order</a>: ${ip.count} works across the catalogue.</p>` : ""}
${genres.length ? `<h2>Genres</h2><p>${genres.map(esc).join(" · ")}</p>` : ""}
${moods.length ? `<h2>What it feels like</h2><p>${moods.map(esc).join(" · ")}</p><p class="meta">Tags are an AI-assisted reading awaiting editorial review.</p>` : ""}
${related.length ? `<h2>Connected stories</h2><ul>${related.map((r) => `<li>${esc(r.label[0].toUpperCase() + r.label.slice(1))} ${workLink(r)}</li>`).join("")}</ul>` : ""}
<p><a class="cta" href="/#work-${esc(w.slug)}">Open in Mimir</a><a class="cta ghost" href="/">Find something like this</a></p>`;
    const dir = path.join(out, "works", w.slug);
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(path.join(dir, "index.html"), staticPage(title, desc, url, body,
      ld(schema) + crumbs([["Mimir", `${SITE_URL}/`], [hub.name, `${SITE_URL}/${hub.slug}/`], [w.title, url]]),
      { type: "website", image: cover ? cover.url : undefined, index: !!w.summary, pageType: "ItemPage" }));
    // A work with no summary yet is a thin page: kept out of search until a batch fills it in.
    if (w.summary) urls.push([url, null, "0.6"]);
  }

  // ------------------------------------------------------------------ one page per medium, listing every work
  for (const hub of HUBS) {
    const list = works.filter((w) => hub.media.includes(w.medium)).sort((a, b) => a.title.localeCompare(b.title));
    if (!list.length) continue;
    const url = `${SITE_URL}/${hub.slug}/`;
    const body = `<p class="eyebrow"><a href="/">Mimir</a> · Catalogue</p><h1>${esc(hub.name)}</h1>
<p class="lede">${esc(hub.blurb)}</p><p class="meta">${list.length} in the catalogue. <a href="/${hub.app}">Browse them in Mimir</a>, or ask for something by mood.</p>
<ul class="cols">${list.map((w) => `<li>${workLink(w)}</li>`).join("")}</ul>`;
    fs.mkdirSync(path.join(out, hub.slug), { recursive: true });
    const n100 = `${(Math.floor(list.length / 100) * 100).toLocaleString("en")}+`;
    const HUB_META = {
      films: [`Film directory: browse ${n100} films by mood and genre · Mimir`, "Browse films by genre, mood, country and year, with a parents' guide where one is assessed and links to where to watch."],
      tv: ["TV series directory: shows by mood and genre · Mimir", "Find a TV series by mood, genre or country, with how long it takes to finish and a parents' guide where one is assessed."],
      books: ["Book and manga directory: find what to read next · Mimir", "Browse books and manga by mood and theme, with reading time and a parents' guide where one is assessed."],
      games: ["Game directory: games by mood and time to play · Mimir", "Find a game that fits your time and taste, with how long it takes and where to play."],
      music: ["Albums by mood: find music for how you feel · Mimir", "Albums sorted by feeling, with links to your music app."],
      youtube: ["YouTube channels and videos worth your time · Mimir", "Channels and videos worth your time, with what each one makes and what a video covers."],
    }[hub.slug] || [`${hub.name} · find what to watch, read, play or listen to · Mimir`, `${hub.blurb} ${list.length} picks, each with the reasons it fits.`];
    fs.writeFileSync(path.join(out, hub.slug, "index.html"), staticPage(HUB_META[0], clip(HUB_META[1], 158), url, body,
      ld({ "@context": "https://schema.org", "@type": "CollectionPage", name: hub.name, url, description: hub.blurb,
        mainEntity: { "@type": "ItemList", numberOfItems: list.length, itemListElement: list.slice(0, 100).map((w, i) => ({ "@type": "ListItem", position: i + 1, url: workUrl(w.slug), name: w.title })) } }),
      { type: "website", pageType: null, crumbs: [["Mimir", `${SITE_URL}/`], [hub.name, url]] }));
    urls.push([url, null, "0.8"]);
  }

  // ------------------------------------------------------------------ one page per shelf
  const shelves = cat.shelves();
  const PHRASES = new Map(JSON.parse(fs.readFileSync(path.join(__dirname, "..", "api", "mde", "catalogue", "shelves.json"), "utf8")).shelves.map((x) => [x.slug, x.phrase]));
  for (const sh of shelves) {
    const full = cat.shelf(sh.slug);
    const phrase = PHRASES.get(sh.slug) || "";
    if (!full || !full.works.length) continue;
    const url = `${SITE_URL}/shelves/${sh.slug}/`;
    const body = `<p class="eyebrow"><a href="/">Mimir</a> · <a href="/shelves/">Shelves</a></p><h1>${esc(full.name)}</h1>
<p class="lede">${esc(full.tagline || "")}</p>${phrase ? `<p class="meta">${esc(phrase)}.</p>` : ""}${full.description ? `<p>${esc(full.description)}</p>` : ""}
<ol>${full.works.map((w) => `<li>${workLink(w)} <span class="meta">${esc(MEDIUM_NAME[w.medium] || w.medium)}</span></li>`).join("")}</ol>
<p><a class="cta" href="/#shelf-${esc(sh.slug)}">Open this shelf in Mimir</a></p>`;
    fs.mkdirSync(path.join(out, "shelves", sh.slug), { recursive: true });
    fs.writeFileSync(path.join(out, "shelves", sh.slug, "index.html"), staticPage([`${phrase} (${full.name}) · Mimir`, `${phrase} · Mimir`, `${full.name}: ${phrase} · Mimir`].filter((t) => phrase && t.length <= 70)[0] || `${clip(full.name, 56)} · Mimir`,
      clip(`${phrase ? `${phrase}: ` : ""}${full.tagline || ""} ${full.works.length.toLocaleString("en")} picks across the catalogue, each with the reason it fits.`.trim(), 158), url, body,
      ld({ "@context": "https://schema.org", "@type": "ItemList", name: full.name, url, numberOfItems: full.works.length,
        itemListElement: full.works.map((w, i) => ({ "@type": "ListItem", position: i + 1, url: workUrl(w.slug), name: w.title })) }), { type: "website", pageType: "CollectionPage", crumbs: [["Mimir", `${SITE_URL}/`], ["Shelves", `${SITE_URL}/shelves/`], [full.name, url]] }));
    urls.push([url, null, "0.7"]);
  }
  const shelvesUrl = `${SITE_URL}/shelves/`;
  fs.writeFileSync(path.join(out, "shelves", "index.html"), staticPage("Shelves: hand-picked films, books, games and music · Mimir",
    "Collections across every medium: comfort watches, diamonds in the rough, long hauls and more, each with the rule that fills it.", shelvesUrl,
    `<p class="eyebrow"><a href="/">Mimir</a> · Catalogue</p><h1>Shelves</h1><p class="lede">Collections across every medium, each filled by a stated rule.</p>
<ul class="cards">${shelves.map((sh) => `<li><a href="/shelves/${esc(sh.slug)}/"><h2>${esc(sh.name)}</h2><p>${esc(sh.tagline || "")}</p></a></li>`).join("")}</ul>`, "", { type: "website", pageType: "CollectionPage", crumbs: [["Mimir", `${SITE_URL}/`], ["Shelves", shelvesUrl]] }));
  urls.push([shelvesUrl, null, "0.7"]);
  return urls;
}

module.exports = { writeCatalogPages, HUBS, MEDIUM_NAME };
