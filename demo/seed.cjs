// The editorial seed: catalogue.json plus every other seed/*.json, merged in name order (mirrors catalogue/seedfiles.py).
"use strict";
const fs = require("fs");
const path = require("path");

function readSeed(seedDir) {
  const base = JSON.parse(fs.readFileSync(path.join(seedDir, "catalogue.json"), "utf8"));
  base.relationships = base.relationships || [];
  const overlays = [];
  for (const name of fs.readdirSync(seedDir).filter((n) => n.endsWith(".json") && n !== "catalogue.json").sort()) {
    const part = JSON.parse(fs.readFileSync(path.join(seedDir, name), "utf8"));
    base.works.push(...(part.works || []));
    base.relationships.push(...(part.relationships || []));
    overlays.push(part.terms || {});
  }
  // Term overlays (seed/subgenres.json) add tags to works defined in any file.
  const bySlug = new Map(base.works.map((w) => [w.slug, w]));
  for (const overlay of overlays) {
    for (const [slug, terms] of Object.entries(overlay)) {
      if (!bySlug.has(slug)) throw new Error(`term overlay names unknown work ${slug}`);
      bySlug.get(slug).terms = { ...(bySlug.get(slug).terms || {}), ...terms };
    }
  }
  return base;
}

module.exports = { readSeed };
