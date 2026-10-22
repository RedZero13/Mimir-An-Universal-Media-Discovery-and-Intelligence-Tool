import Link from "next/link";
import { notFound } from "next/navigation";
import { BasisTag } from "@/components/BasisTag";
import { getWork } from "@/lib/api";
import { DIMENSION_LABELS, intensity, mediumLabel } from "@/lib/format";
import type { Classification, Work } from "@/lib/types";

const DIMENSION_ORDER = ["genre", "theme", "mood", "pacing", "complexity", "narrative", "world", "style"];

function lengthText(w: Work): string | null {
  const approx = w.length_is_estimate ? "about " : "";
  if (w.runtime_minutes) return `${approx}${w.runtime_minutes} minutes`;
  if (w.playtime_hours) return `${approx}${w.playtime_hours} hours (main path)`;
  return null;
}

function basisOf(c: Classification) {
  if (!c.is_interpretation) return "catalogue" as const;
  return c.review_status === "reviewed" ? ("reviewed_interpretation" as const) : ("interpretation" as const);
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const work = await getWork((await params).slug).catch(() => null);
  return { title: work ? `${work.title} · Media Discovery` : "Not found" };
}

export default async function WorkPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const work = await getWork(slug);
  if (!work) notFound();

  const visible = work.classifications.filter((c) => !c.is_spoiler && c.strength > 0);
  const byDimension = DIMENSION_ORDER.map((d) => [d, visible.filter((c) => c.dimension === d)] as const).filter(
    ([, cs]) => cs.length > 0,
  );
  const advisories = work.classifications.filter((c) => c.dimension === "advisory");
  const length = lengthText(work);
  const facts: [string, string][] = [
    ["Medium", mediumLabel(work.medium)],
    ["Released", work.release_year ? String(work.release_year) : "Unknown"],
    ["Original language", work.original_language ?? "None / not recorded"],
    ["Country", work.countries.length ? work.countries.join(", ") : "Not recorded"],
    ["Length", length ?? "Not recorded"],
  ];
  const platforms = work.attributes["platforms"];
  if (Array.isArray(platforms)) facts.push(["Platforms", platforms.join(", ")]);

  return (
    <article className="work">
      <p className="crumbs">
        <Link href="/">← Discover</Link>
      </p>
      <h1>{work.title}</h1>
      {work.original_title && <p className="original-title">{work.original_title}</p>}
      <p className="meta">
        {mediumLabel(work.medium)} · {work.release_year ?? "year unknown"}
        {work.credits.length > 0 && <> · {work.credits.slice(0, 3).map((c) => c.name).join(", ")}</>}
      </p>
      {work.summary && <p className="lede">{work.summary}</p>}
      {work.summary_spoiler && (
        <details className="spoiler">
          <summary>Show the full plot (spoilers)</summary>
          <p>{work.summary_spoiler}</p>
        </details>
      )}
      <p>
        <Link className="button" href={`/?q=${encodeURIComponent(`something like "${work.title}"`)}`}>
          Find similar works
        </Link>{" "}
        <Link
          className="button secondary"
          href={`/?q=${encodeURIComponent(`something like "${work.title}" in a different medium`)}`}
        >
          …in other media
        </Link>
      </p>

      <section>
        <h2>What kind of experience is it?</h2>
        <p className="muted small">
          Bars show how strongly each quality applies. Labels show whether it is catalogue data or an interpretation.
        </p>
        {byDimension.map(([dim, cs]) => (
          <div key={dim} className="dimension">
            <h3>{DIMENSION_LABELS[dim] ?? dim}</h3>
            <ul className="terms">
              {cs.map((c) => (
                <li key={c.slug} title={c.definition}>
                  <span className="term-label">{c.label}</span>
                  <span className="bar" aria-label={`${intensity(c.strength)} (${Math.round(c.strength * 100)}%)`}>
                    <span style={{ width: `${Math.round(c.strength * 100)}%` }} />
                  </span>
                  <BasisTag basis={basisOf(c)} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>

      <section>
        <h2>Before you start</h2>
        {!work.advisories_assessed || advisories.length === 0 ? (
          <p>Content advisories haven&apos;t been assessed for this work yet.</p>
        ) : (
          <ul className="advisories">
            {advisories.map((a) => (
              <li key={a.slug}>
                {a.label}: <strong>{intensity(a.strength)}</strong> <BasisTag basis={basisOf(a)} />
              </li>
            ))}
          </ul>
        )}
      </section>

      {work.relationships.length > 0 && (
        <section>
          <h2>Connected works</h2>
          <ul className="relations">
            {work.relationships
              .filter((r) => !r.is_spoiler)
              .map((r) => (
                <li key={`${r.type}-${r.slug}`}>
                  <BasisTag basis={r.factual ? "catalogue" : "interpretation"} /> {r.label[0].toUpperCase() + r.label.slice(1)}{" "}
                  <Link href={`/works/${r.slug}`}>{r.title}</Link> ({mediumLabel(r.medium)}
                  {r.release_year ? `, ${r.release_year}` : ""}){r.note && <span className="muted">: {r.note}</span>}
                </li>
              ))}
          </ul>
        </section>
      )}

      <section>
        <h2>Facts and sources</h2>
        <dl className="facts">
          {facts.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
          {work.credits.map((c) => (
            <div key={`${c.role}-${c.name}`}>
              <dt>{c.role[0].toUpperCase() + c.role.slice(1)}</dt>
              <dd>{c.name}</dd>
            </div>
          ))}
        </dl>
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
