// Run: node demo/vault.test.cjs. Round trip, wrong key, typo detection, merge rules.
"use strict";
const assert = require("node:assert/strict");
const V = require("./vault.cjs");

(async () => {
  const key = await V.newRecoveryKey();
  assert.match(key, /^([0-9A-HJKMNP-TV-Z]{4}-){8}[0-9A-HJKMNP-TV-Z]{4}$/, "nine groups of four");
  assert.notEqual(key, await V.newRecoveryKey(), "keys are random");

  const parsed = await V.parseRecoveryKey(key.toLowerCase().replace(/-/g, "  "));
  assert.ok(parsed.ok, "spaces, dashes and case are forgiven");
  const lookalike = await V.parseRecoveryKey(key.replace(/0/g, "o").replace(/1/g, "l"));
  assert.ok(lookalike.ok, "o reads as 0, l and i as 1");
  assert.equal((await V.parseRecoveryKey(key.slice(0, -2))).reason, "length");
  const typo = key.replace(/[2-9A-H]/, (c) => (c === "2" ? "3" : "2"));
  assert.equal((await V.parseRecoveryKey(typo)).reason, "typo", "a changed character is caught by the check characters");

  const a = await V.derive(parsed.bytes), b = await V.derive((await V.parseRecoveryKey(key)).bytes);
  assert.equal(a.id, b.id); assert.equal(a.auth, b.auth);
  assert.match(a.id, /^[0-9a-f]{32}$/); assert.ok(a.auth.length >= 43);
  assert.notEqual(a.id, a.auth, "id and auth are independent");

  const data = { v: 1, keys: { "mimir-library": { t: 5, d: { "dune-1984": { status: "completed" } } } } };
  const blob = await V.seal(a, data);
  assert.ok(!blob.includes("dune"), "the blob does not show its contents");
  assert.deepEqual(await V.open(b, blob), data, "round trip on a second derivation");
  assert.notEqual(blob, await V.seal(a, data), "a fresh nonce every time");

  const other = await V.derive((await V.parseRecoveryKey(await V.newRecoveryKey())).bytes);
  await assert.rejects(() => V.open(other, blob), /does not open/, "wrong key");
  const raw = V.unb64u(blob); raw[20] ^= 1;
  await assert.rejects(() => V.open(a, V.b64u(raw)), /does not open/, "tampering is detected");
  await assert.rejects(() => V.open({ ...a, id: "0".repeat(32) }, blob), /does not open/, "bound to the vault id");

  // merging
  const m = V.mergeVaults(
    { v: 1, keys: { r: { t: 10, d: { a: 5, b: 1 } }, l: { t: 3, d: [{ id: 1, x: "old" }] }, only: { t: 1, d: "x" } } },
    { v: 1, keys: { r: { t: 20, d: { a: 9, c: 2 } }, l: { t: 9, d: [{ id: 1, x: "new" }, { id: 2 }] }, theirs: { t: 1, d: 7 } } });
  assert.deepEqual(m.keys.r, { t: 20, d: { a: 9, c: 2, b: 1 } }, "objects merge by key, newer wins");
  assert.deepEqual(m.keys.l.d, [{ id: 1, x: "new" }, { id: 2 }], "lists union by id, newer copy wins");
  assert.equal(m.keys.only.d, "x"); assert.equal(m.keys.theirs.d, 7);
  console.log("vault: all checks passed");
})().catch((e) => { console.error(e); process.exit(1); });
