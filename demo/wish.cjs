// Mimir wish maths: the chance of a 5-star in gacha games with a rising rate and a hard pity. Pure, so the app and the tests share it.
//
// A rule is { base, soft, step, hard, featured }: `base` the 5-star rate in percent before the soft pity, `soft` the first pull whose rate
// rises, `step` how many percentage points each later pull adds, `hard` the pull on which a 5-star is certain, `featured` the chance that
// a 5-star is the featured one (0.5 for a 50/50, 0.75 for a 75/25, 1 when it always is, 0 on a standard banner).
"use strict";
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MimirWish = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  // The chance that pull number n since the last 5-star is a 5-star.
  const rate = (r, n) => (n >= r.hard ? 1 : n >= r.soft ? Math.min(1, r.base / 100 + (n - r.soft + 1) * r.step / 100) : r.base / 100);
  // dist[k] = the chance that the next 5-star comes on exactly the k-th pull from now, starting at `pity` pulls since the last one.
  function dist(r, pity) {
    const out = [0];
    let alive = 1;
    for (let k = 1; k + pity <= r.hard; k++) { const p = rate(r, pity + k); out[k] = alive * p; alive *= 1 - p; }
    return out;
  }
  const cdf = (d, n) => { let s = 0; for (let k = 1; k <= Math.min(n, d.length - 1); k++) s += d[k]; return s; };
  // The chance of the featured 5-star within n pulls. The next 5-star is featured with probability `featured` (surely, if guaranteed);
  // after an off-banner one, the following 5-star is guaranteed to be the featured one, counted from a fresh pity.
  function featuredWithin(r, pity, guaranteed, n) {
    const d1 = dist(r, pity), d0 = dist(r, 0);
    if (guaranteed || r.featured >= 1) return cdf(d1, n);
    let p = r.featured * cdf(d1, n);
    for (let k = 1; k < d1.length && k <= n; k++) p += (1 - r.featured) * d1[k] * cdf(d0, n - k);
    return p;
  }
  const pullsFor = (r, pity, guaranteed, target) => { for (let n = 1; n <= 400; n++) if (featuredWithin(r, pity, guaranteed, n) >= target) return n; return null; };
  const expected = (r, pity) => dist(r, pity).reduce((a, x, k) => a + x * k, 0);

  // ---------------------------------------------------------------- importing a wish history
  // What each game's history is split into. The banner keys are the tracker's own (see catalogue/game-trackers.json).
  const GAMES = {
    "genshin-impact": { types: { 301: "character", 400: "character", 302: "weapon", 200: "standard" }, fetch: [301, 302, 200], host: /^https:\/\/[a-z0-9-]+\.(hoyoverse|mihoyo)\.com\//i,
      // 5-stars that live in the permanent pool: getting one on an event banner means the 50/50 was lost. Newer additions can be missing.
      permanent: { character: ["Jean", "Qiqi", "Mona", "Keqing", "Diluc"],
        weapon: ["Amos' Bow", "Skyward Harp", "Lost Prayer to the Sacred Winds", "Skyward Atlas", "Primordial Jade Winged-Spear", "Skyward Spine", "Skyward Pride", "Wolf's Gravestone", "Skyward Blade", "Aquila Favonia"] } },
    "honkai-star-rail": { types: { 11: "character", 12: "lightcone", 1: "standard" }, fetch: [11, 12, 1], host: /^https:\/\/[a-z0-9-]+\.(hoyoverse|mihoyo)\.com\//i,
      permanent: { character: ["Himeko", "Welt", "Bronya", "Gepard", "Clara", "Yanqing", "Bailu"] } },
  };
  const ASCENDING = (a, b) => (a.id.length - b.id.length) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0);

  // A pasted history link, checked before anything is sent: only the games' own hosts, over https, carrying an authkey.
  function parseLink(text, game) {
    const g = GAMES[game];
    let u;
    try { u = new URL(String(text || "").trim()); } catch { return { error: "That does not look like a link." }; }
    if (!g || !g.host.test(`${u.origin}/`)) return { error: "Only links on the game's own HoYoverse address are used. The link is not sent anywhere else." };
    if (!u.searchParams.get("authkey")) return { error: "The link has no authkey. Open the in-game wish history, then copy the link from the history page." };
    for (const k of ["page", "size", "end_id", "gacha_type", "gacha_id", "timestamp"]) u.searchParams.delete(k);
    return { base: `${u.origin}${u.pathname}`, params: u.searchParams };
  }
  // History items from any of the shapes tools produce: the game's own response (one or several), UIGF v2/v3 (a "list") or v4 (a list per game).
  // `names` maps a game item id to {name, rarity} for exports that carry ids only (UIGF v4).
  function itemsFrom(data, game, names) {
    const out = [];
    const take = (list) => { for (const x of list || []) if (x && x.id != null) out.push(x); };
    const walk = (d) => {
      if (Array.isArray(d)) { if (d.length && d[0] && d[0].id != null && (d[0].gacha_type != null || d[0].uigf_gacha_type != null)) take(d); else d.forEach(walk); return; }
      if (!d || typeof d !== "object") return;
      if (d.data && d.data.list) take(d.data.list);
      else if (Array.isArray(d.list)) take(d.list);
      const key = game === "genshin-impact" ? "hk4e" : game === "honkai-star-rail" ? "hkrpg" : null;
      if (key && Array.isArray(d[key])) d[key].forEach((acc) => take(acc.list));
    };
    walk(data);
    return out.map((x) => {
      const known = names && x.item_id != null ? names[String(x.item_id)] : null;
      return { id: String(x.id), type: Number(x.uigf_gacha_type || x.gacha_type), rank: Number(x.rank_type || (known && known.rarity) || 3), name: x.name || (known && known.name) || "", time: x.time || "" };
    });
  }
  // Histories per banner, oldest first, with each 5-star marked featured (f: true) or from the permanent pool (f: false) where that is known.
  function banners(items, game) {
    const g = GAMES[game], out = {}, seen = new Set();
    for (const it of items.sort(ASCENDING)) {
      const key = g.types[it.type];
      if (!key || seen.has(it.id)) continue;
      seen.add(it.id);
      const pull = { id: it.id, t: Date.parse(`${String(it.time).replace(" ", "T")}Z`) || 0, r: it.rank, n: it.name };
      const perm = g.permanent && g.permanent[key];
      if (it.rank === 5 && perm && key !== "standard") pull.f = !perm.includes(it.name);
      (out[key] = out[key] || []).push(pull);
    }
    return out;
  }
  return { rate, dist, cdf, featuredWithin, pullsFor, expected, GAMES, parseLink, itemsFrom, banners };
});
