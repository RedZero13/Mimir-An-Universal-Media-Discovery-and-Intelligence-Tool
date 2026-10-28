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
  // passphrase-protected key backup
  assert.ok(V.passphraseProblem("short"), "short passphrases are refused");
  assert.ok(V.passphraseProblem("aaaaaaaaaaaaaaaa"), "repetition is refused");
  assert.ok(V.passphraseProblem("password1234"), "common words are refused");
  assert.equal(V.passphraseProblem("correct horse battery staple"), "", "four random words pass");
  const pass = "correct horse battery staple";
  const backup = await V.wrapKey(pass, key);
  assert.ok(backup.startsWith(V.BACKUP_PREFIX) && !backup.includes(key.replace(/-/g, "")), "the backup does not contain the key");
  assert.equal(await V.unwrapKey(pass, backup), key, "round trip returns the same key");
  assert.equal(await V.unwrapKey(pass, `  ${backup.slice(0, 30)}\n${backup.slice(30)} `), key, "line breaks and spaces from pasting are forgiven");
  assert.notEqual(backup, await V.wrapKey(pass, key), "fresh salt and nonce every time");
  await assert.rejects(() => V.unwrapKey("correct horse battery stapl", backup), /does not open/, "wrong passphrase");
  const damaged = V.BACKUP_PREFIX + V.b64u(new TextEncoder().encode(JSON.stringify({ ...JSON.parse(new TextDecoder().decode(V.unb64u(backup.slice(V.BACKUP_PREFIX.length)))), c: V.b64u(new Uint8Array(36)) })));
  await assert.rejects(() => V.unwrapKey(pass, damaged), /does not open/, "tampering is detected");
  await assert.rejects(() => V.unwrapKey(pass, "hello"), /not look like/, "other text");
  await assert.rejects(() => V.wrapKey("short", key), /at least 12/, "weak passphrase");
  await assert.rejects(() => V.wrapKey(pass, "ABCD"), /not a valid/, "bad key");
  console.log("vault: all checks passed");
})().catch((e) => { console.error(e); process.exit(1); });
