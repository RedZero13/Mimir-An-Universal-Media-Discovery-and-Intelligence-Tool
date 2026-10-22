// Runs the JS engine over a list of queries and slugs; prints JSON for api/tests/test_demo_parity.py.
"use strict";
const fs = require("fs");
const path = require("path");
const MDE = require("./engine.cjs");

const api = path.join(__dirname, "..", "api", "mde");
const catalogue = JSON.parse(fs.readFileSync(path.join(api, "seed", "catalogue.json"), "utf8"));
const taxonomy = JSON.parse(fs.readFileSync(path.join(api, "taxonomy", "taxonomy.json"), "utf8"));
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const cat = MDE.createCatalogue(catalogue, taxonomy);
process.stdout.write(JSON.stringify({
  discover: input.queries.map((q) => cat.discover(q, 8)),
  works: input.slugs.map((s) => cat.work(s)),
}));
