import Link from "next/link";
import { notFound } from "next/navigation";
import { BasisTag } from "@/components/BasisTag";
import { ParentsGuide } from "@/components/ParentsGuide";
import { getWork } from "@/lib/api";
import { intensity, languageLabel, mediumLabel, tagHref } from "@/lib/format";
import type { Work } from "@/lib/types";

type Params = Promise<{ slug: string }>;

function lengthText(w: Work): string {
  const approx = w.length_is_estimate ? "about " : "";
  if (w.runtime_minutes) return `${approx}${w.runtime_minutes} minutes`;
  if (w.playtime_hours) return `${approx}${w.playtime_hours} hours (main path)`;
  return w.medium === "book" ? "Varies by edition" : "Not recorded";
}

const ROLE_ORDER = ["director", "author", "developer", "artist", "writer", "cinematographer", "studio", "publisher"];
const roleLabel = (r: string) => r[0].toUpperCase() + r.slice(1);
const roleRank = (r: string) => (ROLE_ORDER.includes(r) ? ROLE_ORDER.indexOf(r) : ROLE_ORDER.length);

export async function generateMetadata({ params }: { params: Params }) {
  const work = await getWork((await params).slug).catch(() => null);
  return { title: work ? `${work.title} (${work.year ?? "?"}) · Mimir` : "Not found" };
}

export default async function WorkPage({ params }: { params: Params }) {
  const work = await getWork((await params).slug);
  if (!work) notFound();

  const facts: [string, React.ReactNode][] = [
    ["Medium", <Link key="m" href={`/browse?medium=${work.medium}`}>{mediumLabel(work.medium)}</Link>],
    ["Released", work.year ? <Link key="y" href={`/browse?decade=${Math.floor(work.year / 10) * 10}`}>{work.year}</Link> : "Unknown"],
    ["Length", lengthText(work)],
    ["Original language", work.original_language ? languageLabel(work.original_language) : "None / not recorded"],
    ["Country", work.countries.length ? work.countries.join(", ") : "Not recorded"],
  ];
  const platforms = work.attributes["platforms"];
  if (Array.isArray(platforms)) facts.push(["Platforms", platforms.join(", ")]);
  const credits = [...work.credits].sort((a, b) => roleRank(a.role) - roleRank(b.role));

  return (
    <article className="work">
      <p className="crumbs">
        <Link href="/browse">Catalogue</Link> / <Link href={`/browse?medium=${work.medium}`}>{mediumLabel(work.medium)}</Link>
      </p>
      <h1>{work.title}</h1>
      {work.original_title && <p className="original-title">{work.original_title}</p>}
      <p className="meta">
        {[mediumLabel(work.medium), work.year, work.length].filter(Boolean).join(" · ")}
        {work.parents_guide.ratings.map((r) => (
          <a key={r.system} href="#parents-guide" className="rating" title={`${r.system} rating`}>
            {r.rating}
          </a>
        ))}
      </p>
      <nav className="section-nav" aria-label="On this page">
        <a href="#overview">Overview</a>
        <a href="#tags">Tags</a>
        <a href="#parents-guide">Parents&apos; guide</a>
        <a href="#credits">Credits</a>
        {work.relationships.length > 0 && <a href="#connected">Connected works</a>}
        <a href="#sources">Sources</a>
      </nav>

      <section id="overview">
        {work.summary && <p className="lede">{work.summary}</p>}
        <dl className="facts">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <p className="actions">
          <Link className="button" href={`/?q=${encodeURIComponent(`something like "${work.title}"`)}`}>
            Find similar works
          </Link>
          <Link className="button secondary" href={`/?q=${encodeURIComponent(`something like "${work.title}" in a different medium`)}`}>
            …in other media
          </Link>
        </p>
      </section>

      <section id="tags">
        <h2>Tags</h2>
        <p className="muted small">Bars show how strongly each quality applies. Select a tag to see every work that has it.</p>
        {work.tags.map((group) => (
          <div key={group.dimension} className="dimension">
            <h3>{group.label}</h3>
            <ul className="terms">
              {group.terms.map((t) => (
                <li key={t.key} title={t.definition}>
                  <Link href={tagHref(t.key)} className="term-label">
                    {t.label}
                  </Link>
                  <span className="bar" role="img" aria-label={`${intensity(t.strength)} (${Math.round(t.strength * 100)}%)`}>
                    <span style={{ width: `${Math.round(t.strength * 100)}%` }} />
                  </span>
                  <BasisTag basis={t.basis} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <ParentsGuide guide={work.parents_guide} />

      <section id="credits">
        <h2>Credits</h2>
        <dl className="facts">
          {credits.map((c) => (
            <div key={`${c.role}-${c.slug}`}>
              <dt>{roleLabel(c.role)}</dt>
              <dd>
                <Link href={`/people/${c.slug}`}>{c.name}</Link>
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {work.relationships.length > 0 && (
        <section id="connected">
          <h2>Connected works</h2>
          <ul className="relations">
            {work.relationships.map((r) => (
              <li key={`${r.type}-${r.slug}`}>
                <BasisTag basis={r.factual ? "catalogue" : "interpretation"} /> {r.label[0].toUpperCase() + r.label.slice(1)}{" "}
                <Link href={`/works/${r.slug}`}>{r.title}</Link> ({mediumLabel(r.medium)}
                {r.year ? `, ${r.year}` : ""}){r.note && <span className="muted">: {r.note}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section id="sources">
        <h2>Sources</h2>
        <ul className="sources small">
          {work.sources.map((s) => (
            <li key={s.slug}>
              <strong>{s.name}</strong>
              {s.notes && <span className="muted">: {s.notes}</span>}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
