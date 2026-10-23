// Builds Mimir's single-page site: page.html with the engine, pilot data and brand assets inlined.
//
//   node demo/build.cjs [out.html]     body-only page (for previews that supply their own document shell)
//   node demo/build.cjs --site [dir]   deployable static site (default: demo/dist/site): index.html with a full
//                                      <head>, favicons, social card, web manifest, robots.txt and CNAME
"use strict";
const fs = require("fs");
const { readSeed } = require("./seed.cjs");
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

function page() {
  return fs.readFileSync(path.join(here, "page.html"), "utf8")
    .replace("/*__TAXONOMY__*/", () => json(path.join(api, "taxonomy", "taxonomy.json")))
    .replace("/*__CATALOGUE__*/", () => safe(JSON.stringify(readSeed(path.join(api, "seed")))))
    .replace("/*__PROVIDERS__*/", () => json(path.join(api, "catalogue", "providers.json")))
    .replace("/*__SHELVES__*/", () => json(path.join(api, "catalogue", "shelves.json")))
    .replace("/*__CALENDAR__*/", () => json(path.join(api, "catalogue", "calendar.json")))
    .replace("/*__BLOG__*/", () => json(path.join(here, "blog.json")))
    // Accounts and community talk to the API at MIMIR_API_URL; without it the site runs on its own, browser-only.
    .replace("/*__CONFIG__*/", () => safe(JSON.stringify({ api: (process.env.MIMIR_API_URL || "").replace(/\/$/, "") })))
    .replace("/*__ENRICHMENT__*/", () => safe(JSON.stringify(enrichment())))
    .replace("/*__ENGINE__*/", () => safe(fs.readFileSync(path.join(here, "engine.cjs"), "utf8")))
    .replace("/*__SEAL__*/", () => dataUri(path.join(brand, "terratales-seal-64.png"), "image/png"));
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
<meta property="og:type" content="website">
<meta property="og:site_name" content="Mimir · A Terratales Venture">
<meta property="og:title" content="Mimir · Drawn from the well of every story">
<meta property="og:description" content="Films, books, games and music, found by how they feel, with the reasons for every pick.">
<meta property="og:url" content="${SITE_URL}/">
<meta property="og:image" content="${SITE_URL}/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">`;
  return `<!doctype html>\n<html lang="en">\n<head>${extraHead}\n${head.trim()}\n</head>\n<body>\n${body.trim()}\n</body>\n</html>\n`;
}

// The blog as static pages (one per post, plus an index) so search engines and link previews can read them; the
// app shows the same posts at #blog. A sitemap lists the home page and every post.
function writeBlog(out) {
  const posts = JSON.parse(fs.readFileSync(path.join(here, "blog.json"), "utf8")).posts.sort((a, b) => b.date.localeCompare(a.date));
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const href = (h) => (h === "#" ? "/" : h.startsWith("#") ? `/${h}` : h);
  const inline = (s) => esc(s).replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, h) => `<a href="${esc(href(h))}">${text}</a>`);
  const md = (src) => src.split(/\n\n+/).map((b) => (b.startsWith("## ") ? `<h2>${inline(b.slice(3))}</h2>`
    : b.startsWith("- ") ? `<ul>${b.split("\n").map((l) => `<li>${inline(l.replace(/^- /, ""))}</li>`).join("")}</ul>` : `<p>${inline(b)}</p>`)).join("\n");
  const date = (d) => new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
  const shell = (title, desc, canonical, body, extraHead = "") => `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title><meta name="description" content="${esc(desc)}"><link rel="canonical" href="${canonical}">
<meta property="og:type" content="article"><meta property="og:title" content="${esc(title)}"><meta property="og:description" content="${esc(desc)}">
<meta property="og:url" content="${canonical}"><meta property="og:image" content="${SITE_URL}/og-image.png"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#EDE3CC"><link rel="icon" href="/favicon.svg" type="image/svg+xml">${extraHead}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600&family=Cormorant+Garamond:ital,wght@0,600;1,500&family=Inter:wght@300;400;500&display=swap">
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
footer{max-width:1080px;margin:64px auto 0;padding:22px 0 40px;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem;display:flex;flex-wrap:wrap;gap:8px 20px;justify-content:space-between}
</style></head><body>
<header class="top"><a class="brand" href="/">MIMIR<small>A TERRATALES VENTURE</small></a><nav><a href="/blog/">Blog</a> · <a href="/">Open Mimir</a></nav></header>
<main class="wrap">${body}</main>
<footer><span>© 2026 Terratales Media Entertainment · All realms reserved</span><span><a href="/">Mimir</a> · <a href="/blog/">Blog</a> · <a href="https://terratalesmedia.world/" target="_blank" rel="noopener">Terratales</a></span></footer>
</body></html>
`;
  fs.mkdirSync(path.join(out, "blog"), { recursive: true });
  fs.writeFileSync(path.join(out, "blog", "index.html"), shell("The Mimir blog · Notes from the well",
    "What Mimir can do, how it works, and what's new: discover and track films, TV, books, manga, games and music.", `${SITE_URL}/blog/`,
    `<p class="eyebrow">The Mimir blog</p><h1>Notes from the well</h1><p class="meta">What Mimir can do, how it works, and what's new.</p>
<ul class="cards">${posts.map((b) => `<li><a href="/blog/${b.slug}/"><p class="meta">${esc(b.tags.join(" · "))} · ${date(b.date)}</p><h2>${esc(b.title)}</h2><p>${esc(b.summary)}</p></a></li>`).join("")}</ul>`));
  for (const b of posts) {
    const url = `${SITE_URL}/blog/${b.slug}/`;
    const ld = { "@context": "https://schema.org", "@type": "BlogPosting", headline: b.title, description: b.summary, datePublished: b.date,
      url, image: `${SITE_URL}/og-image.png`, author: { "@type": "Organization", name: "Mimir · Terratales" },
      publisher: { "@type": "Organization", name: "Terratales Media Entertainment", url: "https://terratalesmedia.world/" } };
    fs.mkdirSync(path.join(out, "blog", b.slug), { recursive: true });
    fs.writeFileSync(path.join(out, "blog", b.slug, "index.html"), shell(`${b.title} · Mimir`, b.summary, url,
      `<p class="eyebrow"><a href="/blog/">Blog</a> · ${esc(b.tags.join(" · "))}</p><h1>${esc(b.title)}</h1><p class="meta">${date(b.date)} · The Mimir team</p>
<p class="lede">${esc(b.summary)}</p>
${md(b.body)}
<p><a class="cta" href="/">Ask Mimir</a><a class="cta ghost" href="/#decide">Decide for me</a></p>`,
      `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, "\\u003c")}</script>`));
  }
  const urls = [[`${SITE_URL}/`, null], [`${SITE_URL}/blog/`, posts[0] && posts[0].date], ...posts.map((b) => [`${SITE_URL}/blog/${b.slug}/`, b.date])];
  fs.writeFileSync(path.join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(([u, d]) => `  <url><loc>${u}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}</url>`).join("\n")}\n</urlset>\n`);
}

const args = process.argv.slice(2);
if (args[0] === "--site") {
  const out = args[1] || path.join(here, "dist", "site");
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "index.html"), standalone(page()));
  for (const f of ["favicon.svg", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "icon-maskable-192.png", "icon-maskable-512.png", "app-icon.svg", "og-image.png"]) {
    fs.copyFileSync(path.join(brand, f), path.join(out, f));
  }
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
  fs.writeFileSync(path.join(out, "sw.js"), fs.readFileSync(path.join(here, "sw.js"), "utf8").replace("__VERSION__", version));
  writeBlog(out);
  fs.writeFileSync(path.join(out, "robots.txt"), `User-agent: *\nAllow: /\nSitemap: ${SITE_URL}/sitemap.xml\n`);
  fs.writeFileSync(path.join(out, "CNAME"), `${HOST}\n`);
  console.log(`wrote site to ${out}`);
} else {
  const out = args[0] || path.join(here, "dist", "mimir.html");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const html = page();
  fs.writeFileSync(out, html);
  console.log(`wrote ${out} (${(html.length / 1024).toFixed(0)} KB)`);
}
