# Putting Mimir on terratalesmedia.world

terratalesmedia.world is a WordPress.com site. Mimir is a separate single-page app, so it goes on its own
subdomain, **mimir.terratalesmedia.world**, and the main site links to it. That matches the brand
architecture: an endorsed venture with its own product surface (Vol. I §12, Vol. II §14).

Hosting is GitHub Pages from this repository. It's free, uses HTTPS and has no servers to run. The workflow
`.github/workflows/pages.yml` builds the site with `node demo/build.cjs --site` on every push to `main`.

## One-time setup

1. **Merge the work into `main`.** Pages deploys from the default branch.
2. **Turn on Pages:** in the repository, go to **Settings → Pages → Build and deployment → Source** and choose
   **GitHub Actions**. (Pages on a private repository needs a paid GitHub plan; otherwise make the repository
   public.) The next push to `main` (or **Actions → Deploy Mimir site → Run workflow**) publishes it.
3. **Add the DNS record** where terratalesmedia.world's DNS is managed. If the domain uses WordPress.com's name
   servers, that's **Upgrades → Domains → terratalesmedia.world → DNS records → Add a record**:

   | Type | Name | Value |
   | --- | --- | --- |
   | CNAME | `mimir` | `redzero13.github.io` |

   This leaves the main site untouched; it only adds the `mimir.` subdomain.
4. **Confirm the domain in GitHub:** in **Settings → Pages → Custom domain**, it should show
   `mimir.terratalesmedia.world` (the build ships a `CNAME` file). Once the DNS check passes, tick
   **Enforce HTTPS**. DNS and certificates can take from a few minutes to a few hours.

To use a different subdomain, change `SITE_URL` in `demo/build.cjs` and the DNS record name to match.

## Linking from the main site

Suggested placements, in keeping with how Akashic Records is presented:

- **Header menu:** add *Mimir*, linking to `https://mimir.terratalesmedia.world/`.
- **Footer:** under the realms, add a *Ventures* group with *Akashic Records* and *Mimir*.
- **"The Standing Tree" section:** a card. Paste this into a *Custom HTML* block:

```html
<a href="https://mimir.terratalesmedia.world/" style="display:block;text-decoration:none;border:1px solid rgba(216,192,132,.16);border-radius:6px;padding:28px;background:#131315">
  <span style="font:600 12px Cinzel,serif;letter-spacing:.34em;color:#C0902F">A TERRATALES VENTURE</span>
  <span style="display:block;font:500 2rem/1.15 'Cormorant Garamond',serif;color:#EDE3CC;margin:10px 0 8px">Mimir: drawn from the well of every story</span>
  <span style="display:block;font:300 1rem/1.6 Inter,sans-serif;color:#9A8E72">Films, books, games and music, found by how they feel, with the reasons for every pick.</span>
  <span style="display:inline-block;margin-top:16px;font:600 11px Cinzel,serif;letter-spacing:.2em;color:#D8B24A">SEEK →</span>
</a>
```

## Accounts and community (the API)

The site works on its own: library, journal, lists, calendar and Decide for me live in each browser. Accounts,
reviews, follows, the feed and challenge leaderboards need the API (`api/`, FastAPI and PostgreSQL) on a server.

1. **Host the API and a database.** The repository has a Render blueprint (`render.yaml`): in Render choose
   **New → Blueprint**, pick this repository, and it creates `mimir-api` (from `api/Dockerfile`) and a Postgres
   database. The container applies migrations and loads the catalogue on every start (both idempotent). Any host
   that runs a Docker image with a `DATABASE_URL` works the same way (Fly.io, Railway, a VM).
2. **Allow the site to call it.** `CORS_ORIGINS` must include `https://mimir.terratalesmedia.world` (the blueprint
   sets it).
3. **Point the site at it.** In GitHub: **Settings → Secrets and variables → Actions → Variables → New repository
   variable**, name `MIMIR_API_URL`, value the API's address (for example `https://mimir-api.onrender.com`, or a
   subdomain such as `https://api.mimir.terratalesmedia.world` with a CNAME to the host). Then re-run **Deploy
   Mimir site**. Sign-in, reviews and the community pages appear; without the variable they stay hidden.
4. **Before opening sign-ups widely:** add a privacy notice and terms of use, a moderation routine for the
   `report` table, and email verification and password reset (not built yet: they need an email-sending service).

## What is deployed

The static site runs the discovery engine in the browser on the beta catalogue (503 works) with the open-data
enrichment committed in `api/mde/data/enrichment/`. Ratings and feedback stay in each visitor's browser.
The full stack (PostgreSQL, the API and the Next.js app in `web/`) needs a server host; see the README. When it's live, point the same subdomain at it instead.
