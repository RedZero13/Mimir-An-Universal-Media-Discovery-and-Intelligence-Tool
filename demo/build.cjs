// Builds Mimir's single-page site: page.html with the engine, pilot data and brand assets inlined.
//
//   node demo/build.cjs [out.html]     body-only page (for previews that supply their own document shell)
//   node demo/build.cjs --site [dir]   deployable static site (default: demo/dist/site): index.html with a full
//                                      <head>, favicons, social card, web manifest, robots.txt and CNAME
"use strict";
const fs = require("fs");
const { readSeed } = require("./seed.cjs");
const { writeCatalogPages, HUBS } = require("./seo.cjs");
const path = require("path");

const here = __dirname;
const root = path.join(here, "..");
const api = path.join(root, "api", "mde");
const brand = path.join(root, "brand");

const SITE_URL = "https://mimir.terratalesmedia.world";
const HOST = new URL(SITE_URL).host;

// Inline JSON/JS must not be able to close the <script> element early.
const safe = (s) => s.replace(/<\/(script)/gi, "<\\/$1");
const json = (p) => safe(JSON.stringify(JSON.parse(fs.readFileSync(p, "utf8"))));
const dataUri = (p, type) => `data:${type};base64,${fs.readFileSync(p).toString("base64")}`;

// Open-data enrichment written by `python -m mde ingest` (one file per source); empty until fetched.
function enrichment() {
  const dir = path.join(api, "data", "enrichment");
  const out = {};
  if (fs.existsSync(dir)) {
    for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".json") && n !== "review.json").sort()) {
      out[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    }
  }
  return out;
}

// What the site's engine reads from each enrichment record; the rest (match reasons, candidates, Commons pages)
// is for editors and the API, and would only weigh down the download.
function slimEnrichment(all) {
  const pick = (o, keys) => Object.fromEntries(keys.filter((k) => o[k] !== undefined).map((k) => [k, o[k]]));
  const out = {};
  for (const [source, data] of Object.entries(all)) {
    const works = {};
    for (const [slug, rec] of Object.entries(data.works || {})) {
      const slim = pick(rec, ["facts", "ids", "scores", "box_office", "series", "links", "tracks", "key"]);
      if (rec.match) slim.match = rec.match.mbid ? { mbid: rec.match.mbid } : {};
      if (rec.images) slim.images = rec.images.map((i) => pick(i, ["kind", "url", "licence", "attribution"]));
      works[slug] = slim;
    }
    out[source] = { works };
  }
  return out;
}

// The data each page reads, as JSON text by name (the page parses it with DATA(name)).
function dataTexts(slim) {
  const read = (p) => JSON.stringify(JSON.parse(fs.readFileSync(p, "utf8")));
  return {
    taxonomy: read(path.join(api, "taxonomy", "taxonomy.json")),
    catalogue: JSON.stringify(readSeed(path.join(api, "seed"))),
    shelves: read(path.join(api, "catalogue", "shelves.json")),
    enrichment: JSON.stringify(slim ? slimEnrichment(enrichment()) : enrichment()),
    providers: read(path.join(api, "catalogue", "providers.json")),
    calendar: read(path.join(api, "catalogue", "calendar.json")),
    audiobooks: read(path.join(api, "catalogue", "audiobooks.json")),
    // Accounts and community talk to the API at MIMIR_API_URL; without it the site runs on its own, browser-only.
    config: JSON.stringify({ api: (process.env.MIMIR_API_URL || "").replace(/\/$/, "") }),
    blog: read(path.join(here, "blog.json")),
  };
}

function page() {
  return fs.readFileSync(path.join(here, "page.html"), "utf8")
    .replace("/*__TAXONOMY__*/", () => json(path.join(api, "taxonomy", "taxonomy.json")))
    .replace("/*__CATALOGUE__*/", () => safe(JSON.stringify(readSeed(path.join(api, "seed")))))
    .replace("/*__PROVIDERS__*/", () => json(path.join(api, "catalogue", "providers.json")))
    .replace("/*__SHELVES__*/", () => json(path.join(api, "catalogue", "shelves.json")))
    .replace("/*__CALENDAR__*/", () => json(path.join(api, "catalogue", "calendar.json")))
    .replace("/*__AUDIOBOOKS__*/", () => json(path.join(api, "catalogue", "audiobooks.json")))
    .replace("/*__BLOG__*/", () => json(path.join(here, "blog.json")))
    // Accounts and community talk to the API at MIMIR_API_URL; without it the site runs on its own, browser-only.
    .replace("/*__CONFIG__*/", () => safe(JSON.stringify({ api: (process.env.MIMIR_API_URL || "").replace(/\/$/, "") })))
    .replace("/*__ENRICHMENT__*/", () => safe(JSON.stringify(enrichment())))
    .replace("/*__ENGINE__*/", () => safe(fs.readFileSync(path.join(here, "engine.cjs"), "utf8")))
    .replace("/*__SEAL__*/", () => dataUri(path.join(brand, "terratales-seal-64.png"), "image/png"));
}

// Inter sets the hero's lead paragraph, usually the largest text on a phone: fetch it first.
const FONT_HEAD = `<link rel="preload" as="font" type="font/woff2" href="/fonts/inter-latin.woff2" crossorigin fetchpriority="high">
<style>${fs.readFileSync(path.join(here, "fonts", "fonts.css"), "utf8")}</style>`;

// The deployed page: data and code move to content-hashed files loaded after the first paint, so the HTML (styles and
// the static hero) paints at once, and a returning visitor's browser or service worker reuses the files until they change.
function sitePage(out) {
  const hash = (s) => require("crypto").createHash("sha256").update(s).digest("hex").slice(0, 10);
  const texts = dataTexts(true);
  const works = JSON.parse(texts.catalogue).works.length;
  let html = fs.readFileSync(path.join(here, "page.html"), "utf8")
    .replace(/<script id="[a-z]+-data" type="application\/json">\/\*__[A-Z]+__\*\/<\/script>\n/g, "")
    .replace("/*__SEAL__*/", () => dataUri(path.join(brand, "terratales-seal-64.png"), "image/png"))
    .replace('<span class="pilot" id="beta-pill">Beta</span>', `<span class="pilot" id="beta-pill">Beta · ${works} works</span>`)
    .replace('<span id="cat-count">hundreds of</span>', `<span id="cat-count">${works}</span>`);
  // Self-hosted fonts in place of Google Fonts: no third-party connections before the first paint.
  html = html.replace(/<link rel="preconnect" href="https:\/\/fonts\.(googleapis|gstatic)\.com"( crossorigin)?>\n/g, "")
    .replace(/<link rel="preload" as="style" href="https:\/\/fonts\.googleapis\.com[^\n]*\n<noscript>[^\n]*<\/noscript>/, FONT_HEAD);
  const start = html.indexOf("<script>/*__ENGINE__*/</script>");
  const main = html.slice(html.indexOf("<script>\n", start + 10) + 9, html.lastIndexOf("</script>"));
  const dataJs = `window.MIMIR_DATA=${JSON.stringify(texts)};\n`;
  const appJs = `${fs.readFileSync(path.join(here, "engine.cjs"), "utf8")}\n;\n${main}`;
  const files = { [`assets/data.${hash(dataJs)}.js`]: dataJs, [`assets/app.${hash(appJs)}.js`]: appJs };
  fs.rmSync(path.join(out, "assets"), { recursive: true, force: true });
  fs.mkdirSync(path.join(out, "assets"), { recursive: true });
  for (const [f, body] of Object.entries(files)) fs.writeFileSync(path.join(out, f), body);
  const [dataFile, appFile] = Object.keys(files);
  // Requested just after the first paint, so on a slow connection the page, its styles and fonts get the bandwidth
  // first; async=false keeps the two in order (data, then the app).
  html = html.slice(0, start) + `<script>requestAnimationFrame(() => setTimeout(() => ${JSON.stringify([`/${dataFile}`, `/${appFile}`])}.forEach((src) => {
  const s = document.createElement("script"); s.src = src; s.async = false; document.body.appendChild(s);
}), 0));</script>\n`;
  return { html: standalone(html), assets: Object.keys(files).map((f) => `/${f}`) };
}

function standalone(html) {
  const [head, body] = html.split("<!--/head-->");
  const extraHead = `
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#131315">
<link rel="canonical" href="${SITE_URL}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="manifest" href="/site.webmanifest">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<meta name="keywords" content="what to watch, what to read, what to play, movie recommendations, TV show recommendations, book recommendations, game recommendations, music recommendations, anime and manga, mood-based recommendations, parents guide, watchlist, reading list, Mimir, Terratales">
<meta name="author" content="Terratales Media Entertainment">
<meta name="application-name" content="Mimir">
<meta property="og:type" content="website">
<meta property="og:locale" content="en_US">
<meta property="og:site_name" content="Mimir · A Terratales Venture">
<meta property="og:title" content="Mimir · Find what to watch, read, play or listen to next">
<meta property="og:description" content="Describe a mood, a favourite or a time limit; Mimir finds films, TV, books, games and music that fit, with the reason for every pick.">
<meta property="og:url" content="${SITE_URL}/">
<meta property="og:image" content="${SITE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Mimir · Find what to watch, read, play or listen to next">
<meta name="twitter:description" content="Films, TV, books, games and music, found by how they feel, with the reason for every pick.">
<meta name="twitter:image" content="${SITE_URL}/og-image.png">
<link rel="alternate" type="application/rss+xml" title="The Mimir blog" href="${SITE_URL}/blog/feed.xml">
<script type="application/ld+json">${JSON.stringify({ "@context": "https://schema.org", "@graph": [
    { "@type": "WebSite", "@id": `${SITE_URL}/#site`, url: `${SITE_URL}/`, name: "Mimir", alternateName: "Mimir · A Terratales Venture",
      description: "Discover and track films, TV, books, manga, games and music by how they feel, with the reason for every pick.",
      publisher: { "@id": "https://terratalesmedia.world/#org" }, inLanguage: "en" },
    { "@type": "WebApplication", name: "Mimir", url: `${SITE_URL}/`, applicationCategory: "EntertainmentApplication", operatingSystem: "Any",
      offers: { "@type": "Offer", price: "0", priceCurrency: "USD" } },
    { "@type": "Organization", "@id": "https://terratalesmedia.world/#org", name: "Terratales Media Entertainment", url: "https://terratalesmedia.world/",
      logo: `${SITE_URL}/icon-512.png`, email: "hello@terratalesmedia.world" },
  ] }).replace(/</g, "\\u003c")}</script>`;
  return `<!doctype html>\n<html lang="en">\n<head>${extraHead}\n${head.trim()}\n</head>\n<body>\n${body.trim()}\n</body>\n</html>\n`;
}

// The blog as static pages (one per post, plus an index) so search engines and link previews can read them; the
// app shows the same posts at #blog. A sitemap lists the home page and every post.
// Static pages (blog, works, hubs, shelves) share one light shell: readable without the app, linked into it.
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const staticPage = (title, desc, canonical, body, extraHead = "", { type = "article", image = `${SITE_URL}/og-image.png`, index = true } = {}) => `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title><meta name="description" content="${esc(desc)}"><meta name="robots" content="${index ? "index, follow, max-image-preview:large" : "noindex, follow"}"><link rel="canonical" href="${canonical}">
<meta property="og:type" content="${type}"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${canonical}"><meta property="og:image" content="${esc(image)}"><meta name="twitter:card" content="summary_large_image"><meta property="og:site_name" content="Mimir · A Terratales Venture">
<meta name="theme-color" content="#EDE3CC"><link rel="icon" href="/favicon.svg" type="image/svg+xml">${extraHead}
<link rel="stylesheet" href="/fonts/fonts.css">
<style>
:root{--bg:#EDE3CC;--surface:#F6F0E2;--ink:#23211C;--head:#131315;--muted:#5F5A4F;--gold:#8A6A18;--line:rgba(110,104,92,.24)}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:300 17px/1.75 Inter,system-ui,sans-serif;padding:0 16px}
a{color:var(--gold);text-underline-offset:3px}.wrap{max-width:720px;margin:0 auto}
header.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:22px 0;border-bottom:1px solid var(--line);max-width:1080px;margin:0 auto}
.brand{font:600 1.2rem Cinzel,serif;letter-spacing:.2em;color:var(--gold);text-decoration:none}.brand small{display:block;font-size:.55rem;letter-spacing:.3em;color:var(--muted)}
.eyebrow{font:600 .7rem Cinzel,serif;letter-spacing:.2em;text-transform:uppercase;color:var(--gold);margin:40px 0 6px}
h1{font:600 clamp(2rem,6vw,3rem)/1.1 "Cormorant Garamond",Georgia,serif;color:var(--head);margin:0 0 8px}
h2{font:600 1.6rem "Cormorant Garamond",Georgia,serif;color:var(--head);margin:32px 0 6px}
.meta{color:var(--muted);font-size:.85rem}.lede{font:italic 500 1.35rem/1.45 "Cormorant Garamond",Georgia,serif;color:#5E4B1C}
.cta{display:inline-block;margin:28px 12px 0 0;padding:12px 22px;border-radius:99px;background:var(--gold);color:#F6F0E2;text-decoration:none;font:600 .75rem Cinzel,serif;letter-spacing:.16em;text-transform:uppercase}
.cta.ghost{background:transparent;color:var(--gold);border:1px solid var(--gold)}
.cards{list-style:none;padding:0;display:grid;gap:14px}.cards a{display:block;padding:18px 20px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);text-decoration:none}
.cards a:hover{border-color:var(--gold)}.cards h2{margin:0 0 4px;font-size:1.35rem}
nav{font-size:.85rem;text-align:right;line-height:1.9}.cover{float:right;width:min(240px,40%);margin:6px 0 16px 20px;border-radius:6px;box-shadow:0 8px 22px rgba(0,0,0,.25)}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:4px 16px;margin:20px 0}.facts dt{color:var(--muted);font-size:.85rem}.facts dd{margin:0}
.cols{columns:2 240px;column-gap:28px;padding-left:18px}.cols li{break-inside:avoid}h1,h2{clear:none}
footer{max-width:1080px;margin:64px auto 0;padding:22px 0 40px;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;display:flex;flex-wrap:wrap;gap:8px 20px;justify-content:space-between}
</style></head><body>
<header class="top"><a class="brand" href="/">MIMIR<small>A TERRATALES VENTURE</small></a><nav>${HUBS.map((h) => `<a href="/${h.slug}/">${h.name}</a>`).join(" · ")} · <a href="/shelves/">Shelves</a> · <a href="/blog/">Blog</a></nav></header>
<main class="wrap">${body}</main>
<footer><span>© 2026 Terratales Media Entertainment · All realms reserved</span><span><a href="/">Mimir</a> · <a href="/blog/">Blog</a> · <a href="https://terratalesmedia.world/" target="_blank" rel="noopener">Terratales</a></span></footer>
</body></html>
`;

function writeBlog(out) {
  const posts = JSON.parse(fs.readFileSync(path.join(here, "blog.json"), "utf8")).posts.sort((a, b) => b.date.localeCompare(a.date));
  const href = (h) => (h === "#" ? "/" : h.startsWith("#") ? `/${h}` : h);
  const inline = (s) => esc(s).replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, h) => `<a href="${esc(href(h))}">${text}</a>`);
  const md = (src) => src.split(/\n\n+/).map((b) => (b.startsWith("## ") ? `<h2>${inline(b.slice(3))}</h2>`
    : b.startsWith("- ") ? `<ul>${b.split("\n").map((l) => `<li>${inline(l.replace(/^- /, ""))}</li>`).join("")}</ul>` : `<p>${inline(b)}</p>`)).join("\n");
  const date = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  fs.mkdirSync(path.join(out, "blog"), { recursive: true });
  fs.writeFileSync(path.join(out, "blog", "index.html"), staticPage("The Mimir blog · Notes from the well",
    "What Mimir can do, how it works, and what's new: discover and track films, TV, books, manga, games and music.", `${SITE_URL}/blog/`,
    `<p class="eyebrow">The Mimir blog</p><h1>Notes from the well</h1><p class="meta">What Mimir can do, how it works, and what's new.</p>
<ul class="cards">${posts.map((b) => `<li><a href="/blog/${b.slug}/"><p class="meta">${esc(b.tags.join(" · "))} · ${date(b.date)}</p><h2>${esc(b.title)}</h2><p>${esc(b.summary)}</p></a></li>`).join("")}</ul>`));
  for (const b of posts) {
    const url = `${SITE_URL}/blog/${b.slug}/`;
    const ld = { "@context": "https://schema.org", "@type": "BlogPosting", headline: b.title, description: b.summary, datePublished: b.date,
      url, image: `${SITE_URL}/og-image.png`, author: { "@type": "Organization", name: "Mimir · Terratales" },
      publisher: { "@type": "Organization", name: "Terratales Media Entertainment", url: "https://terratalesmedia.world/" } };
    fs.mkdirSync(path.join(out, "blog", b.slug), { recursive: true });
    fs.writeFileSync(path.join(out, "blog", b.slug, "index.html"), staticPage(`${b.title} · Mimir`, b.summary, url,
      `<p class="eyebrow"><a href="/blog/">Blog</a> · ${esc(b.tags.join(" · "))}</p><h1>${esc(b.title)}</h1><p class="meta">${date(b.date)} · The Mimir team</p>
<p class="lede">${esc(b.summary)}</p>
${md(b.body)}
<p><a class="cta" href="/">Ask Mimir</a><a class="cta ghost" href="/#decide">Decide for me</a></p>`,
      `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, "\\u003c")}</script>`));
  }
  const xml = (t) => esc(t).replace(/'/g, "&apos;");
  fs.writeFileSync(path.join(out, "blog", "feed.xml"), `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>The Mimir blog</title><link>${SITE_URL}/blog/</link><description>What Mimir can do, how it works, and what's new.</description><language>en</language>
<atom:link href="${SITE_URL}/blog/feed.xml" rel="self" type="application/rss+xml"/>
${posts.map((b) => `<item><title>${xml(b.title)}</title><link>${SITE_URL}/blog/${b.slug}/</link><guid>${SITE_URL}/blog/${b.slug}/</guid><pubDate>${new Date(`${b.date}T12:00:00Z`).toUTCString()}</pubDate><description>${xml(b.summary)}</description></item>`).join("\n")}
</channel></rss>
`);
  return [[`${SITE_URL}/blog/`, posts[0] && posts[0].date, "0.6"], ...posts.map((b) => [`${SITE_URL}/blog/${b.slug}/`, b.date, "0.5"])];
}

const args = process.argv.slice(2);
if (args[0] === "--site") {
  const out = args[1] || path.join(here, "dist", "site");
  fs.mkdirSync(out, { recursive: true });
  const site = sitePage(out);
  fs.writeFileSync(path.join(out, "index.html"), site.html);
  for (const f of ["favicon.svg", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-192.png", "icon-maskable-512.png", "app-icon.svg", "og-image.png"]) {
    fs.copyFileSync(path.join(brand, f), path.join(out, f));
  }
  fs.rmSync(path.join(out, "fonts"), { recursive: true, force: true });
  fs.cpSync(path.join(here, "fonts"), path.join(out, "fonts"), { recursive: true, filter: (f) => !f.endsWith(".md") });
  fs.writeFileSync(path.join(out, "site.webmanifest"), JSON.stringify({
    name: "Mimir · A Terratales Venture", short_name: "Mimir", start_url: "/", scope: "/", display: "standalone",
    description: "Discover and track films, TV, books, manga, games and music, with the reason behind every pick.",
    categories: ["entertainment", "books", "music"],
    background_color: "#EDE3CC", theme_color: "#EDE3CC",
    icons: [{ src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" }, { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" }, { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
      { src: "/app-icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  }, null, 2));
  // Offline support: the service worker's cache name changes with the page, so each deploy replaces the old copy.
  const version = require("crypto").createHash("sha256").update(fs.readFileSync(path.join(out, "index.html"))).digest("hex").slice(0, 12);
  fs.writeFileSync(path.join(out, "sw.js"), fs.readFileSync(path.join(here, "sw.js"), "utf8").replace("__VERSION__", version)
    .replace('"/__ASSETS__"', site.assets.map((a) => JSON.stringify(a)).join(", ")));
  // Static pages for search engines and link previews: the blog, every work, each medium and each shelf.
  const texts = dataTexts(false);
  const MDE = require("./engine.cjs");
  const P = (n) => JSON.parse(texts[n]);
  const cat = MDE.createCatalogue(P("catalogue"), P("taxonomy"), P("enrichment"), P("shelves"), P("providers"), P("calendar"));
  const today = new Date().toISOString().slice(0, 10);
  const urls = [[`${SITE_URL}/`, today, "1.0"], ...writeBlog(out),
    ...writeCatalogPages(out, { cat, works: P("catalogue").works, SITE_URL, staticPage, esc })];
  fs.writeFileSync(path.join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(([u, d, pr]) => `  <url><loc>${u}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}${pr ? `<priority>${pr}</priority>` : ""}</url>`).join("\n")}\n</urlset>\n`);
  // Everything is crawlable, scripts included: search engines render the app with them.
  fs.writeFileSync(path.join(out, "robots.txt"), `# Mimir · ${SITE_URL}\nUser-agent: *\nAllow: /\n\nSitemap: ${SITE_URL}/sitemap.xml\n`);
  fs.writeFileSync(path.join(out, "404.html"), staticPage("Page not found · Mimir", "This page isn't here. Search Mimir's catalogue of films, TV, books, games and music instead.", `${SITE_URL}/`,
    `<p class="eyebrow">Not found</p><h1>This page isn't in the well</h1><p class="lede">The link may be old, or the page may have moved.</p>
<p><a class="cta" href="/">Ask Mimir</a><a class="cta ghost" href="/films/">Browse the catalogue</a></p>`).replace('<meta name="robots" content="index, follow, max-image-preview:large">', '<meta name="robots" content="noindex">'));
  fs.writeFileSync(path.join(out, "CNAME"), `${HOST}\n`);
  console.log(`wrote site to ${out}`);
} else {
  const out = args[0] || path.join(here, "dist", "mimir.html");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const html = page();
  fs.writeFileSync(out, html);
  console.log(`wrote ${out} (${(html.length / 1024).toFixed(0)} KB)`);
}
