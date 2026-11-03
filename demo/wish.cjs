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
  return { rate, dist, cdf, featuredWithin, pullsFor, expected };
});
