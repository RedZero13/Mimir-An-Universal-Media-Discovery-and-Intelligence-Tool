// Builds Mimir's single-page site: page.html with the engine, pilot data and brand assets inlined.
//
//   node demo/build.cjs [out.html]     body-only page (for previews that supply their own document shell)
//   node demo/build.cjs --site [dir]   deployable static site (default: demo/dist/site): index.html with a full
//                                      <head>, favicons, social card, web manifest, robots.txt and CNAME
"use strict";
const fs = require("fs");
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
    for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".json")).sort()) {
      out[f.slice(0, -5)] = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    }
  }
  return out;
}

function page() {
  return fs.readFileSync(path.join(here, "page.html"), "utf8")
    .replace("/*__TAXONOMY__*/", () => json(path.join(api, "taxonomy", "taxonomy.json")))
    .replace("/*__CATALOGUE__*/", () => json(path.join(api, "seed", "catalogue.json")))
    .replace("/*__SHELVES__*/", () => json(path.join(api, "catalogue", "shelves.json")))
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

const args = process.argv.slice(2);
if (args[0] === "--site") {
  const out = args[1] || path.join(here, "dist", "site");
  fs.mkdirSync(out, { recursive: true });
  fs.writeFileSync(path.join(out, "index.html"), standalone(page()));
  for (const f of ["favicon.svg", "favicon-32.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png", "og-image.png"]) {
    fs.copyFileSync(path.join(brand, f), path.join(out, f));
  }
  fs.writeFileSync(path.join(out, "site.webmanifest"), JSON.stringify({
    name: "Mimir · A Terratales Venture", short_name: "Mimir", start_url: "/", display: "standalone",
    background_color: "#131315", theme_color: "#131315",
    icons: [{ src: "/icon-192.png", sizes: "192x192", type: "image/png" }, { src: "/icon-512.png", sizes: "512x512", type: "image/png" }],
  }, null, 2));
  fs.writeFileSync(path.join(out, "robots.txt"), "User-agent: *\nAllow: /\n");
  fs.writeFileSync(path.join(out, "CNAME"), `${HOST}\n`);
  console.log(`wrote site to ${out}`);
} else {
  const out = args[0] || path.join(here, "dist", "mimir.html");
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const html = page();
  fs.writeFileSync(out, html);
  console.log(`wrote ${out} (${(html.length / 1024).toFixed(0)} KB)`);
}
