import Link from "next/link";
import { notFound } from "next/navigation";
import { WorkCard } from "@/components/WorkCard";
import { getTag } from "@/lib/api";
import { intensity, tagHref } from "@/lib/format";

type Params = Promise<{ dimension: string; slug: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const { dimension, slug } = await params;
  const tag = await getTag(`${dimension}:${slug}`).catch(() => null);
  return { title: tag ? `${tag.label} · Mimir` : "Not found" };
}

export default async function TagPage({ params }: { params: Params }) {
  const { dimension, slug } = await params;
  const tag = await getTag(`${dimension}:${slug}`);
  if (!tag) notFound();
  return (
    <>
      <p className="crumbs">
        <Link href="/tags">Tags</Link> / {tag.dimension_label}
      </p>
      <h1>{tag.label}</h1>
      <p className="lede">{tag.definition}</p>
      <p>
        <Link className="button secondary" href={`/browse?tag=${encodeURIComponent(tag.key)}`}>
          Filter the catalogue by this tag
        </Link>
      </p>
      {tag.related.length > 0 && (
        <section>
          <h2>Often found with</h2>
          <ul className="tag-cloud">
            {tag.related.map((r) => (
              <li key={r.key}>
                <Link href={tagHref(r.key)} className="tag-chip">
                  {r.label} <span className="count">{r.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2>{tag.works.length === 1 ? "1 work" : `${tag.works.length} works`}, strongest first</h2>
        <ol className="work-grid">
          {tag.works.map((w) => (
            <WorkCard
              key={w.slug}
              work={w}
              extra={
                w.strength !== undefined && (
                  <p className="strength">
                    <span className="bar" aria-hidden>
                      <span style={{ width: `${Math.round(w.strength * 100)}%` }} />
                    </span>{" "}
                    {intensity(w.strength)} ({Math.round(w.strength * 100)}%)
                  </p>
                )
              }
            />
          ))}
        </ol>
      </section>
    </>
  );
}
