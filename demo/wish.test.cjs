// Run: node demo/wish.test.cjs. The wish maths against values that follow from the rules.
"use strict";
const assert = require("node:assert/strict");
const W = require("./wish.cjs");
const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

const char = { base: 0.6, soft: 74, step: 6, hard: 90, featured: 0.5 };
const weapon = { base: 0.7, soft: 63, step: 7, hard: 80, featured: 0.75 };

// the rate curve: flat, rising from the soft pity, certain at the hard pity
near(W.rate(char, 1), 0.006, 1e-12, "flat");
near(W.rate(char, 73), 0.006, 1e-12, "last flat pull");
near(W.rate(char, 74), 0.066, 1e-12, "first soft pull");
near(W.rate(char, 80), 0.426, 1e-9, "mid soft pity");
assert.equal(W.rate(char, 90), 1);

// the distribution of the next 5-star is a probability distribution, and ends at the hard pity
for (const [r, pity] of [[char, 0], [char, 50], [char, 80], [weapon, 0], [weapon, 70]]) {
  const d = W.dist(r, pity);
  near(d.reduce((a, x) => a + x, 0), 1, 1e-9, `sums to one (hard ${r.hard}, pity ${pity})`);
  assert.equal(d.length - 1, r.hard - pity, "last possible pull is the hard pity");
}
// at the hard pity, the next pull is certain
near(W.cdf(W.dist(char, 89), 1), 1, 1e-12, "certain at hard pity");

// the expected number of pulls to a 5-star is about 62 for the 0.6% curve (the figure players quote)
near(W.expected(char, 0), 62.5, 1.5, "expected pulls, character banner");
// a 50/50 needs about 1.5 5-stars: more than one, less than two, pulls
const e = W.expected(char, 0);
near(W.featuredWithin(char, 0, false, 180), 1, 1e-9, "two hard pities always reach the featured one");
assert.ok(W.featuredWithin(char, 0, false, 90) < 1 && W.featuredWithin(char, 0, false, 90) >= 0.5 - 1e-9, "within one hard pity: at least the 50%");
// guaranteed: the first 5-star is the featured one
near(W.featuredWithin(char, 0, true, 90), 1, 1e-12, "guaranteed within the hard pity");
near(W.featuredWithin(char, 0, true, 40), W.cdf(W.dist(char, 0), 40), 1e-12, "guaranteed = the 5-star itself");
// monotone in the number of pulls, and more pity never hurts
let last = 0;
for (let n = 0; n <= 180; n += 10) { const p = W.featuredWithin(char, 10, false, n); assert.ok(p >= last - 1e-12); last = p; }
assert.ok(W.featuredWithin(char, 60, false, 20) > W.featuredWithin(char, 0, false, 20));
// pullsFor agrees with featuredWithin
const n90 = W.pullsFor(char, 0, false, 0.9);
assert.ok(W.featuredWithin(char, 0, false, n90) >= 0.9 && W.featuredWithin(char, 0, false, n90 - 1) < 0.9);
// a rule that always gives the featured one is just the 5-star curve
near(W.featuredWithin({ ...weapon, featured: 1 }, 0, false, 80), 1, 1e-12, "always featured");
console.log(`wish: all checks passed (expected pulls ${e.toFixed(1)}, 90% sure of featured by ${n90})`);
