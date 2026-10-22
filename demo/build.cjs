// Builds the single-file browser demo: page.html with the engine and pilot data inlined.
// Usage: node demo/build.cjs [output.html]   (default: demo/dist/media-discovery.html)
"use strict";
const fs = require("fs");
const path = require("path");

const here = __dirname;
const api = path.join(here, "..", "api", "mde");
const out = process.argv[2] || path.join(here, "dist", "media-discovery.html");
// Inline JSON/JS must not be able to close the <script> element early.
const safe = (s) => s.replace(/<\/(script)/gi, "<\\/$1");
const json = (p) => safe(JSON.stringify(JSON.parse(fs.readFileSync(p, "utf8"))));

const html = fs.readFileSync(path.join(here, "page.html"), "utf8")
  .replace("/*__TAXONOMY__*/", () => json(path.join(api, "taxonomy", "taxonomy.json")))
  .replace("/*__CATALOGUE__*/", () => json(path.join(api, "seed", "catalogue.json")))
  .replace("/*__ENGINE__*/", () => safe(fs.readFileSync(path.join(here, "engine.cjs"), "utf8")));
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, html);
console.log(`wrote ${out} (${(html.length / 1024).toFixed(0)} KB)`);
