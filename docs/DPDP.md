# DPDP Act compliance record (India)

**Status and limits.** This is the working record behind Mimir's privacy notice: what data exists, why, how long it is kept,
who handles it, and how each right is met. It was written from what the code does today. It is **not legal advice** and has
**not been reviewed by a lawyer**; items marked *verify with counsel* depend on the Digital Personal Data Protection Rules,
2025 and their phased commencement, which should be checked against the current text before relying on this.

Public pages generated from `demo/legal.cjs`: `/privacy/`, `/cookies/`, `/terms/`, `/data-requests/`, `/security/`.
Anything the company must still supply is shown on those pages as "To be added" and listed at the end of this file.

## Roles
- **Data Fiduciary:** Terratales Media Entertainment Private Limited (registered office on the privacy notice; phone +91 95994 85028; hello@terratalesmedia.world).
- **Data Processors:** WordPress.com / Automattic (hosts the Mimir Vault plugin and its database); GitHub (serves the static site; sees ordinary web-request data).
- **Grievance Officer:** [to be appointed].
- **Data Protection Officer / Significant Data Fiduciary:** not designated; *verify with counsel* whether any threshold applies.

## Data inventory
| Data | Where | Purpose | Basis | Kept | Processor | Leaves India? |
|---|---|---|---|---|---|---|
| Library, ratings, lists, journal, settings | Visitor's browser only | Run the product for the visitor | Not received by us | Until cleared | none | no |
| Encrypted vault (ciphertext, size, version) | Plugin database | Sync across the visitor's devices | Consent (creating an account) | Until the visitor deletes it | WordPress.com | possibly (host data centres) |
| Vault id, keyed hash of login secret | Plugin database | Locate and authenticate a vault | Consent | With the vault | WordPress.com | possibly |
| Created and last-used dates | Plugin database | Operate, optional inactivity purge | Consent | With the vault | WordPress.com | possibly |
| Consent version and analytics choice (accounts) | Plugin database | Record consent | Consent | With the vault | WordPress.com | possibly |
| Analytics counts, hashed visitor id, device class | Plugin database | Understand usage, fix bugs, decide features | Consent (opt-in) | 13 months | WordPress.com | possibly |
| Error reports (message, page, version) | Plugin database | Fix bugs and keep the service working | Legitimate use: service reliability; no identifier collected | 13 months | WordPress.com | possibly |
| Rate-limit counters (keyed hash of address) | WordPress transients | Stop abuse | Legitimate use: security | up to 1 hour | WordPress.com | possibly |
| Web-server logs (IP address, request) | Hosts' own logs | Operate and secure the hosts | Hosts' own terms | Hosts' policy | GitHub, WordPress.com | possibly |
| Emails to hello@ | Company mailbox | Reply to the sender | Consent (the sender wrote to us) | While needed | Mail provider [to be confirmed] | to be confirmed |

Not collected: names, emails, phone numbers, dates of birth, location, advertising ids, device fingerprints, what a visitor
searches for, rates or saves. No data is sold, rented or used for advertising or targeted behavioural profiling.

## Where each public statement comes from
| Statement | Source in the repository |
|---|---|
| The server cannot read vaults | `demo/vault.cjs` (HKDF-derived independent id, auth, key; AES-GCM), `docs/ACCOUNTS.md` |
| Only the listed fields are stored | `wordpress/mimir-vault/mimir-vault.php` (tables in `install()`); contract tests in `wordpress/tests/harness.php` |
| No cookies | `harness.php` (no cookie functions in the plugin); `docs/` cookie audit: the app uses localStorage and IndexedDB only |
| IP address not stored | `harness.php` ("no address and no raw visitor id is stored") |
| Analytics off until opt-in; errors need no id | `demo/page.html` (`TEL`, consent panel); plugin `telemetry()` drops non-error events without a visitor id |
| 13-month retention | plugin `purge_usage()` (`RETAIN_DAYS`), tested in `harness.php` |
| Export and delete at once | Account page; plugin `delete()` removes rows immediately |
| Global Privacy Control / Do Not Track honoured | `TEL` in `demo/page.html` |

## Rights and how they are met
| Right | How |
|---|---|
| Access / summary | Export my data (Account page); email request; the summary is this inventory |
| Correction / update | The person edits their data in the product; email request for anything else |
| Erasure and withdrawal of consent | Delete my account; Privacy choices; email request. Deleted rows leave the database at once; host backups age out per the host (*retention period to be confirmed*) |
| Grievance redressal | Grievance Officer, 7-day acknowledgement, 30-day target (*proposed; confirm*) |
| Nomination | By email; the nominee is recorded in the company's request log. Accounts are anonymous, so a nominee needs the recovery key or a deletion request |
| Complaint to the Data Protection Board | Stated on the privacy notice |
Verifying a requester without collecting more personal data: control of the vault (sign-in) is the proof for account data.

## Consent
- Asked before collection, itemised, in plain English, with accept and refuse equally easy and no feature withheld for refusing.
- Records: the choice and notice version are kept on the device (`mimir-consent`) and, for signed-in people, in the account row (`consent_version`, `consent_analytics`). A fuller consent log (timestamps per change) is not kept server-side; *decide with counsel whether one is required*.
- Notice versions: `CONSENT_VERSION` in `demo/page.html` and `VERSION` in `demo/legal.cjs`. A new version re-asks.
- Languages: English now; translation into Eighth Schedule languages planned; the notice says it can be requested.

## Children
Accounts: "I am 18 or older" tick; no account is offered otherwise. No tracking, behavioural monitoring or targeted advertising
directed at children. Analytics is opt-in and the prompt is not aimed at children. The DPDP Act requires verifiable parental
consent for processing a child's data; Mimir avoids the need by not offering accounts to under-18s and by collecting nothing
from visitors who do not opt in. A tick is not verification of age: *verify with counsel* whether this is sufficient, or whether
a different approach is needed (for example no analytics prompt on a device likely used by a child, or a verified-parent flow).

## Retention and erasure schedule
Vaults: until deleted. Usage counts, visitor hashes, error reports: 13 months, purged daily by the plugin. Rate-limit
counters: one hour. Optional purge of vaults unused for N days (Settings, Mimir Vault; off by default; minimum 90 days; the
notice must say so before it is switched on, and there is no way to warn an anonymous account holder, so *verify with counsel*).

## Security safeguards
Client-side encryption, constant-time comparison, rate limits, no cookies, no secrets in logs, TLS (host), least data
(`docs/ACCOUNTS.md`), tests in CI. Gaps: shared hosting; Premium plan has no real-time backups (add Jetpack Backup or Business);
no formal penetration test; no intrusion alerting.

## Personal data breach
See `docs/INCIDENT-RESPONSE.md`: assess, contain, notify affected people and the Data Protection Board of India in the form
and time the Rules require (*verify with counsel*), record, review.

## Risk note (DPIA-style)
| Risk | Likelihood | Impact | Controls | Residual |
|---|---|---|---|---|
| Server database stolen | Low-medium (shared hosting) | Low: only ciphertext, hashed secrets, dates | End-to-end encryption; no names or emails | Low |
| Recovery key lost | High over time | Medium: person loses synced data, keeps the on-device copy | Clear warnings; confirm-you-saved step; export | Accepted |
| Recovery key stolen | Low | High for that person | Rotate key; keep private; warnings | Medium |
| Analytics re-identifies someone | Low | Low-medium | Opt-in; no content; no IP; hashed id; 13-month limit; coarse device classes | Low |
| Child uses accounts or analytics | Medium | Medium | 18+ tick; opt-in analytics; no targeting | Medium: see Children |
| Cross-border storage | Certain (host decides) | Low | Disclosed; encrypted data | Low |
| Plugin vulnerability | Low-medium | High | Validation, prepared statements, tests, small surface | Medium until independently reviewed |

## Checklist to review with counsel
- [ ] Is a tick enough for the 18+ gate, and how should the analytics prompt treat likely children?
- [ ] Is "legitimate use" correctly relied on for error reports, rate limiting and service security, and is the no-identifier design enough?
- [ ] Notice content and form under the Act and Rules (itemised, plain language, a link to withdraw, how to complain); translations.
- [ ] Grievance Officer: who, contact, response times; Board complaint wording.
- [ ] Breach notification form, content and timelines; who files.
- [ ] Whether consent logs must be kept server-side and for how long.
- [ ] Cross-border transfer position and any restrictions by notification.
- [ ] Significant Data Fiduciary criteria; consent-manager registration (not used).
- [ ] Processor contracts with Automattic and GitHub; where the data sits; backup retention.
- [ ] Whether the inactivity purge may run without notice to anonymous account holders.
- [ ] Terms: governing law and jurisdiction, liability limits, IP and trademark wording.
- [ ] If used from the EU or UK: GDPR/UK GDPR consent, rights and representative questions. Mimir's design (opt-in analytics, export, deletion, no profiling) is intended to be compatible but makes no claim of GDPR compliance.

## Still to be supplied by the company
Grievance Officer name and contact; privacy@terratalesmedia.world mailbox; company registration (CIN) details; backup
arrangement and retention with the host; inactivity period if the purge is used; response times; jurisdiction wording;
mail provider and its location; legal review. The exact list is generated by `node -e 'console.log(require("./demo/legal.cjs").placeholders())'`
and by audit rule B003 (`python -m mde audit`).
