// The legal pages: privacy notice, cookie policy, terms, data requests and security. Plain text in a small markup (## heading,
// - list, | table |, **bold**, [text](url)); [[like this]] marks something the company must still supply. They are written to
// describe what the site really does today (docs/DPDP.md lists each statement's source) and need a lawyer's review.
"use strict";

const VERSION = "2026-10";
const UPDATED = "27 October 2026";
const OPERATOR = "Terratales Media Entertainment Private Limited";
const ADDRESS = "Third Floor situated at Mr. Balraj Singh Lohiya House No. 170 in Kh No. 393, G/F, L/S. Vill- Ghitorni Near-100 Feeta Road, New Delhi 110030";
const PHONE = "+91 95994 85028";
const EMAIL = "hello@terratalesmedia.world";
const PRIVACY_EMAIL = "[[privacy@terratalesmedia.world: create this mailbox before publishing]]";
const GRIEVANCE = "[[Name of the Grievance Officer: to be appointed and added]]";

const mailto = (subject, body) => `mailto:${EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;

const PAGES = [
  {
    slug: "privacy", title: "Privacy notice", desc: "What Mimir collects, why, how long it keeps it and how to use your rights, including under India's Digital Personal Data Protection Act.",
    md: `Mimir keeps your library on your device. This notice says exactly what Mimir does collect, why, for how long, and how you can use your rights. It is written in plain English; versions in the languages of India's Eighth Schedule are planned, and you can ask for this notice in one of them by writing to us.

## Who we are
**${OPERATOR}** ("Terratales", "we") runs Mimir and is the Data Fiduciary for the personal data described here. Registered office: ${ADDRESS}. Phone ${PHONE}. Email ${EMAIL}. Privacy contact: ${PRIVACY_EMAIL}. Company registration details: [[CIN and any other registration numbers to be added]].

## What stays on your device
Your library, ratings, lists, journal, trackers, taste edits, preferences and similar settings are stored in your browser on your own device. We do not receive them. Mimir works fully this way, with no account. The [cookie policy](/cookies/) lists every item.

## If you create an account
An account is a recovery key. Your browser encrypts your data with it before sending anything, so we cannot read what you save. The server keeps:
- a vault identifier and a keyed hash of a secret derived from your key (neither reveals the key);
- your encrypted data, its size and version;
- the date the account was created and last used;
- whether you allowed analytics, and the version of this notice you saw.
We do not ask for your name, email address, phone number or date of birth. You confirm you are 18 or older with a tick; we do not keep proof. If you lose your key we cannot recover your data.

## Analytics, only if you allow it
When you choose "Allow analytics" we count anonymous usage: a random identifier kept on your device (you can reset it), page and feature names, device type, browser, operating system, screen size class, language and how fast pages load. We never receive what you search for, rate, save or write. Your IP address is not stored: it is used only to limit abuse and is discarded. Without your permission none of this is collected.

## Error reports, always
When something breaks, Mimir may send the error message, the page name and the site version, with no identifier, so we can fix it.

## Other parties who see technical data
- **GitHub Pages** serves the Mimir site, and **WordPress.com (Automattic)** hosts the account and analytics server. Like any host, they process your IP address and request details in their own logs under their own policies.
- Cover images and thumbnails load from their original sources (for example Wikimedia, Open Library and YouTube), which can see your IP address when your browser fetches them.
- A YouTube video loads only after you press its play button, in YouTube's privacy-enhanced mode; YouTube then applies its own policy.
- If you email us, we keep your message and address to reply to you.

## Why we use your data, and your consent
We use data only for the purposes above: running accounts, keeping Mimir secure, fixing errors, and, if you allow it, learning how Mimir is used so we can improve it. We do not sell or rent data, show advertising, or build profiles to target you. Where consent is the basis you can give it or refuse it freely, with no loss of any feature, and withdraw it as easily as you gave it: use "Privacy choices" in the footer of every page.

## Your rights
Under the Digital Personal Data Protection Act, 2023 you can:
- ask for a summary of the personal data we process about you and who we share it with;
- ask us to correct, complete or update it;
- ask us to erase it and withdraw consent;
- have your grievance heard, and complain to the Data Protection Board of India if you are not satisfied;
- nominate another person to exercise these rights if you die or cannot act for yourself.
In Mimir, **Export my data** and **Delete my account** on the [Account page](/#account) do the first and third at once, for account data. For anything else, or if you cannot sign in, use [data requests](/data-requests/). Because accounts are anonymous, we can only act on a request if you can prove control of the vault, for example by signing in; we will not ask for more personal data to verify you.

## Children
Accounts are for people aged 18 or over. We do not knowingly create accounts for, track, monitor the behaviour of, or target advertising at, anyone under 18, and the analytics prompt is not meant for them. A parent or guardian who believes a child has created an account can write to us and we will delete it. Mimir works fully without an account on a child's device and collects nothing from it unless analytics is switched on.

## How long we keep data
| Data | Kept |
| Account vault | Until you delete it. Deleted at once from our database; copies in host backups age out within [[backup retention period to be confirmed with the host]] |
| Analytics counts, visitor identifiers and error reports | 13 months, then deleted |
| Rate-limit counters | Up to one hour |
| Emails you send us | While needed to deal with your request, then deleted |
| Accounts unused for a long time | We may delete them after [[inactivity period, minimum 90 days, to be decided; we will say so here before it is switched on]] |

## Keeping it safe
Account data is encrypted on your device before it is sent. The server stores only ciphertext, limits repeated guesses, sets no cookies and logs no keys. Details are on the [security page](/security/). If a personal data breach affects you, we will tell you and the Data Protection Board of India as the law requires.

## Moving data abroad
Our hosts may store data in data centres outside India. We do not restrict transfers except as the law of India requires.

## Grievances and contact
Grievance Officer: ${GRIEVANCE}. Write to ${EMAIL} (privacy contact: ${PRIVACY_EMAIL}) or to the registered office above. We will acknowledge within 7 days and aim to resolve within 30 days [[confirm response times]]. If you remain unhappy you can complain to the Data Protection Board of India.

## Changes to this notice
We will change this notice when what we do changes, and say so below. Material changes will ask for your choice again.

## Version history
- ${UPDATED} (version ${VERSION}): first published, with accounts and optional analytics.

This notice is not legal advice and has not yet been reviewed by counsel: [[legal review pending]].`,
  },
  {
    slug: "cookies", title: "Cookie policy", desc: "Mimir sets no cookies. This page lists everything it stores on your device, why, and how to change your choices.",
    md: `Mimir sets **no cookies**. To work, it stores some information on your device with your browser's local storage and IndexedDB. These work like cookies for privacy purposes, so this page lists them all and explains how to control them.

## Strictly necessary
These keep Mimir working and are not used for tracking. They stay on your device.
| Item | What it is | How long |
| mimir-library, mimir-ratings, mimir-lists, mimir-journal, mimir-trackers, mimir-challenges, mimir-activity, mimir-feedback and similar | Your library, ratings, lists, journal and other saved choices | Until you clear them or delete your data |
| mimir-prefs, mimir-theme, mimir-foryou-opts, mimir-shelf, mimir-taste-edits and similar | Your settings: theme, filters, taste edits | Until you clear them |
| mimir-swipe-count, mimir-craft, mimir-eggs, mimir-together, mimir-plan, mimir-decide and similar | Where you are in Swipe, Craft, Plan and other tools | Until you clear them |
| mimir-consent | Your privacy choice and when you made it | Until you change it |
| mimir-vault-meta | When your account last synced and which changes are waiting | Until you sign out |
| IndexedDB "mimir-vault" | If you sign in: your vault identifier and an encryption key that cannot be exported | Until you sign out |

## Optional, only with your permission
| Item | What it is | How long |
| mimir-install-id | A random identifier used to count active visitors in analytics. It is created only if you allow analytics and deleted if you say no or reset it | Until you reset or refuse; stored counts are deleted after 13 months |

## Third parties
Mimir sets no cookies of its own and uses no advertising or analytics services from other companies. If you press play on a YouTube video, YouTube loads in privacy-enhanced mode (youtube-nocookie.com) and may then store its own cookies or similar identifiers under [Google's policy](https://policies.google.com/privacy). Cover images load from their original sources, which can see your IP address.

## Your choices
- Change your analytics choice at any time with "Privacy choices" in the footer.
- Clear Mimir's data in your browser settings (this also removes your on-device library, so export it first from [Import and export](/#transfer)).
- Browsers' Global Privacy Control and Do Not Track signals are honoured: analytics stays off unless you turn it on yourself.

Related: [privacy notice](/privacy/). Version ${VERSION}, updated ${UPDATED}.

## Version history
- ${UPDATED} (version ${VERSION}): first published.`,
  },
  {
    slug: "terms", title: "Terms of use", desc: "The rules for using Mimir: acceptable use, AI-assisted readings, other people's artwork and trademarks, and the limits of what Mimir promises.",
    md: `By using Mimir you agree to these terms. Mimir is provided by **${OPERATOR}**, ${ADDRESS}.

## Using Mimir
Mimir is free and in public beta. You may use it for your own personal, lawful use. Do not misuse it: no attacks on the site or the account server, no automated scraping that degrades the service, no attempt to open other people's vaults, and no use that breaks the law.

## What Mimir tells you
Facts such as titles, years, creators and lengths come from open data where a source matches, and may be wrong or out of date. Moods, themes, subgenres and parents' guide levels are **AI-assisted readings awaiting editorial review** and are labelled that way. "Not assessed" means no one has assessed it. A parents' guide is a help, not a guarantee: check content yourself before choosing it for a child. Picks are suggestions, not advice.

## Other people's work
Posters, covers, logos and thumbnails belong to their owners and are shown to identify the work. Names, titles and marks are the property of their holders and are used only to refer to the works. Open data from Wikidata, Open Library, MusicBrainz and others is used under their licences. If you own something shown here and want it changed or removed, write to ${EMAIL}.

## Your data
Your library stays on your device unless you create an account, and then only encrypted. If you lose your recovery key we cannot recover your data. Read the [privacy notice](/privacy/) and [cookie policy](/cookies/).

## Accounts
Accounts are for people aged 18 or over. Keep your recovery key private: anyone who holds it can open your vault. You can delete your account at any time from the [Account page](/#account).

## Community content
If community features such as reviews, comments or shared lists are switched on, you are responsible for what you post, which must be lawful, must not harass or mislead others, and must not infringe anyone's rights. We may remove content that breaks these rules. These features are not switched on yet.

## No warranty, and limits
Mimir is provided as it is, without promises that it will always be available, accurate or error free. To the extent the law allows, Terratales is not liable for loss from using Mimir or relying on its picks, and nothing here limits liability that cannot be limited by law.

## Changes, law and contact
We may change these terms and will update the date and version history below. These terms are governed by the laws of India, and the courts at New Delhi have jurisdiction [[jurisdiction to be confirmed by counsel]]. Questions: ${EMAIL}, ${PHONE}.

Version ${VERSION}, updated ${UPDATED}.

## Version history
- ${UPDATED} (version ${VERSION}): first published.`,
  },
  {
    slug: "data-requests", title: "Data requests", desc: "How to see, correct or erase your data, withdraw consent, nominate someone or raise a grievance about Mimir.",
    md: `You have rights over your personal data. Most can be used straight away inside Mimir; for anything else, write to us.

## Do it yourself
- **See or take your data:** sign in on the [Account page](/#account) and choose **Export my data**. It is decrypted on your device and downloaded as a file.
- **Erase your data:** choose **Delete my account**. Your vault and everything stored for you on the server is deleted at once.
- **Withdraw or change analytics consent:** use **Privacy choices** in the footer of any page.

## Ask us
Use these ready-made emails (they open your email program; add your details in the message). Because accounts are anonymous, include the vault identifier from your key only if you are comfortable doing so; we will not ask for more personal data than we need.
- [Ask for a summary of my data](${mailto("Data request: summary of my data", "I would like a summary of the personal data Mimir processes about me.\n\nWhat I use (account or on-device only):\n")})
- [Correct or update my data](${mailto("Data request: correction", "I would like the following corrected or updated:\n")})
- [Erase my data and withdraw consent](${mailto("Data request: erasure", "I would like my data erased and my consent withdrawn.\n")})
- [Nominate someone to act for me](${mailto("Data request: nominee", "I would like to nominate the following person to exercise my rights if I die or cannot act for myself:\n")})
- [Make a complaint or raise a grievance](${mailto("Grievance", "My grievance is:\n")})

We acknowledge requests within 7 days and aim to answer within 30 days [[confirm response times]]. Grievance Officer: ${GRIEVANCE}. Privacy contact: ${PRIVACY_EMAIL}. If you are not satisfied, you can complain to the Data Protection Board of India.

Related: [privacy notice](/privacy/). Version ${VERSION}, updated ${UPDATED}.

## Version history
- ${UPDATED} (version ${VERSION}): first published.`,
  },
  {
    slug: "security", title: "Security", desc: "How Mimir protects account data: end-to-end encryption, no cookies, abuse limits, and how to report a problem.",
    md: `A summary of how Mimir protects data. It is meant to be checkable: the code is in the project's repository.

## Encrypted on your device
- An account is a random 160-bit recovery key. Your browser derives from it a vault identifier, a login secret and an AES-256-GCM encryption key using HKDF-SHA256. The three are independent, so the server, which sees the first two, cannot work out the third.
- Your data is encrypted in the browser with a fresh nonce each time and bound to your vault identifier. The server stores only ciphertext.
- The encryption key is held in your browser as a key that cannot be exported.

## On the server
- The login secret is stored only as a keyed hash and compared in constant time. An unknown vault and a wrong secret get the same answer.
- Repeated wrong attempts are limited per connection and per vault; creating vaults and saving are limited too.
- No cookies are set, no keys or contents are logged, and IP addresses are not stored.
- Analytics is separate from your vault, off until you allow it, and holds counts only.

## Limits you should know
- Anyone who holds your recovery key can open your vault; keep it private. If you lose it, nobody can recover your data.
- The server operator can see that a vault exists, its size and when it was last used, and can delete it.
- The server runs on shared WordPress.com hosting. We rely on the host for network and physical security, for keeping PHP and WordPress patched, and for daily backups [[how long backups are kept, to be confirmed with the host]].

## If something goes wrong
We keep a written [incident response plan](https://github.com/RedZero13/Mimir-An-Universal-Media-Discovery-and-Intelligence-Tool/blob/main/docs/INCIDENT-RESPONSE.md). If a personal data breach affects you we will tell you, and the Data Protection Board of India, as the law requires.

## Reporting a problem
Found a security problem? Email ${EMAIL} with "Security" in the subject. Please give us reasonable time to fix it before sharing details. We do not currently run a bounty programme.

Related: [privacy notice](/privacy/). Version ${VERSION}, updated ${UPDATED}.

## Version history
- ${UPDATED} (version ${VERSION}): first published.`,
  },
];

const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const inline = (s) => esc(s)
  .replace(/\[\[([^\]]+)\]\]/g, '<mark class="todo">To be added: $1</mark>')
  .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, text, href) => `<a href="${href.replace(/&amp;/g, "&amp;")}">${text}</a>`);

function render(md) {
  const out = [];
  let list = [], para = [], table = [];
  const flush = () => {
    if (list.length) out.push(`<ul>${list.map((l) => `<li>${inline(l)}</li>`).join("")}</ul>`);
    if (para.length) out.push(`<p>${inline(para.join(" "))}</p>`);
    if (table.length) {
      const rows = table.map((l) => l.replace(/^\||\|$/g, "").split(" | ").map((c) => c.trim()));
      out.push(`<div class="tbl"><table><thead><tr>${rows[0].map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${rows.slice(1).map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    }
    list = []; para = []; table = [];
  };
  for (const line of md.split("\n")) {
    if (line.trim() === "") flush();
    else if (line.startsWith("## ")) { flush(); out.push(`<h2>${inline(line.slice(3))}</h2>`); }
    else if (line.startsWith("- ")) { if (!list.length) flush(); list.push(line.slice(2)); }
    else if (line.startsWith("|")) { if (!table.length) flush(); table.push(line); }
    else { if (list.length || table.length) flush(); para.push(line); }
  }
  flush();
  return out.join("\n");
}

/** Placeholders still to be filled, for the audit and the final report. */
const placeholders = () => PAGES.flatMap((p) => [...p.md.matchAll(/\[\[([^\]]+)\]\]/g)].map((m) => ({ page: p.slug, text: m[1] })));

module.exports = { PAGES, VERSION, UPDATED, render, placeholders, esc };
