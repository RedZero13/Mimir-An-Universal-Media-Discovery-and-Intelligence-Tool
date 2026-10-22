import Link from "next/link";
import { WorkCard } from "@/components/WorkCard";
import { browse } from "@/lib/api";
import { AVOID_OPTIONS, languageLabel, mediumLabel } from "@/lib/format";
import { asArray, asString, browseHref, type SearchParams } from "@/lib/params";
import type { FacetValue } from "@/lib/types";

export const metadata = { title: "Browse the catalogue · Mimir" };

const SORTS = [
  ["popular", "Best known"],
  ["title", "Title A–Z"],
  ["newest", "Newest"],
  ["oldest", "Oldest"],
  ["shortest", "Shortest"],
] as const;

function Facet({ title, values, params, paramKey, label }: {
  title: string;
  values: FacetValue[];
  params: SearchParams;
  paramKey: string;
  label?: (v: FacetValue) => string;
}) {
  if (!values.length) return null;
  const active = asArray(params[paramKey]);
  return (
    <div className="facet">
      <h3>{title}</h3>
      <ul>
        {values.map((v) => {
          const value = String(v.value);
          const on = active.includes(value);
          // Tags and media combine; decade and language replace each other. Clicking an active value removes it.
          const multi = paramKey === "tag" || paramKey === "medium";
          const href = multi
            ? browseHref(params, paramKey, value, on ? "remove" : "add")
            : browseHref(params, paramKey, on ? null : value, "set");
          return (
            <li key={value}>
              <Link href={href} className={on ? "on" : undefined}>
                {label ? label(v) : v.label}
              </Link>{" "}
              <span className="count">{v.count}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default async function BrowsePage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const filters = {
    medium: asArray(params.medium),
    tag: asArray(params.tag),
    avoid: asArray(params.avoid),
    decade: asString(params.decade),
    language: asString(params.language),
    max_minutes: asString(params.max_minutes),
    q: asString(params.q),
    sort: asString(params.sort) || "popular",
  };

  let data;
  try {
    data = await browse(filters);
  } catch {
    return <p className="error">The catalogue service isn&apos;t reachable right now. Is the API running?</p>;
  }

  const activeChips: { label: string; href: string }[] = [
    ...filters.medium.map((m) => ({ label: mediumLabel(m), href: browseHref(params, "medium", m, "remove") })),
    ...filters.tag.map((t) => ({
      label: t.split(":")[1].replace(/-/g, " "),
      href: browseHref(params, "tag", t, "remove"),
    })),
    ...(filters.decade ? [{ label: `${filters.decade}s`, href: browseHref(params, "decade", null, "set") }] : []),
    ...(filters.language ? [{ label: languageLabel(filters.language), href: browseHref(params, "language", null, "set") }] : []),
  ];

  return (
    <>
      <h1>Browse the catalogue</h1>
      <form className="browse-form" action="/browse" method="get">
        {filters.tag.map((t) => <input key={t} type="hidden" name="tag" value={t} />)}
        {filters.decade && <input type="hidden" name="decade" value={filters.decade} />}
        {filters.language && <input type="hidden" name="language" value={filters.language} />}
        <div className="row">
          <label htmlFor="q">Title or name</label>
          <input id="q" name="q" type="search" defaultValue={filters.q} placeholder="e.g. Tarkovsky, Solaris" />
        </div>
        <fieldset>
          <legend>Medium</legend>
          {["film", "book", "game", "album"].map((m) => (
            <label key={m} className="check">
              <input type="checkbox" name="medium" value={m} defaultChecked={filters.medium.includes(m)} /> {mediumLabel(m)}
            </label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Parents&apos; guide: none or mild</legend>
          {AVOID_OPTIONS.map((o) => (
            <label key={o.key} className="check">
              <input type="checkbox" name="avoid" value={o.key} defaultChecked={filters.avoid.includes(o.key)} /> {o.label}
            </label>
          ))}
          <p className="muted small">Works that haven&apos;t been assessed for a checked category are left out.</p>
        </fieldset>
        <div className="row inline">
          <label htmlFor="max_minutes">Max length</label>
          <select id="max_minutes" name="max_minutes" defaultValue={filters.max_minutes}>
            <option value="">Any</option>
            <option value="90">90 min</option>
            <option value="120">2 hours</option>
            <option value="180">3 hours</option>
            <option value="600">10 hours</option>
          </select>
          <label htmlFor="sort">Sort</label>
          <select id="sort" name="sort" defaultValue={filters.sort}>
            {SORTS.map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <button className="button" type="submit">
            Apply
          </button>
        </div>
      </form>

      {activeChips.length > 0 && (
        <p className="active-filters">
          {activeChips.map((c) => (
            <Link key={c.href} href={c.href} className="chip chip-limit" aria-label={`Remove filter ${c.label}`}>
              {c.label} ×
            </Link>
          ))}{" "}
          <Link href="/browse" className="small">
            Clear all
          </Link>
        </p>
      )}

      <div className="browse-layout">
        <aside className="facets" aria-label="Refine">
          <Facet title="Medium" values={data.facets.medium} params={params} paramKey="medium" label={(v) => mediumLabel(String(v.value))} />
          <Facet title="Genre" values={data.facets.genre} params={params} paramKey="tag" />
          <Facet title="Themes" values={data.facets.theme} params={params} paramKey="tag" />
          <Facet title="Mood" values={data.facets.mood} params={params} paramKey="tag" />
          <Facet title="Decade" values={data.facets.decade} params={params} paramKey="decade" />
          <Facet title="Original language" values={data.facets.language} params={params} paramKey="language" label={(v) => languageLabel(String(v.value))} />
        </aside>
        <section aria-label="Results" className="browse-results">
          <p className="muted">{data.total === 1 ? "1 work" : `${data.total} works`}</p>
          {data.total === 0 ? (
            <p className="empty">Nothing matches these filters. Try removing one.</p>
          ) : (
            <ol className="work-grid">
              {data.results.map((w) => (
                <WorkCard key={w.slug} work={w} />
              ))}
            </ol>
          )}
        </section>
      </div>
    </>
  );
}
