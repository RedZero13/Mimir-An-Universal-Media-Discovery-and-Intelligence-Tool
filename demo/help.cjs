// The Help centre's content: categories, the 20 guides and the FAQ. Shared by the app (as window.MimirHelp) and the build,
// which writes each guide as its own static page. Bodies are HTML; links use the app's #routes, and {{feedback}} is replaced by
// the feedback address where the guide is shown.
"use strict";
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.MimirHelp = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
const HELP_CATS = [
  ["start", "Getting started", "What Mimir is and the quickest way in."],
  ["find", "Finding something", "Ask, decide, swipe, spin, craft and browse."],
  ["library", "Your library", "Track what you watch, read, play and hear."],
  ["taste", "Taste and picks", "How recommendations work and how to steer them."],
  ["community", "Days and community", "Calendars, days of the year and sharing."],
  ["data", "Privacy and your data", "What is stored, where, and how to reset it."],
];
// [id, category, title, summary, html body, keywords]
const HELP = [
  ["what-is-mimir", "start", "What Mimir is", "A catalogue and a guide, for films, TV, books, games, music and YouTube.",
    `<p>Mimir is a free catalogue and discovery engine. Describe a mood, a favourite or how much time you have and it returns a few picks, each with the reasons it fits. It is also a catalogue you can browse by medium, shelf, tag, person and franchise.</p>
     <p>Every reason Mimir shows is marked as a recorded fact or an editorial reading, so you can see what is known and what is interpreted.</p>`, "about catalogue guide overview"],
  ["first-five-minutes", "start", "Your first five minutes", "The fastest way to get picks that feel like yours.",
    `<ol><li>Open <a href="#swipe">Swipe</a> and go through ten cards: right to like, up to love, left for not for me, down to skip what you have not seen.</li>
     <li>Open <a href="#for-you">For you</a> to see picks built from those swipes, each with a Why? link.</li>
     <li>Or type what you want on the home page, for example "a cosy mystery, under two hours".</li>
     <li>Save anything you like to your <a href="#library">Library</a>.</li></ol>
     <p class="help-tip">Ratings stay in this browser. Nothing needs an account.</p>`, "start begin new tutorial swipe"],
  ["get-around", "start", "Getting around the site", "The menu, the search box and the footer.",
    `<p>The top menu groups the site: Discover, Films, TV, Books, Games, YouTube, Music, Sagas, Library, Community and Catalogue. The search box has a scope picker, so you can search everything, one medium, people or tags. Ask Mimir takes a whole sentence.</p>
     <p>The footer repeats every section and lists the most-reviewed works. On a phone, open the menu with the ☰ button.</p>`, "menu navigation search footer"],
  ["ask-mimir", "find", "Ask Mimir in your own words", "Moods, themes, things to avoid, time limits.",
    `<p>On the home page, write what you want: "something slow and sad, a book, not too long", "a film like Arrival", "a game for twenty minutes". Mimir shows how it read the request as chips (wanted, avoided, limits) so you can see and correct it.</p>
     <ol><li>Type your request and press Ask Mimir.</li><li>Check the chips under the box; remove or add one to adjust.</li><li>Open a pick to see why it fits.</li></ol>
     <p class="help-tip">The <a href="#mix">mood mixer</a> builds a request for you from moods you tap.</p>`, "ask search request prompt natural language"],
  ["decide-for-me", "find", "Decide for me", "Pick one thing when you cannot choose.",
    `<p><a href="#decide">Decide for me</a> chooses one work, using up to three moods and your time. Press again for another. Not tonight? Say so and it remembers.</p>`, "decide random pick one"],
  ["swipe", "find", "Swipe to teach Mimir your taste", "Like a dating app, for films, books and games.",
    `<p><a href="#swipe">Swipe</a> shows one work at a time. Right likes, up loves, left is not for me, down skips. Use arrow keys, the buttons or a drag. Z undoes. Each swipe is saved as a rating, and the next card is chosen to teach Mimir something new about you.</p>`, "swipe tinder bumble cards rate"],
  ["spin", "find", "No time to browse: spin a mood", "Pick a mood, spin the posters, watch the countdown.",
    `<p>On <a href="#spin">Don't have time to browse?</a> pick a mood card (Comfort, Laugh out loud, Edge of the seat, After dark and more). Right spins that mood's posters like a slot machine, lands on one title and opens it after a three-second countdown. Left tries another mood.</p>`, "spin slot machine mood quick"],
  ["craft", "find", "Craft a recommendation", "Combine works, moods and genres into something new.",
    `<p>On <a href="#craft">Craft</a>, drag one piece onto another, or tap two and press Combine. Works, moods, genres and mediums blend into a hybrid such as "Comforting science fiction", and Mimir finds the works that carry the most of it. Keep a blend and combine it again.</p>`, "craft infinite craft combine mix hybrid"],
  ["browse", "find", "Browse by medium, shelf, tag and person", "Directories, 36 shelves, sagas, tags and people.",
    `<p>Use <a href="#films">Films</a>, <a href="#tv">TV</a>, <a href="#books">Books</a>, <a href="#games">Games</a> or <a href="#albums">Music</a> for directories with filters. <a href="#shelves">Shelves</a> are hand-named groups such as Laugh Riot or Fright Club. <a href="#series">Sagas</a> gather a whole franchise on one page with a row per medium. <a href="#tags">Tags</a> and <a href="#people">People and studios</a> let you wander by quality or by creator.</p>`, "browse directory shelves sagas franchise tags people"],
  ["work-page", "find", "Reading a work page", "Tags, parents' guide, credits, where to watch.",
    `<p>Each work page shows its summary, an Experience DNA (moods, themes, pacing and style), a parents' guide, credits including lead cast, and links to where you can watch, read, play or listen. Tags on a page lead to other works with the same quality. Where a parents' guide says "Not assessed", it has not been reviewed yet; it does not mean safe.</p>
     <p>Press Compare on a work page to put two works side by side.</p>`, "work page parents guide tags credits where to watch compare"],
  ["library-basics", "library", "Using your library", "Status, score, progress, notes, diary.",
    `<ol><li>On any work, choose a status: Planned, In progress, Done and so on.</li><li>Add a score, progress and notes if you like.</li><li>Open <a href="#library">Library</a> and switch tabs for All, In progress, Planned or Diary.</li></ol>`, "library status score progress diary"],
  ["lists-sharing", "library", "Lists, trackers and sharing", "Share a list, a playlist or a directory with a link.",
    `<p>Make <a href="#lists">lists</a> of anything and share them with a link. <a href="#trackers">Custom trackers</a> follow things Mimir does not, like "films watched with Dad". Share buttons show how many times you have shared something.</p>`, "lists trackers share link playlist"],
  ["import-export", "library", "Import from MyAnimeList, IMDb, Letterboxd or Goodreads", "Bring your history with you.",
    `<ol><li>Open <a href="#transfer">Import &amp; export</a>.</li><li>Choose the service and upload its export file.</li><li>Review the matches and confirm.</li></ol>
     <p>The same page saves a backup of your library you can restore later.</p>`, "import export backup mal imdb letterboxd goodreads"],
  ["rings-badges", "library", "Rings, streaks and badges", "Daily rings, visit streaks, share and easter-egg badges.",
    `<p><a href="#achievements">Rings and badges</a> track what you finish, how many days in a row you open Mimir and how often you share. Some covers hide easter eggs; finding them earns badges, and the page shows how many you have found without saying where.</p>`, "badges achievements streak rings easter eggs"],
  ["how-picks-work", "taste", "How picks are made", "Tags, your ratings and the reasons shown.",
    `<p>Every work is tagged against a controlled vocabulary. Mimir matches your request, then your ratings, to those tags, respects your limits and spreads its picks so one creator does not fill the list. Press Why? on a pick to see each shared quality and how strongly it counts.</p>`, "recommendations why algorithm tags explain"],
  ["steer-picks", "taste", "Steer your recommendations", "More, less, never; hidden gems; stretch me.",
    `<p>Open <a href="#taste">Your taste</a> to see what you lean towards and away from and to say more, less or never about any quality, including parents' guide items. On <a href="#for-you">For you</a> choose hidden gems or well known, a length, and how familiar the picks should be.</p>
     <p><a href="#plan">Plan my time</a> fills an evening, weekend or month; <a href="#together">Pick together</a> finds picks fair to several people.</p>`, "taste profile for you plan together control"],
  ["calendar-days", "community", "Social calendar and days of the year", "Something new or something for you on World Laughter Day and about 50 more.",
    `<p>The <a href="#calendar">calendar</a> lists challenges and events; <a href="#days">Days of the year</a> lists about 50 observances. Each day has two kinds of pick: something completely new, chosen from review scores across platforms, and picks from your own profile.</p>`, "calendar days of the year events world laughter"],
  ["accounts", "community", "Accounts and the community", "When sign-in arrives.",
    `<p>Accounts are optional. Everything works without one and your data stays in your browser. An account is a recovery key: it keeps your library, lists, ratings and journal in step across devices, encrypted on your device so Mimir cannot read it. Reviews, shared lists and hosted watch-alongs need the community server, which is not connected yet.</p>`, "account sign in login community"],
  ["your-data", "data", "What Mimir stores and where", "Your library lives in your browser.",
    `<p>Ratings, library, lists, journal, trackers and settings live in this browser's storage. Mimir does not send them to a server. Clearing site data or switching browsers removes them, so save a backup from <a href="#transfer">Import &amp; export</a>.</p>`, "privacy data storage local browser backup"],
  ["reset", "data", "Reset your recommendations", "Start again in one click.",
    `<p>In your profile, or in Import &amp; export, press reset. One confirmed click deletes your library, ratings, feedback and taste edits. Lists, journal, trackers and rings stay.</p>`, "reset delete clear start over"],
  ["report", "data", "Report a mistake or send feedback", "Wrong tag, missing work, broken link.",
    `<p>Mimir's tags, summaries and parents' guide levels are AI-assisted readings awaiting editorial review, so mistakes are expected. <a href="{{feedback}}">Send beta feedback</a> and say which work and what is wrong.</p>`, "feedback bug mistake missing wrong"],
];
const HELP_FAQ = [
  ["Is Mimir free?", "Yes. The catalogue, recommendations and library are free to use."],
  ["Do I need an account?", "No. Everything works without one and is saved in your browser. An optional account (a recovery key) keeps your library in step across devices, encrypted so Mimir cannot read it."],
  ["What happens if I lose my recovery key?", "Nobody can recover it, because Mimir never has it. Your data stays on the devices where you are signed in, so export it from the Account page and make a new vault."],
  ["Can I back up my recovery key with a passphrase?", "Yes. When Mimir shows you a new recovery key, open \"Also save a passphrase-protected backup\", choose a passphrase of at least 12 characters and download the backup. To use it later, choose \"Sign in with a protected backup\" on the Account page. The key is locked on your device: Mimir never sees the passphrase or the backup, and cannot recover either one. Keep the passphrase somewhere other than the backup."],
  ["What does Mimir collect?", "Nothing, unless you allow it: your library stays on your device. If you allow analytics, Mimir counts anonymous usage such as pages, features and device type, never what you search for, rate or save. Change this any time from Privacy choices in the footer, and read the privacy notice."],
  ["Where are my ratings and library stored?", "In this browser only. Save a backup from Import & export, because clearing site data removes them."],
  ["Why does a work have no summary?", "Many works were imported from Wikidata with facts only. Summaries, moods and parents' guides are filled in batches."],
  ["What does \"Not assessed\" mean in a parents' guide?", "That category has not been reviewed yet. It does not mean the work is safe."],
  ["Are the tags and summaries written by people?", "They are AI-assisted readings awaiting editorial review, and the site labels them that way."],
  ["Can I import my MyAnimeList, IMDb, Letterboxd or Goodreads history?", "Yes, from Import & export."],
  ["How do I stop seeing something?", "Mark it not for me when you swipe or rate it, or say never about its qualities in Your taste."],
  ["How do I start my recommendations from scratch?", "Use the reset button in your profile or in Import & export."],
  ["How do I report something wrong?", "Use Send beta feedback in the Catalogue menu and name the work."],
];
return { HELP_CATS, HELP, HELP_FAQ };
});
