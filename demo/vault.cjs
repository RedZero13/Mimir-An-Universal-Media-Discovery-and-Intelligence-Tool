// Mimir vault: the browser-side crypto for accounts. The server only ever sees ciphertext.
//
//   recovery key  20 random bytes, written as 32 Crockford base32 characters plus 4 check characters (XXXX-XXXX-...).
//   id            HKDF(key, "id")   : names the vault on the server, reveals nothing about the key
//   auth          HKDF(key, "auth") : proves you hold the key (the server stores only a keyed hash of it)
//   backup        optional: the key wrapped by a passphrase (PBKDF2-SHA256 + AES-256-GCM) into text the person keeps; never sent to the server
//   enc           HKDF(key, "enc")  : AES-256-GCM key for the vault contents; never leaves the browser
// The three are independent outputs of HKDF-SHA256, so the server, which sees id and auth, cannot work out enc.
"use strict";
(function (root, factory) {
  const api = factory(typeof crypto !== "undefined" ? crypto : require("node:crypto").webcrypto);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MimirVault = api;
})(typeof self !== "undefined" ? self : globalThis, function (webcrypto) {
  const subtle = webcrypto.subtle;
  const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";   // Crockford: no I, L, O or U
  const enc = new TextEncoder(), dec = new TextDecoder();
  const SALT = enc.encode("mimir-vault-v1");

  const b64u = (bytes) => { let s = ""; for (const b of bytes) s += String.fromCharCode(b); return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); };
  const unb64u = (s) => { const t = s.replace(/-/g, "+").replace(/_/g, "/"); const bin = atob(t + "=".repeat((4 - (t.length % 4)) % 4)); return Uint8Array.from(bin, (c) => c.charCodeAt(0)); };
  const hex = (bytes) => [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");

  function toBase32(bytes) {
    let bits = 0, value = 0, out = "";
    for (const b of bytes) { value = (value << 8) | b; bits += 8; while (bits >= 5) { out += ALPHABET[(value >>> (bits - 5)) & 31]; bits -= 5; } }
    if (bits > 0) out += ALPHABET[(value << (5 - bits)) & 31];
    return out;
  }
  function fromBase32(text) {
    let bits = 0, value = 0; const out = [];
    for (const ch of text) { const i = ALPHABET.indexOf(ch); if (i < 0) return null; value = (value << 5) | i; bits += 5; if (bits >= 8) { out.push((value >>> (bits - 8)) & 255); bits -= 8; } }
    return Uint8Array.from(out);
  }
  async function checkChars(bytes) { return toBase32(new Uint8Array(await subtle.digest("SHA-256", bytes))).slice(0, 4); }

  const group = (s) => s.match(/.{1,4}/g).join("-");

  // A new recovery key, as the text people save and type. 160 random bits.
  async function newRecoveryKey() {
    const bytes = webcrypto.getRandomValues(new Uint8Array(20));
    return group(toBase32(bytes) + (await checkChars(bytes)));
  }

  // Typed keys come with spaces, dashes, lower case and look-alike letters: normalise, then check the check characters.
  // Returns { ok: true, bytes } or { ok: false, reason: "length" | "characters" | "typo" }.
  async function parseRecoveryKey(text) {
    const clean = String(text || "").toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
    if (clean.length !== 36) return { ok: false, reason: "length" };
    const bytes = fromBase32(clean.slice(0, 32));
    if (!bytes || bytes.length !== 20 || clean.slice(0, 32) !== toBase32(bytes)) return { ok: false, reason: "characters" };
    if ((await checkChars(bytes)) !== clean.slice(32)) return { ok: false, reason: "typo" };
    return { ok: true, bytes };
  }

  async function derive(bytes) {
    const base = await subtle.importKey("raw", bytes, "HKDF", false, ["deriveBits", "deriveKey"]);
    const bits = (label, n) => subtle.deriveBits({ name: "HKDF", hash: "SHA-256", salt: SALT, info: enc.encode(label) }, base, n);
    return {
      id: hex(new Uint8Array(await bits("mimir-vault-id-v1", 128))),
      auth: b64u(new Uint8Array(await bits("mimir-vault-auth-v1", 256))),
      key: await subtle.deriveKey({ name: "HKDF", hash: "SHA-256", salt: SALT, info: enc.encode("mimir-vault-enc-v1") }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]),
    };
  }

  // The contents are JSON, encrypted with a fresh nonce each time and bound to the vault id.
  async function seal(derived, payload) {
    const iv = webcrypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(await subtle.encrypt({ name: "AES-GCM", iv, additionalData: enc.encode(`${derived.id}|v1`) }, derived.key, enc.encode(JSON.stringify(payload))));
    const out = new Uint8Array(12 + ct.length); out.set(iv); out.set(ct, 12);
    return b64u(out);
  }
  async function open(derived, blob) {
    const raw = unb64u(blob);
    if (raw.length < 29) throw new Error("This vault is damaged.");
    try {
      const pt = await subtle.decrypt({ name: "AES-GCM", iv: raw.slice(0, 12), additionalData: enc.encode(`${derived.id}|v1`) }, derived.key, raw.slice(12));
      return JSON.parse(dec.decode(pt));
    } catch { throw new Error("That key does not open this vault."); }
  }

  // ---- merging two copies of the vault: { keys: { "mimir-library": { t: ms, d: value } } }
  const idOf = (x) => (x && typeof x === "object" ? (x.id ?? x.slug ?? JSON.stringify(x)) : JSON.stringify(x));
  function mergeValue(newer, older) {
    if (Array.isArray(newer) && Array.isArray(older)) {   // lists: union, the newer copy's entries first and winning
      const seen = new Set(newer.map(idOf));
      return [...newer, ...older.filter((x) => !seen.has(idOf(x)))];
    }
    if (newer && older && typeof newer === "object" && typeof older === "object" && !Array.isArray(newer) && !Array.isArray(older)) {
      const out = { ...older };
      for (const k of Object.keys(newer)) out[k] = k in older ? mergeValue(newer[k], older[k]) : newer[k];
      return out;
    }
    return newer;   // scalars: the newer side wins
  }
  function mergeVaults(local, remote) {
    const keys = {};
    for (const k of new Set([...Object.keys(local.keys || {}), ...Object.keys(remote.keys || {})])) {
      const a = (local.keys || {})[k], b = (remote.keys || {})[k];
      if (!a || !b) { keys[k] = a || b; continue; }
      keys[k] = a.t >= b.t ? { t: a.t, d: mergeValue(a.d, b.d) } : { t: b.t, d: mergeValue(b.d, a.d) };
    }
    return { v: 1, keys };
  }

  // ---- Passphrase-protected key backup. The recovery key is wrapped on this device and the result is a text the person keeps
  // (a file, a note, an email to themselves). Nothing is sent anywhere: the server never sees the passphrase, the wrapped key or this
  // text. PBKDF2-SHA256 slows guessing; the passphrase is the only defence if the text leaks, so weak ones are refused.
  const BACKUP_PREFIX = "MIMIR-KEY-BACKUP-1:";
  const BACKUP_AAD = enc.encode("mimir-key-backup-v1");
  const ITERATIONS = 600000;                  // OWASP guidance for PBKDF2-HMAC-SHA256
  const COMMON = ["password", "passphrase", "123456", "qwerty", "letmein", "iloveyou", "welcome", "mimir", "terratales", "abcdef", "111111", "000000"];

  // Returns "" when the passphrase is acceptable, otherwise a plain sentence saying what to change.
  function passphraseProblem(p) {
    p = String(p || "");
    if (p.length < 12) return "Use at least 12 characters. Four random words works well.";
    if (new Set(p.toLowerCase()).size < 6) return "That repeats too much. Mix it up, or use four random words.";
    const flat = p.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (COMMON.some((w) => flat.includes(w) && flat.length < w.length + 8)) return "That is too easy to guess. Four random words works well.";
    return "";
  }

  async function wrapKey(passphrase, key, iterations = ITERATIONS) {
    const problem = passphraseProblem(passphrase);
    if (problem) throw new Error(problem);
    const parsed = await parseRecoveryKey(key);
    if (!parsed.ok) throw new Error("That is not a valid recovery key.");
    const salt = webcrypto.getRandomValues(new Uint8Array(16)), iv = webcrypto.getRandomValues(new Uint8Array(12));
    const k = await passphraseKey(passphrase, salt, iterations, ["encrypt"]);
    const ct = new Uint8Array(await subtle.encrypt({ name: "AES-GCM", iv, additionalData: BACKUP_AAD }, k, parsed.bytes));
    return BACKUP_PREFIX + b64u(enc.encode(JSON.stringify({ v: 1, kdf: "PBKDF2-SHA256", i: iterations, s: b64u(salt), n: b64u(iv), c: b64u(ct) })));
  }

  // Returns the recovery key text, or throws "That passphrase does not open this backup." (wrong passphrase and damage look the same).
  async function unwrapKey(passphrase, backup) {
    const text = String(backup || "").trim().replace(/\s+/g, "");
    if (!text.startsWith(BACKUP_PREFIX)) throw new Error("That does not look like a Mimir key backup.");
    let o;
    try { o = JSON.parse(dec.decode(unb64u(text.slice(BACKUP_PREFIX.length)))); } catch { throw new Error("That backup is damaged."); }
    if (!o || o.v !== 1 || o.kdf !== "PBKDF2-SHA256" || !Number.isInteger(o.i) || o.i < 100000 || o.i > 5000000) throw new Error("That backup is damaged or from a newer version of Mimir.");
    try {
      const k = await passphraseKey(String(passphrase || ""), unb64u(o.s), o.i, ["decrypt"]);
      const bytes = new Uint8Array(await subtle.decrypt({ name: "AES-GCM", iv: unb64u(o.n), additionalData: BACKUP_AAD }, k, unb64u(o.c)));
      return group(toBase32(bytes) + (await checkChars(bytes)));
    } catch { throw new Error("That passphrase does not open this backup."); }
  }

  async function passphraseKey(passphrase, salt, iterations, usages) {
    const base = await subtle.importKey("raw", enc.encode(passphrase.normalize("NFKC")), "PBKDF2", false, ["deriveKey"]);
    return subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations }, base, { name: "AES-GCM", length: 256 }, false, usages);
  }

  return { newRecoveryKey, parseRecoveryKey, derive, seal, open, mergeVaults, mergeValue, b64u, unb64u, passphraseProblem, wrapKey, unwrapKey, BACKUP_PREFIX };
});
