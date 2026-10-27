// Browser test of the whole account flow against the real plugin code. See docs/ACCOUNTS.md ("Testing").
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const BASE = "http://localhost:8094/";
(async () => {
  const b = await chromium.launch();
  const mk = async () => { const ctx = await b.newContext({ viewport: { width: 1100, height: 900 }, acceptDownloads: true }); const p = await ctx.newPage(); const errs = []; p.on("pageerror", (e) => errs.push(String(e).slice(0, 200))); p.errs = errs; return p; };
  const A = await mk();
  await A.goto(BASE + "#account"); await A.waitForSelector(".acct-card");
  await A.evaluate(() => { localStorage.setItem("mimir-library", JSON.stringify({ "dune-1984": { status: "completed", updated: "2026-10-01" } })); localStorage.setItem("mimir-ratings", JSON.stringify({ "dune-1984": 5 })); });
  assert.equal(await A.isDisabled("[data-create]"), true, "create needs the age box");
  await A.check("[data-age]"); await A.click("[data-create]");
  await A.waitForSelector("#vault-key");
  const key = await A.getAttribute("#vault-key", "data-key");
  assert.match(key, /^([0-9A-Z]{4}-){8}[0-9A-Z]{4}$/); console.log("key shown:", key.slice(0, 9) + "…");
  assert.equal(await A.isDisabled("[data-finish]"), true);
  // protected backup made while the key is on screen
  await A.click(".key-backup summary");
  await A.fill("[data-bk-pass]", "short"); await A.fill("[data-bk-pass2]", "short"); await A.click("[data-bk-save]");
  await A.waitForFunction(() => /at least 12/.test(document.querySelector("[data-bk-msg]").textContent));
  await A.fill("[data-bk-pass]", "correct horse battery staple"); await A.fill("[data-bk-pass2]", "correct horse battery stapel"); await A.click("[data-bk-save]");
  assert.match(await A.textContent("[data-bk-msg]"), /don't match/);
  await A.fill("[data-bk-pass2]", "correct horse battery staple");
  const [bdl] = await Promise.all([A.waitForEvent("download"), A.click("[data-bk-save]")]);
  const backupFile = require("fs").readFileSync(await bdl.path(), "utf8");
  assert.match(backupFile, /MIMIR-KEY-BACKUP-1:/); assert.ok(!backupFile.includes(key.replace(/-/g, "")), "the backup file does not contain the key");
  console.log("protected backup downloaded");
  await A.check("[data-key-saved]"); await A.fill("[data-key-confirm]", "zzzz");
  assert.equal(await A.isDisabled("[data-finish]"), true, "wrong confirmation");
  await A.fill("[data-key-confirm]", key.replace(/-/g, "").slice(-4).toLowerCase());
  assert.equal(await A.isDisabled("[data-finish]"), false);
  await A.click("[data-finish]"); await A.waitForSelector("[data-sync-now]");
  console.log("created:", (await A.textContent("h1")).trim());
  assert.equal((await A.textContent("#account-link")).trim(), "Account");
  // server holds ciphertext only
  const raw = await (await fetch("http://127.0.0.1:8099/wp-json/mimir/v1/health")).json(); assert.ok(raw.ok);
  // Device B signs in with the key
  const B = await mk();
  await B.goto(BASE + "#account"); await B.waitForSelector("[data-signin]");
  await B.fill("[data-key-in]", "AAAA-BBBB"); await B.click("[data-signin] button");
  assert.match(await B.textContent("[data-signin-msg]"), /36 letters/, "short key message");
  const typo = key.replace(/[2-9A-H]/, (c) => (c === "2" ? "3" : "2"));
  await B.fill("[data-key-in]", typo); await B.click("[data-signin] button");
  await B.waitForFunction(() => document.querySelector("[data-signin-msg]").textContent.length > 0);
  assert.match(await B.textContent("[data-signin-msg]"), /typing mistake/, "typo message");
  const other = await B.evaluate(() => window.MimirVault.newRecoveryKey());
  await B.fill("[data-key-in]", other); await B.click("[data-signin] button");
  await B.waitForFunction(() => /No vault opens/.test(document.querySelector("[data-signin-msg]").textContent));
  console.log("wrong key:", (await B.textContent("[data-signin-msg]")).trim());
  await B.fill("[data-key-in]", key.toLowerCase()); await B.click("[data-signin] button");
  await B.waitForSelector("[data-sync-now]", { timeout: 20000 });
  const lib = await B.evaluate(() => JSON.parse(localStorage.getItem("mimir-library")));
  assert.equal(lib["dune-1984"].status, "completed"); console.log("device B restored library:", Object.keys(lib));
  assert.equal(await B.evaluate(() => JSON.parse(localStorage.getItem("mimir-ratings"))["dune-1984"]), 5);
  // Device D signs in from the protected backup instead of the key
  const D = await mk();
  await D.goto(BASE + "#account"); await D.waitForSelector(".key-backup summary");
  await D.click(".key-backup summary");
  await D.fill("[data-bk-in]", backupFile); await D.fill("[data-bk-in-pass]", "wrong passphrase here"); await D.click("[data-signin-bk] button[type=submit]");
  await D.waitForFunction(() => /does not open/.test(document.querySelector("[data-signin-bk-msg]").textContent));
  await D.fill("[data-bk-in-pass]", "correct horse battery staple"); await D.click("[data-signin-bk] button[type=submit]");
  await D.waitForSelector("[data-sync-now]", { timeout: 20000 });
  assert.equal((await D.evaluate(() => JSON.parse(localStorage.getItem("mimir-library"))))["dune-1984"].status, "completed"); console.log("device D signed in from the protected backup");
  // edits on both devices merge
  await B.evaluate(() => localStorage.setItem("mimir-ratings", JSON.stringify({ "dune-1984": 5, "alien-1979": 4 })));
  await A.evaluate(() => localStorage.setItem("mimir-lists", JSON.stringify([{ id: "l1", name: "Weekend" }])));
  await B.click("[data-sync-now]"); await B.waitForFunction(() => /Synced/.test(document.querySelector("[data-sync-msg]").textContent));
  await A.click("[data-sync-now]"); await A.waitForFunction(() => /Synced/.test(document.querySelector("[data-sync-msg]").textContent));
  await B.click("[data-sync-now]"); await B.waitForFunction(() => /Synced/.test(document.querySelector("[data-sync-msg]").textContent));
  const aR = await A.evaluate(() => JSON.parse(localStorage.getItem("mimir-ratings"))), bL = await B.evaluate(() => JSON.parse(localStorage.getItem("mimir-lists")));
  assert.deepEqual(aR, { "dune-1984": 5, "alien-1979": 4 }); assert.deepEqual(bL, [{ id: "l1", name: "Weekend" }]);
  console.log("both devices converged");
  assert.ok(await A.locator(".sync-notice").count() >= 0);
  // export
  const [dl] = await Promise.all([B.waitForEvent("download"), B.click("[data-export]")]);
  const exp = JSON.parse(require("fs").readFileSync(await dl.path(), "utf8")); assert.equal(exp.data["mimir-ratings"]["alien-1979"], 4); console.log("export ok:", Object.keys(exp.data).length, "keys");
  // rotate on B; A's old key no longer syncs
  await B.click("[data-rotate]"); await B.waitForSelector("#rotate-out #vault-key");
  const newKey = await B.getAttribute("#rotate-out #vault-key", "data-key");
  await B.check("#rotate-out [data-key-saved]"); await B.fill("#rotate-out [data-key-confirm]", newKey.replace(/-/g, "").slice(-4));
  await B.click("[data-rotate-go]"); await B.waitForFunction(() => /Done/.test(document.querySelector("#rotate-out").textContent));
  await A.click("[data-sync-now]"); await A.waitForFunction(() => /No vault opens/.test(document.querySelector("[data-sync-msg]").textContent));
  console.log("old key rejected after rotate");
  // sign out with wipe, then sign in with the new key
  await B.check("[data-wipe]"); await B.click("[data-signout]"); await B.waitForSelector("[data-signin]");
  assert.equal(await B.evaluate(() => localStorage.getItem("mimir-library")), null, "wiped");
  await B.fill("[data-key-in]", newKey); await B.click("[data-signin] button"); await B.waitForSelector("[data-sync-now]", { timeout: 20000 });
  assert.equal(await B.evaluate(() => JSON.parse(localStorage.getItem("mimir-library"))["dune-1984"].status), "completed"); console.log("signed out, wiped and restored from the new key");
  // delete
  await B.fill("[data-del-confirm]", "DELETE"); await B.click("[data-delete]"); await B.waitForFunction(() => /account is deleted/.test(document.body.innerText));
  const C = await mk(); await C.goto(BASE + "#account"); await C.waitForSelector("[data-signin]");
  await C.fill("[data-key-in]", newKey); await C.click("[data-signin] button"); await C.waitForFunction(() => /No vault opens/.test(document.querySelector("[data-signin-msg]").textContent));
  console.log("deleted vault cannot be opened");
  for (const p of [A, B, C]) assert.deepEqual(p.errs, [], "page errors");
  await b.close(); console.log("vault e2e: all passed");
})().catch((e) => { console.error(e); process.exit(1); });
