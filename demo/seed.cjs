// The editorial seed: catalogue.json plus every other seed/*.json, merged in name order (mirrors catalogue/seedfiles.py).
"use strict";
const fs = require("fs");
const path = require("path");

function readSeed(seedDir) {
  const base = JSON.parse(fs.readFileSync(path.join(seedDir, "catalogue.json"), "utf8"));
  base.relationships = base.relationships || [];
  for (const name of fs.readdirSync(seedDir).filter((n) => n.endsWith(".json") && n !== "catalogue.json").sort()) {
    const part = JSON.parse(fs.readFileSync(path.join(seedDir, name), "utf8"));
    base.works.push(...(part.works || []));
    base.relationships.push(...(part.relationships || []));
  }
  return base;
}

module.exports = { readSeed };
