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
    overlays.push({ terms: part.terms || {}, attributes: part.attributes || {}, credits: part.credits || {}, summaries: part.summaries || {} });
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
    for (const [slug, text] of Object.entries(overlay.summaries)) {   // a summary written in the work's own record wins
      const w = target(slug);
      if (!w.summary) w.summary = text;
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
  // Last of all, the manual review's corrections (seed/review-corrections.json): whole fields that win over everything above.
  // "attributes.x" sets one attribute; null removes the field.
  const corrPath = path.join(seedDir, "review-corrections.json");
  const corrections = fs.existsSync(corrPath) ? JSON.parse(fs.readFileSync(corrPath, "utf8")) : {};
  for (const [slug, patch] of Object.entries(corrections.corrections || {})) {
    const w = target(slug);
    for (const [field, value] of Object.entries(patch)) {
      const [holder, key] = field.startsWith("attributes.") ? [(w.attributes = w.attributes || {}), field.slice(11)] : [w, field];
      if (value === null) delete holder[key];
      else holder[key] = value;
    }
  }
  return base;
}

module.exports = { readSeed };
