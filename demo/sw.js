// Mimir service worker: the app works offline after the first visit (your library lives in this browser anyway).
// Pages are network-first so a deploy shows up at once; icons and fonts are cache-first. API calls are never cached.
const CACHE = "mimir-__VERSION__";
const SHELL = ["/", "/site.webmanifest", "/favicon.svg", "/favicon-32.png", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];
const FONT_HOSTS = ["fonts.googleapis.com", "fonts.gstatic.com"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith("mimir-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (req.mode === "navigate") {
    // Each page is cached under its own path (the app at "/", blog posts at /blog/...), and the app is the fallback.
    event.respondWith(fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(url.pathname, copy)); }
      return res;
    }).catch(() => caches.match(url.pathname).then((hit) => hit || caches.match("/"))));
    return;
  }
  const sameOrigin = url.origin === self.location.origin;
  if ((sameOrigin && SHELL.includes(url.pathname)) || FONT_HOSTS.includes(url.hostname)) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
      return res;
    })));
  }
});
