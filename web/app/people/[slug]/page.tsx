import Link from "next/link";
import { notFound } from "next/navigation";
import { WorkCard } from "@/components/WorkCard";
import { getPerson } from "@/lib/api";
import { tagHref } from "@/lib/format";

type Params = Promise<{ slug: string }>;

export async function generateMetadata({ params }: { params: Params }) {
  const person = await getPerson((await params).slug).catch(() => null);
  return { title: person ? `${person.name} · Mimir` : "Not found" };
}

export default async function PersonPage({ params }: { params: Params }) {
  const person = await getPerson((await params).slug);
  if (!person) notFound();
  return (
    <>
      <p className="crumbs">
        <Link href="/people">People &amp; studios</Link>
      </p>
      <h1>{person.name}</h1>
      <p className="meta">
        {person.kind === "organisation" ? "Studio / organisation" : "Person"} · {person.roles.join(", ")}
      </p>
      {person.recurring_tags.length > 0 && (
        <section>
          <h2>Recurring qualities</h2>
          <ul className="tag-cloud">
            {person.recurring_tags.map((t) => (
              <li key={t.key}>
                <Link href={tagHref(t.key)} className="tag-chip">
                  {t.label} <span className="count">{t.count}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h2>Works in the catalogue</h2>
        <ol className="work-grid">
          {person.works.map((w) => (
            <WorkCard key={w.slug} work={w} extra={w.roles && <p className="meta">Credited as {w.roles.join(", ")}</p>} />
          ))}
        </ol>
      </section>
    </>
  );
}
