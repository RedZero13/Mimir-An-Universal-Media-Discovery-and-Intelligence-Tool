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

// ---- importing a history
const ok = W.parseLink("https://public-operation-hk4e-sg.hoyoverse.com/gacha_info/api/getGachaLog?authkey_ver=1&authkey=abc%2Bdef&gacha_type=301&page=6&size=5&end_id=99&lang=en", "genshin-impact");
assert.ok(ok.base.endsWith("/gacha_info/api/getGachaLog") && ok.params.get("authkey") === "abc+def" && !ok.params.has("page") && !ok.params.has("end_id") && ok.params.get("lang") === "en", "link parsed, paging removed");
assert.ok(W.parseLink("https://evil.example.com/gacha_info/api/getGachaLog?authkey=abc", "genshin-impact").error, "other hosts are refused");
assert.ok(W.parseLink("http://public-operation-hk4e-sg.hoyoverse.com/x?authkey=abc", "genshin-impact").error, "plain http is refused");
assert.ok(W.parseLink("https://public-operation-hk4e-sg.hoyoverse.com.evil.com/x?authkey=abc", "genshin-impact").error, "look-alike hosts are refused");
assert.ok(W.parseLink("https://public-operation-hk4e-sg.hoyoverse.com/x", "genshin-impact").error, "no authkey");
assert.ok(W.parseLink("not a link", "genshin-impact").error);
const api = { retcode: 0, data: { list: [
  { id: "1700000000000000003", gacha_type: "301", rank_type: "5", name: "Diluc", time: "2024-05-03 10:00:00" },
  { id: "1700000000000000001", gacha_type: "301", rank_type: "3", name: "Slingshot", time: "2024-05-01 10:00:00" },
  { id: "1700000000000000002", gacha_type: "400", rank_type: "4", name: "Bennett", time: "2024-05-02 10:00:00" },
  { id: "1700000000000000004", gacha_type: "301", rank_type: "5", name: "Kamisato Ayaka", time: "2024-05-04 10:00:00" },
  { id: "1700000000000000005", gacha_type: "302", rank_type: "5", name: "Amos' Bow", time: "2024-05-05 10:00:00" },
  { id: "1700000000000000006", gacha_type: "100", rank_type: "3", name: "Beginner", time: "2024-05-06 10:00:00" },
  { id: "1700000000000000001", gacha_type: "301", rank_type: "3", name: "Slingshot", time: "2024-05-01 10:00:00" } ] } };
const b = W.banners(W.itemsFrom([api, { retcode: 0, data: { list: [] } }], "genshin-impact"), "genshin-impact");
assert.deepEqual(b.character.map((p) => p.n), ["Slingshot", "Bennett", "Diluc", "Kamisato Ayaka"], "oldest first, duplicates dropped, 400 joins the character banner");
assert.equal(b.character[2].f, false, "a permanent 5-star on the event banner is a lost 50/50");
assert.equal(b.character[3].f, true, "an event 5-star is the featured one");
assert.equal(b.weapon[0].f, false, "a permanent weapon");
assert.ok(!b.beginner && Object.keys(b).length === 2, "beginner wishes are left out");
// UIGF v3 and v4
const v3 = W.itemsFrom({ info: { uigf_version: "v3.0" }, list: [{ uigf_gacha_type: "301", gacha_type: "400", item_id: "1", time: "2024-05-01 10:00:00", name: "Mona", rank_type: "5", id: "1700000000000000009" }] }, "genshin-impact");
assert.equal(v3[0].type, 301); assert.equal(v3[0].rank, 5);
const v4 = W.itemsFrom({ info: { version: "v4.0" }, hk4e: [{ uid: 1, list: [{ gacha_type: 301, item_id: "10000002", time: "2024-05-01 10:00:00", id: "1700000000000000010" }] }] }, "genshin-impact", { 10000002: { name: "Kamisato Ayaka", rarity: 5 } });
assert.deepEqual([v4[0].name, v4[0].rank], ["Kamisato Ayaka", 5], "v4 carries ids only: names and rarity come from the lists");
console.log(`wish: all checks passed (expected pulls ${e.toFixed(1)}, 90% sure of featured by ${n90})`);
