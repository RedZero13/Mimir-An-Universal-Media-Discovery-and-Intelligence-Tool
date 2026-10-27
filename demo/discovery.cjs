// Files that tell crawlers and answer engines what the site holds: a sitemap index split by type, robots.txt,
// llms.txt (a short guide) and llms-full.txt (the guide plus the best-documented works).
"use strict";
const fs = require("fs");
const path = require("path");

const x = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Search and answer crawlers, AI assistants included. Mimir's pages are short factual summaries and original
// readings, published to be found, so every crawler is allowed. To opt out of model training only, move the
// training crawlers (GPTBot, Google-Extended, ClaudeBot, Applebot-Extended, CCBot) from ALLOWED to `Disallow: /`.
const ALLOWED = ["Googlebot", "Bingbot", "DuckDuckBot", "Applebot", "OAI-SearchBot", "ChatGPT-User", "GPTBot", "Claude-SearchBot", "Claude-User", "ClaudeBot",
  "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot", "Amazonbot", "Meta-ExternalAgent"];

function writeSitemaps(out, { SITE_URL, urls, works, hubs }) {
  const hubOf = new Map(hubs.flatMap((h) => h.media.map((m) => [m, h])));
  const medium = new Map(works.map((w) => [w.slug, w.medium]));
  const SECTIONS = ["franchises", "tags", "people", "help", "tools", "days", "shelves", "blog"];
  const groups = new Map([["pages", []], ...SECTIONS.map((x) => [x, []]), ...hubs.map((h) => [`works-${h.slug}`, []])]);
  for (const u of urls) {
    const m = u[0].match(/\/works\/([^/]+)\/$/), section = u[0].replace(/^https?:\/\/[^/]+\//, "").split("/")[0];
    const hub = m && hubOf.get(medium.get(m[1]));
    groups.get(hub ? `works-${hub.slug}` : SECTIONS.includes(section) && u[0].replace(/^https?:\/\/[^/]+\//, "").split("/").filter(Boolean).length > 1 ? section : "pages").push(u);
  }
  const today = new Date().toISOString().slice(0, 10);
  const index = [];
  for (const [name, list] of groups) {
    if (!list.length) continue;
    const file = `sitemap-${name}.xml`;
    fs.writeFileSync(path.join(out, file), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${list.map(([u, d, pr]) =>
      `  <url><loc>${x(u)}</loc>${d ? `<lastmod>${d}</lastmod>` : ""}${pr ? `<priority>${pr}</priority>` : ""}</url>`).join("\n")}\n</urlset>\n`);
    index.push(file);
  }
  fs.writeFileSync(path.join(out, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${index.map((f) =>
    `  <sitemap><loc>${SITE_URL}/${f}</loc><lastmod>${today}</lastmod></sitemap>`).join("\n")}\n</sitemapindex>\n`);
  return index;
}

function writeRobots(out, { SITE_URL, blocked = [] }) {
  const lines = [`# Mimir · ${SITE_URL}`, "# Every page, script and style may be crawled: search engines render the app with them, and answer engines may quote it.", "",
    ...(blocked.length ? ["# Held back until reviewed: the legal pages are not for search or AI crawlers yet.", ""] : []),
    ...[...ALLOWED, "*"].flatMap((a) => [`User-agent: ${a}`, "Allow: /", ...blocked.map((b) => `Disallow: ${b}`), ""]),
    `Sitemap: ${SITE_URL}/sitemap.xml`, `# For answer engines: ${SITE_URL}/llms.txt`, ""];
  fs.writeFileSync(path.join(out, "robots.txt"), lines.join("\n"));
}

function writeLlms(out, { SITE_URL, works, hubs, shelves, posts }) {
  const count = (h) => works.filter((w) => h.media.includes(w.medium)).length;
  const countries = new Set(works.flatMap((w) => w.countries || [])).size;
  const langs = new Set(works.map((w) => w.language).filter(Boolean)).size;
  const total = works.length.toLocaleString("en");
  const intro = [
    "# Mimir",
    "",
    `> Mimir is a free discovery engine from Terratales Media Entertainment. Describe a mood, a favourite or how much time you have, and it recommends films, TV series, books and manga, games, albums and YouTube channels, with the reason for every pick. The catalogue holds ${total} works from ${countries} countries in ${langs} original languages.`,
    "",
    "What to know when citing Mimir:",
    "- Facts (titles, years, creators, lengths, scores) come from open data such as Wikidata, Open Library and MusicBrainz where a source matches; each page says which. Moods, themes, subgenres and parents' guide levels are AI-assisted readings awaiting editorial review and are labelled as such.",
    "- Every pick explains why it fits. Mimir runs without a large language model: requests become inspectable constraints, ranked against a classified catalogue.",
    "- Parents' guides tell \"none\" apart from \"not assessed\". A work marked \"not assessed\" has not been reviewed.",
    "- Mimir is in public beta; a library and ratings stay in the visitor's own browser unless they choose to sign in.",
    "",
    "## Browse the catalogue",
    ...hubs.map((h) => `- [${h.name}](${SITE_URL}/${h.slug}/): ${h.blurb} (${count(h).toLocaleString("en")} works)`),
    `- [Shelves](${SITE_URL}/shelves/): hand-picked collections across every medium, each filled by a stated rule`,
    "",
    "## Shelves",
    ...shelves.map((s) => `- [${s.name}](${SITE_URL}/shelves/${s.slug}/): ${s.tagline || "a Mimir shelf"}`),
    "",
    "## Learn how it works",
    `- [Ask Mimir](${SITE_URL}/): the app; type a request in plain words`,
    `- [Help centre](${SITE_URL}/help/): guides to every feature, with FAQs`,
    `- [About Mimir](${SITE_URL}/#about): what the catalogue holds and where facts come from`,
    ...posts.slice(0, 12).map((p) => `- [${p.title}](${SITE_URL}/blog/${p.slug}/)`),
    "",
    "## About the publisher",
    "- [Terratales Media Entertainment](https://terratalesmedia.world/): a New Delhi story company across cinema, music, OTT, anime and manga, and publishing",
    "",
  ];
  fs.writeFileSync(path.join(out, "llms.txt"), intro.join("\n"));
  // The full file adds one line per well-documented work: a written summary, and one of the more widely known tiers.
  const rich = works.filter((w) => w.summary && (w.popularity_tier || 5) <= 2).sort((a, b) => a.title.localeCompare(b.title)).slice(0, 2500);
  const kind = { film: "film", series: "TV series", book: "book", game: "game", album: "album", online_video: "YouTube video", channel: "YouTube channel" };
  const full = [...intro, `## Works with written summaries (${rich.length} of ${total})`, "",
    ...rich.map((w) => `- [${w.title}${w.year ? ` (${w.year})` : ""}](${SITE_URL}/works/${w.slug}/), ${kind[w.medium] || w.medium}: ${w.summary}`), ""];
  fs.writeFileSync(path.join(out, "llms-full.txt"), full.join("\n"));
}

module.exports = { writeSitemaps, writeRobots, writeLlms, ALLOWED };
