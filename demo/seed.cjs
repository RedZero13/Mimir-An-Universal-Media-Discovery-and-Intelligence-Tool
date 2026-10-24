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
    overlays.push({ terms: part.terms || {}, attributes: part.attributes || {}, credits: part.credits || {} });
  }
  // Overlays add to works defined in any file: tags (seed/subgenres.json), attributes such as franchises, and
  // extra credits such as lead cast (seed/people-and-franchises.json). Existing values win over overlay attributes.
  const bySlug = new Map(base.works.map((w) => [w.slug, w]));
  const target = (slug) => {
    if (!bySlug.has(slug)) throw new Error(`overlay names unknown work ${slug}`);
    return bySlug.get(slug);
  };
  for (const overlay of overlays) {
    for (const [slug, terms] of Object.entries(overlay.terms)) {
      const w = target(slug);
      w.terms = { ...(w.terms || {}), ...terms };
    }
    for (const [slug, attrs] of Object.entries(overlay.attributes)) {
      const w = target(slug);
      w.attributes = { ...attrs, ...(w.attributes || {}) };
    }
    for (const [slug, credits] of Object.entries(overlay.credits)) {
      const w = target(slug);
      const have = new Set((w.credits || []).map((c) => `${c[0]}|${c[1]}`));
      const added = [];
      for (const c of credits) {   // a credit already present (or repeated in the overlay) is skipped
        const key = `${c[0]}|${c[1]}`;
        if (!have.has(key)) { have.add(key); added.push(c); }
      }
      w.credits = [...(w.credits || []), ...added];
    }
  }
  return base;
}

module.exports = { readSeed };
