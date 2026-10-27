# Accounts: the encrypted vault

A Mimir account is a **recovery key**. There is no email, no password and no profile. The browser encrypts everything
before it leaves the device, so the server holds ciphertext it cannot read. This page explains the design, the server
contract, how to install the server side, and what is still to come.

Status: vault, sync, the Account page, opt-in analytics with a consent panel, and the legal pages are built. Sign in with
Google, Apple and Meta is not (see "Not built yet").

## How it works
1. **Create.** The browser makes a random 160-bit recovery key and shows it once, as nine groups of four characters
   (`XXXX-XXXX-…`), with Copy, Download and Print. The last four characters are check characters, so a typo is caught
   before any request is made. The vault is only created after the person confirms they saved the key.
2. **Derive.** From the key, HKDF-SHA256 produces three independent values (`demo/vault.cjs`):
   `id` (names the vault), `auth` (proves you hold the key) and `enc` (an AES-256-GCM key). The server sees `id` and
   `auth`; it cannot work out `enc` or the key. `enc` is held as a non-extractable key in the browser's IndexedDB.
3. **Seal.** Everything under the `mimir-*` storage keys (library, ratings, lists, journal, trackers, taste edits, rings,
   preferences, craft and swipe state) is gathered as one JSON document and encrypted with a fresh nonce, bound to the
   vault id. Per-device keys (theme, session, visit counts, the sync bookkeeping) are not synced.
4. **Store.** The plugin keeps `id`, a keyed hash of `auth`, the ciphertext, a version number, its size and two dates
   (created, last used). Nothing else.
5. **Sync.** Changes are pushed a few seconds after they are made, on load, when the device comes back online and when
   the tab is hidden. Each sync pulls, merges, and pushes with `if_match = version`; if another device saved first the
   server answers 409 with its copy and the browser merges again.

**Merging.** Each synced key carries the time it was last changed on that device. The newer side wins a key; objects
merge field by field; lists are combined by `id` (or `slug`) with the newer copy winning; removing a key is recorded as a
newer change. Known limit: removing one item from a list on one device is not carried to another device, because lists
are combined. Clearing a whole key is.

**Honest limits.** A lost key cannot be recovered by anyone. Anyone who holds the key can open the vault. The server
operator can see that a vault exists, its size and when it was last used, and can delete it. Signing in on a new device
needs the key; social sign-in (when added) will find the account but cannot decrypt it.

## Server contract (`/wp-json/mimir/v1`)
All calls are JSON. Secrets travel in the body of a POST, never in a URL. `id` is 32 hex characters, `auth` 43 base64url
characters, `blob` base64url text of at most 2 MB. Errors use WordPress's shape: `{ code, message, data: { status } }`.

| Call | Body | Success | Errors |
|---|---|---|---|
| `GET /health` | | 200 `{ ok, service, version, max_blob }` | |
| `POST /vault/create` | `id, auth, blob, consent_version?, analytics?` | 201 `{ version, updated }` | 409 `exists`, 429 `rate_limited`, 400 |
| `POST /vault/open` | `id, auth` | 200 `{ blob, version, updated }` | 401 `bad_key`, 429 |
| `POST /vault/save` | `id, auth, blob, if_match` | 200 `{ version, updated }` | 409 `conflict` with `data: { blob, version, updated }`, 401, 429 |
| `POST /vault/rotate` | `id, auth, blob, new_id, new_auth` | 200 `{ version, updated }` | 409 `exists`, 401 |
| `POST /vault/consent` | `id, auth, consent_version, analytics` | 200 `{ saved: true }` | 401 |
| `POST /telemetry` | `{ vid?, ver, start?, device, browser, os, screen, lang, events[] }` | 202 `{ kept }` | 413 `too_large`, 429 |
| `POST /vault/delete` | `id, auth` | 200 `{ deleted: true }` | 401 |

An unknown id and a wrong secret answer identically and take the same time. Wrong attempts are limited to 20 per 15
minutes per connection and per vault; creating vaults to 10 per hour per connection; saving to 240 per hour per vault.
The limits use WordPress transients keyed by a keyed hash of the address, so no address is stored. The plugin sets no
cookies and logs nothing. Browsers may call it from `https://mimir.terratalesmedia.world` (filter `mimir_vault_origins`).

## Installing the server side (you do this)
Mimir Vault is one PHP file: `wordpress/mimir-vault/mimir-vault.php`. Build the two install forms with
`python3 wordpress/build.py` (writes `wordpress/dist/mimir-vault.zip` and `mimir-vault-snippet.php`; neither is committed).

**Which WordPress plan.** Your WordPress.com plans page showed `terratalesmedia.world` on **Premium**. Premium lists
"extend your site with WordPress plugins" and already runs plugins such as ACF and Site Kit, but SFTP/SSH, WP-CLI, GitHub
deployments and real-time backups belong to Business. It is not certain a Premium site accepts an uploaded plugin ZIP, so
there are two ways in. Try them in order:

1. **Upload the plugin.** WordPress admin, Plugins, Add New, Upload Plugin, choose `mimir-vault.zip`, Install, Activate.
   If there is no Upload Plugin button, your plan does not allow it: use step 2, or upgrade to Business.
2. **Paste the snippet.** Install **Code Snippets** or **WPCode** from the plugin directory, add a new PHP snippet, paste
   the contents of `mimir-vault-snippet.php`, set it to run everywhere, save and activate.

Then check it works: open `https://terratalesmedia.world/wp-json/mimir/v1/health` in a browser. You should see
`{"ok":true,"service":"mimir-vault",…}`. Tables are created on first use. Visit Settings, Mimir Vault to see totals only
(vaults, new and active counts, space used) and to switch on automatic deletion of vaults unused for N days (off by
default; say so in the privacy notice before turning it on).

The deployed site already points at `https://terratalesmedia.world/wp-json/mimir/v1`. Build with `MIMIR_VAULT_URL=<url>`
to use another address, or `MIMIR_VAULT_URL=off` to switch accounts off. Until the endpoint answers, the Account page says
plainly that accounts aren't connected yet.

**Backups and data loss.** Checked on 27 October 2026 with the WordPress.com tools (read only): Jetpack Backup is active on
`terratalesmedia.world`, with a daily backup (137 so far, the latest on 26 October) and a malware scan that found nothing. That is
daily, not real-time: a restore could lose up to a day of vault changes (people keep their on-device copy). Confirm in
WordPress.com that a restore works and how long backups are kept before inviting many people to use accounts; the privacy notice
has a placeholder for the retention period.

## PHP security advisory (October 2026)
PHP shipped emergency fixes on 21 October 2026 for CVE-2026-109618 and CVE-2026-109619, two critical vulnerabilities (CVSS 9.2) in
PHP itself that allow unauthenticated remote code execution and, per Qualys, disclosure of worker memory. The fixed releases are
PHP 8.5.12, 8.4.27, 8.3.36 and 8.2.35; branches older than 8.2 are end of life and get no fix. Sources:
[CyberScoop](https://cyberscoop.com/php-emergency-patches-php2shell-vulnerabilities/), [Qualys](https://blog.qualys.com/vulnerabilities-threat-research/2026/10/20/php-announces-critical-security-release-for-two-vulnerabilities),
[Tenable](https://www.tenable.com/blog/php2shell-cve-2026-109618-cve-2026-109619-frequently-asked-questions-about-critical-php-remote),
[Snyk](https://snyk.io/blog/php-patches-critical-unauthenticated-rces/). A later report says exploitation has begun; verify against CISA's catalogue.

What this means here:
- **The Mimir site** (`mimir.terratalesmedia.world`) is static files on GitHub Pages and runs no PHP: not affected.
- **The account server** runs on the host's PHP. On WordPress.com the host (Automattic) patches PHP; you cannot patch it yourself, and
  on the Premium plan you cannot choose the version either. **Check:** WordPress admin, Tools, Site Health, Info, Server, "PHP
  version"; if it is below the fixed release for its branch, ask WordPress.com support to confirm the platform fix is applied. The
  plugin cannot read or change this beyond a warning: Settings, Mimir Vault, and an admin notice show an advisory when the PHP
  version is end of life or below the fixed release (it never appears to visitors).
- **Exposure of vault data is limited by design.** A compromised PHP process could see the login secret and the encrypted vault
  of anyone who used the server in that window, but not the recovery key or the encryption key, which never leave the browser. If
  the host confirms its PHP was unpatched while exploited, tell account holders to make a new recovery key (Account page, Make a new key).
- **Other PHP:** this repository's only PHP is the plugin and its tests (`wordpress/tests`), which take no outside input. Run them on a
  patched PHP (8.3.36 or newer); the API itself is Python.
- Keep WordPress core and plugins current as usual; updating them does not update PHP.
**Do not** complete the Premium checkout for `piyushbanerjee370-cirgk.wordpress.com` or connect `terratalesmedia.world`
to a different site. That could take the Terratales site offline and change DNS records that
`mimir.terratalesmedia.world` (GitHub Pages) and `akashic.terratalesmedia.world` rely on. Confirm the plan under
WordPress.com, Upgrades, and check DNS before and after any change.

**Limits of shared hosting.** Requests share PHP resources and time out after about 30 seconds; there are no websockets,
so live features such as watch-alongs will poll. The vault format does not depend on WordPress: moving to a dedicated
server later means re-pointing `MIMIR_VAULT_URL`; nobody has to do anything.

**Processor.** The host is WordPress.com (Automattic). Name it as a processor in the privacy notice, with the note that
data is stored in its data centres, possibly outside India.

## Community features
Reviews, shared lists and hosted watch-alongs need the Python community API (`docs/DEPLOY.md`), which cannot run on
WordPress. They stay switched off until it is hosted or ported, and the Help centre says so. The account never sends vault
contents to the community API.

## Testing
- `node demo/vault.test.cjs`: key format, typo detection, round trip, wrong key, tampering, binding to the vault id, merge rules.
- `php wordpress/tests/harness.php`: runs the real plugin file against a stand-in for WordPress (sqlite) and checks the contract above, the limits and that no secret is stored or logged.
- `api/tests/test_vault.py` runs both in CI, and lints the built zip and snippet.
- Browser flow (create, wrong and mistyped keys, second device, merge, export, change key, sign out, delete):
  `MIMIR_VAULT_URL=http://127.0.0.1:8099/wp-json/mimir/v1 node demo/build.cjs --site /tmp/site`,
  serve `/tmp/site` on port 8094, run `MIMIR_TEST_STATE=/tmp/wp-state php -S 127.0.0.1:8099 wordpress/tests/serve.php`, then `node wordpress/tests/e2e.cjs`.

## Analytics and consent
Off until the visitor chooses. The consent panel appears a few seconds after a first visit (never over the first paint),
with "Allow analytics" and "No thanks" equally easy, a plain list of what is collected, and a note when the browser sends a
Global Privacy Control or Do Not Track signal (analytics then stays off unless the person turns it on). "Privacy choices" in
every footer reopens it; the choice is stored on the device (`mimir-consent`) and, for signed-in people, in the account row.

- **Without consent:** only error reports (message, page name, site version; no id) are sent.
- **With consent:** a random per-install id (kept on the device, resettable, deleted on refusal), page names (never titles),
  a few feature names, device class, browser and system family, screen class, language and a page-speed bucket. No
  content, no search text, no address stored.
- **Server (`POST /telemetry`):** validates every field against fixed lists, rate-limits, stores daily counters, a hashed
  visitor id (keyed hash, not reversible), and error counts. Everything older than 13 months is deleted daily.
- **Reading it:** WordPress admin, Settings, Mimir Vault: active visitors per day, week and month, new visitors,
  retention, device mix, pages, features, speed and errors. Totals only.

## Legal pages
`/privacy/`, `/cookies/`, `/terms/`, `/data-requests/` and `/security/` are generated by `demo/legal.cjs`, linked from every
footer and the sitemap, and written from what the code does. `docs/DPDP.md` is the compliance record (data inventory, rights,
retention, risks, checklist for counsel) and `docs/INCIDENT-RESPONSE.md` the breach plan. Anything the company must supply
shows on the pages as "To be added" and is listed by audit rule B003. They have not been reviewed by a lawyer.

## Not built yet
- Sign in with Google, Apple and Meta. End-to-end encryption means a provider login can only find an account, not unlock it:
  a new device still needs the recovery key. It also needs OAuth apps you register (Google Cloud console, an Apple
  Developer account with a Services ID and key, a Meta developer app with business verification). Say whether you still
  want it before it is built; a passphrase-wrapped key backup is an alternative that restores without the key but is weaker.
- Age handling beyond the "I am 18 or older" tick (verifiable parental consent): a question for counsel.
